"""Private review API (ADR 0009). Session authentication, CSRF on writes, permission checked on
every request; the crosswalk services stay the only writers."""

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.authentication import SessionScheme
from drf_spectacular.utils import extend_schema
from rescue.middleware import LOCAL_AUTO_LOGIN_OFF, local_auto_login_user
from rest_framework import exceptions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .api import ErrorSerializer, parameters
from .crosswalk import (
    REVIEW_PERMISSION,
    STAGE_PERMISSION,
    approve_exact_carries,
    approve_link,
    propose_links,
)
from .logbook_sync import rows_already_in_sheet
from .models import SHEETS, RowIdentityLink, SheetRow, SheetSnapshot, SourceIdentity

PROPOSAL_KINDS = ("new", "exact_carry", "candidates", "blocked", "repeat", "linked")
STATUS_BY_PROPOSAL = {
    "new": "to_review",
    "exact_carry": "to_review",
    "candidates": "to_review",
    "blocked": "blocked",
    # A row entered twice in the sheet is fixed there, like an error (acceptance D4).
    "repeat": "blocked",
    "linked": "linked",
}
STATUSES = ("to_review", "blocked", "linked")
# Identity review concerns event sheets; Data_ports rows are read as port labels (UI2).
REVIEW_SHEETS = ("Data_operations", "Other_data")
ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 405, 409, 429)}


class Conflict(exceptions.APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "The state changed or the rule refuses this decision; reload and decide again."


class InvalidCredentials(exceptions.APIException):
    status_code = 400
    default_code = "invalid_credentials"
    # One message whatever failed (unknown user, wrong password, inactive account).
    default_detail = "Username or password is incorrect."


class PrivateSessionAuthentication(SessionAuthentication):
    # A challenge makes DRF answer 401 (not 403) when there is no session.
    def authenticate_header(self, request):
        return "Session"


class PrivateSessionScheme(SessionScheme):
    # Documents the session cookie for the private views in OpenAPI.
    target_class = "catalog.private_api.PrivateSessionAuthentication"
    name = "privateSession"


def has_any_perm(user, *permissions):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and any(user.has_perm(permission) for permission in permissions)
    )


class CanReviewIdentities(BasePermission):
    def has_permission(self, request, view):
        return has_any_perm(request.user, REVIEW_PERMISSION)


class CanStageSnapshots(BasePermission):
    def has_permission(self, request, view):
        return has_any_perm(request.user, STAGE_PERMISSION)


class CanStageOrReview(BasePermission):
    def has_permission(self, request, view):
        return has_any_perm(request.user, STAGE_PERMISSION, REVIEW_PERMISSION)


def private_error_code(exc):
    """Explicit error codes for the private API; the public API keeps its http_<status> codes."""
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return "not_authenticated"
    if isinstance(exc, exceptions.PermissionDenied):
        return "csrf_failed" if str(exc.detail).startswith("CSRF Failed") else "permission_denied"
    if isinstance(
        exc, (exceptions.ValidationError, exceptions.ParseError, exceptions.UnsupportedMediaType)
    ):
        return "invalid"
    if isinstance(exc, exceptions.MethodNotAllowed):
        return "method_not_allowed"
    if isinstance(exc, Conflict):
        # Subclasses name the rule that refused, e.g. rights_not_approved.
        return exc.default_code
    if isinstance(exc, InvalidCredentials):
        return "invalid_credentials"
    if isinstance(exc, exceptions.Throttled):
        return "throttled"
    return (
        "not_found"
        if getattr(exc, "status_code", None) == 404 or exc.__class__.__name__ == "Http404"
        else "error"
    )


class PrivateView(APIView):
    private_api = True
    authentication_classes = [PrivateSessionAuthentication]
    permission_classes = [CanReviewIdentities]
    parser_classes = [JSONParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


def page(values, items):
    offset, limit = values["offset"], values["limit"]
    return {
        "items": items[offset : offset + limit],
        "total_count": len(items),
        "has_next": offset + limit < len(items),
    }


class PageParams(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=25)
    offset = serializers.IntegerField(min_value=0, max_value=100000, default=0)


# Me


class PermissionsSerializer(serializers.Serializer):
    review_identity = serializers.BooleanField()
    stage_snapshot = serializers.BooleanField()
    prepare_drafts = serializers.BooleanField()
    publish = serializers.BooleanField()
    invite = serializers.BooleanField()


class MeSerializer(serializers.Serializer):
    username = serializers.CharField()
    permissions = PermissionsSerializer()
    decisions = serializers.IntegerField(
        help_text="Verification decisions this person has recorded: their progress, never a score."
    )


def me_payload(user):
    return {
        "username": user.get_username(),
        "decisions": RowIdentityLink.objects.filter(approved_by=user).count(),
        "permissions": {
            "review_identity": user.has_perm(REVIEW_PERMISSION),
            "stage_snapshot": user.has_perm(STAGE_PERMISSION),
            "prepare_drafts": user.has_perm("catalog.add_event"),
            "publish": user.has_perm("catalog.publish_event"),
            "invite": user.has_perm("catalog.add_invitation"),
        },
    }


class MeView(PrivateView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer, **ERRORS}, operation_id="private_me")
    def get(self, request):
        parameters(request, serializers.Serializer)
        return Response(me_payload(request.user))


class SignInSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=4096, trim_whitespace=False)


class SessionStateSerializer(serializers.Serializer):
    signed_in = serializers.BooleanField(
        help_text="Someone is signed in in this browser. Public pages ask this, never /me/."
    )
    local_auto_login = serializers.BooleanField(
        help_text="This local development machine can sign the team in without a password."
    )


class SessionView(PrivateView):
    """Sign in and out with the Django session, from the application's own screen.

    On a local machine with LOCAL_AUTO_LOGIN, signing out also stops the automatic sign-in for
    this browser (a cookie), and PUT brings it back."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sign_in"

    def get_throttles(self):
        # Only sign-in attempts are rate limited.
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(
        request=SignInSerializer,
        responses={200: MeSerializer, **ERRORS},
        operation_id="private_sign_in",
    )
    def post(self, request):
        # DRF checks CSRF only for authenticated users: a sign-in form must be protected too.
        PrivateSessionAuthentication().enforce_csrf(request)
        body = SignInSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user = authenticate(
            request._request,
            username=body.validated_data["username"],
            password=body.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise InvalidCredentials()
        # Rotates the session key and the CSRF token.
        login(request._request, user)
        response = Response(me_payload(user))
        response.delete_cookie(LOCAL_AUTO_LOGIN_OFF)
        return response

    @extend_schema(
        request=None, responses={200: SessionStateSerializer}, operation_id="private_session_state"
    )
    def get(self, request):
        return Response(
            SessionStateSerializer(
                {
                    "signed_in": request.user.is_authenticated,
                    "local_auto_login": local_auto_login_user() is not None,
                }
            ).data
        )

    @extend_schema(
        request=None, responses={200: MeSerializer, **ERRORS}, operation_id="private_resume_local"
    )
    def put(self, request):
        """Local machine only: sign in again as the automatic account after a sign-out."""
        PrivateSessionAuthentication().enforce_csrf(request)
        user = local_auto_login_user()
        if user is None:
            raise exceptions.NotFound()
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        response = Response(me_payload(user))
        response.delete_cookie(LOCAL_AUTO_LOGIN_OFF)
        return response

    @extend_schema(request=None, responses={204: None, **ERRORS}, operation_id="private_sign_out")
    def delete(self, request):
        if not request.user.is_authenticated:
            raise exceptions.NotAuthenticated()
        logout(request._request)
        response = Response(status=204)
        if local_auto_login_user() is not None:
            response.set_cookie(
                LOCAL_AUTO_LOGIN_OFF, "1", max_age=30 * 24 * 3600, httponly=True, samesite="Lax"
            )
        return response


# Snapshots


class SnapshotParams(PageParams):
    sheet = serializers.ChoiceField(choices=SHEETS, required=False)


class SourceRefSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()


class SnapshotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = SourceRefSerializer()
    sheet = serializers.CharField()
    created_at = serializers.DateTimeField()
    row_count = serializers.IntegerField()
    source_read = serializers.CharField()
    contract_version = serializers.CharField()


class SnapshotPageSerializer(serializers.Serializer):
    items = SnapshotSerializer(many=True)
    total_count = serializers.IntegerField()
    has_next = serializers.BooleanField()


class SnapshotsView(PrivateView):
    @extend_schema(
        parameters=[SnapshotParams],
        responses={200: SnapshotPageSerializer, **ERRORS},
        operation_id="private_list_snapshots",
    )
    def get(self, request):
        values = parameters(request, SnapshotParams)
        queryset = SheetSnapshot.objects.select_related("source").order_by("-created_at", "-pk")
        queryset = (
            queryset.filter(sheet=values.get("sheet"))
            if "sheet" in values
            else queryset.filter(sheet__in=REVIEW_SHEETS)
        )
        items = [
            {
                "id": snapshot.pk,
                "source": {"key": snapshot.source.key, "name": snapshot.source.name},
                "sheet": snapshot.sheet,
                "created_at": snapshot.created_at,
                "row_count": snapshot.row_count,
                "source_read": snapshot.source_read,
                "contract_version": snapshot.contract_version,
            }
            for snapshot in queryset
        ]
        return Response(SnapshotPageSerializer(page(values, items)).data)


# Review queue


class QueueParams(PageParams):
    snapshot = serializers.UUIDField()
    status = serializers.ChoiceField(choices=STATUSES, default="to_review")


class QueueItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    line = serializers.IntegerField()
    status = serializers.ChoiceField(choices=STATUSES)
    proposal = serializers.ChoiceField(choices=PROPOSAL_KINDS)
    candidate_count = serializers.IntegerField()
    repeats_line = serializers.IntegerField(
        allow_null=True, help_text="For a row entered twice: the earlier line it copies."
    )
    occurred_on = serializers.CharField(allow_null=True)
    kind = serializers.CharField(allow_null=True)
    people = serializers.IntegerField(allow_null=True)
    deaths = serializers.IntegerField(allow_null=True)
    error_codes = serializers.ListField(child=serializers.CharField())


class QueueCountsSerializer(serializers.Serializer):
    to_review = serializers.IntegerField()
    blocked = serializers.IntegerField()
    linked = serializers.IntegerField()


class QueuePageSerializer(serializers.Serializer):
    items = QueueItemSerializer(many=True)
    total_count = serializers.IntegerField()
    has_next = serializers.BooleanField()
    counts = QueueCountsSerializer()


def summary(candidate):
    candidate = candidate or {}
    return {
        "occurred_on": candidate.get("occurred_on"),
        "kind": candidate.get("kind"),
        "people": candidate.get("nb_survivor"),
        "deaths": candidate.get("death_nb_people"),
    }


class ReviewRowsView(PrivateView):
    @extend_schema(
        parameters=[QueueParams],
        responses={200: QueuePageSerializer, **ERRORS},
        operation_id="private_list_review_rows",
    )
    def get(self, request):
        values = parameters(request, QueueParams)
        snapshot = get_object_or_404(SheetSnapshot, pk=values["snapshot"])
        if snapshot.sheet not in REVIEW_SHEETS:
            raise exceptions.ValidationError(
                {"snapshot": "This sheet is not reviewed as identities."}
            )
        proposals = propose_links(snapshot)
        rows = {row.pk: row for row in snapshot.rows.only("id", "line", "candidate", "error_codes")}
        counts = {status: 0 for status in STATUSES}
        items = []
        for proposal in proposals:
            status = STATUS_BY_PROPOSAL[proposal.kind]
            counts[status] += 1
            if status != values["status"]:
                continue
            row = rows[proposal.row_id]
            items.append(
                {
                    "id": row.pk,
                    "line": row.line,
                    "status": status,
                    "proposal": proposal.kind,
                    "candidate_count": len(proposal.identity_ids)
                    if proposal.kind != "linked"
                    else 0,
                    "repeats_line": proposal.repeats_line,
                    **summary(row.candidate),
                    "error_codes": row.error_codes,
                }
            )
        return Response(QueuePageSerializer({**page(values, items), "counts": counts}).data)


# Row detail and decisions


class ReceivedSerializer(serializers.Serializer):
    headers = serializers.ListField(child=serializers.CharField(allow_blank=True))
    cells = serializers.ListField(child=serializers.CharField(allow_blank=True))


class SummarySerializer(serializers.Serializer):
    occurred_on = serializers.CharField(allow_null=True)
    kind = serializers.CharField(allow_null=True)
    people = serializers.IntegerField(allow_null=True)
    deaths = serializers.IntegerField(allow_null=True)


class CandidateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    external_id = serializers.CharField()
    summary = SummarySerializer()


class ProposalSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=PROPOSAL_KINDS)
    candidates = CandidateSerializer(many=True)
    repeats_line = serializers.IntegerField(allow_null=True)


class DecisionSerializer(serializers.Serializer):
    identity = serializers.UUIDField()
    external_id = serializers.CharField()
    match = serializers.CharField()
    approved_by = serializers.CharField()
    approved_at = serializers.DateTimeField()
    reason = serializers.CharField()


class SnapshotRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sheet = serializers.CharField()
    sha256 = serializers.CharField()
    contract_version = serializers.CharField()


class LogbookEvidenceSerializer(serializers.Serializer):
    url = serializers.URLField()
    rotation = serializers.CharField()
    logged_at = serializers.CharField()
    quote = serializers.CharField()
    to_check = serializers.ListField(child=serializers.CharField())
    sheet_line = serializers.IntegerField(
        allow_null=True, help_text="Line of the association's sheet that already holds this row."
    )


def logbook_evidence(row, in_sheet=None):
    """The logbook page and quote a rebuilt row comes from (ADR 0014); None for a sheet row.
    `in_sheet` maps rebuilt rows to the sheet line that holds them (rows_already_in_sheet)."""
    try:
        found = row.logbook
    except SheetRow.logbook.RelatedObjectDoesNotExist:
        return None
    if in_sheet is None:
        in_sheet = rows_already_in_sheet(row.snapshot.rows.all())
    return {
        "sheet_line": in_sheet.get(row.pk),
        "url": found.source_url,
        "rotation": found.rotation,
        "logged_at": found.logged_at,
        "quote": found.quote,
        "to_check": [part.strip() for part in found.to_check.split(";") if part.strip()],
    }


class RowDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    line = serializers.IntegerField()
    row_ref = serializers.CharField()
    snapshot = SnapshotRefSerializer()
    status = serializers.ChoiceField(choices=STATUSES)
    received = ReceivedSerializer()
    interpreted = serializers.JSONField(allow_null=True)
    error_codes = serializers.ListField(child=serializers.CharField())
    proposal = ProposalSerializer()
    decision = DecisionSerializer(allow_null=True)
    evidence = LogbookEvidenceSerializer(allow_null=True)


def latest_candidates(identity_ids):
    """Latest linked candidate of each identity, by snapshot date."""
    latest = {}
    links = (
        RowIdentityLink.objects.filter(identity_id__in=identity_ids)
        .select_related("row", "snapshot")
        .order_by("snapshot__created_at", "row__line")
    )
    for link in links:
        latest[link.identity_id] = link.row.candidate
    return latest


def row_detail(row):
    proposal = next(p for p in propose_links(row.snapshot) if p.row_id == row.pk)
    candidate_ids = proposal.identity_ids if proposal.kind != "linked" else ()
    latest = latest_candidates(candidate_ids)
    identities = SourceIdentity.objects.in_bulk(candidate_ids)
    link = getattr(row, "identity_link", None)
    return {
        "id": row.pk,
        "line": row.line,
        "row_ref": row.row_ref,
        "snapshot": {
            "id": row.snapshot.pk,
            "sheet": row.snapshot.sheet,
            "sha256": row.snapshot.sha256,
            "contract_version": row.snapshot.contract_version,
        },
        "status": STATUS_BY_PROPOSAL[proposal.kind],
        "received": {"headers": row.snapshot.header_cells, "cells": row.raw_cells},
        "interpreted": row.candidate,
        "error_codes": row.error_codes,
        "evidence": logbook_evidence(row),
        "proposal": {
            "kind": proposal.kind,
            "repeats_line": proposal.repeats_line,
            "candidates": [
                {
                    "id": pk,
                    "external_id": identities[pk].external_id,
                    "summary": summary(latest.get(pk)),
                }
                for pk in candidate_ids
                if pk in identities
            ],
        },
        "decision": None
        if link is None
        else {
            "identity": link.identity_id,
            "external_id": link.identity.external_id,
            "match": link.match,
            "approved_by": link.approved_by.get_username(),
            "approved_at": link.created_at,
            "reason": link.reason,
        },
    }


def load_row(pk):
    return get_object_or_404(
        SheetRow.objects.select_related(
            "snapshot", "identity_link__identity", "identity_link__approved_by"
        ),
        pk=pk,
    )


class ReviewRowView(PrivateView):
    @extend_schema(
        responses={200: RowDetailSerializer, **ERRORS}, operation_id="private_retrieve_review_row"
    )
    def get(self, request, id):
        parameters(request, serializers.Serializer)
        return Response(RowDetailSerializer(row_detail(load_row(id))).data)


class DecisionRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["create_identity", "link"])
    identity = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=2000)

    def validate(self, attrs):
        if attrs["action"] == "link" and "identity" not in attrs:
            raise exceptions.ValidationError({"identity": "Choose the identity to link."})
        if attrs["action"] == "create_identity" and "identity" in attrs:
            raise exceptions.ValidationError(
                {"identity": "A new identity takes no existing identity."}
            )
        return attrs


class ReviewDecisionView(PrivateView):
    @extend_schema(
        request=DecisionRequestSerializer,
        responses={200: RowDetailSerializer, **ERRORS},
        operation_id="private_decide_review_row",
    )
    def post(self, request, id):
        body = DecisionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = load_row(id)
        identity = None
        if body.validated_data["action"] == "link":
            identity = SourceIdentity.objects.filter(pk=body.validated_data["identity"]).first()
            if identity is None:
                raise exceptions.ValidationError({"identity": "Unknown identity."})
        try:
            approve_link(
                row=row, actor=request.user, reason=body.validated_data["reason"], identity=identity
            )
        except DjangoValidationError as exc:
            raise Conflict(detail=" ".join(exc.messages)) from exc
        return Response(RowDetailSerializer(row_detail(load_row(id))).data)


class ExactCarriesRequestSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    reason = serializers.CharField(max_length=2000)


class ExactCarriesResultSerializer(serializers.Serializer):
    carried = serializers.IntegerField()


class ExactCarriesView(PrivateView):
    @extend_schema(
        request=ExactCarriesRequestSerializer,
        responses={200: ExactCarriesResultSerializer, **ERRORS},
        operation_id="private_approve_exact_carries",
    )
    def post(self, request, id):
        body = ExactCarriesRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        snapshot = get_object_or_404(SheetSnapshot, pk=id)
        try:
            carried = approve_exact_carries(
                snapshot=snapshot,
                actor=request.user,
                reason=body.validated_data["reason"],
                rows=body.validated_data["rows"],
            )
        except DjangoValidationError as exc:
            raise Conflict(detail=" ".join(exc.messages)) from exc
        return Response({"carried": carried})


# Identity search


class IdentityParams(serializers.Serializer):
    snapshot = serializers.UUIDField()
    q = serializers.CharField(required=False, max_length=36)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=20)


class IdentityPageSerializer(serializers.Serializer):
    items = CandidateSerializer(many=True)


class IdentitiesView(PrivateView):
    @extend_schema(
        parameters=[IdentityParams],
        responses={200: IdentityPageSerializer, **ERRORS},
        operation_id="private_search_identities",
    )
    def get(self, request):
        values = parameters(request, IdentityParams)
        snapshot = get_object_or_404(SheetSnapshot, pk=values["snapshot"])
        identities = list(
            SourceIdentity.objects.filter(source=snapshot.source_id, sheet=snapshot.sheet)
        )
        latest = latest_candidates([identity.pk for identity in identities])
        query = values.get("q", "").strip().lower()
        items = []
        for identity in identities:
            facts = summary(latest.get(identity.pk))
            if query and not (
                (facts["occurred_on"] or "").startswith(query) or str(identity.pk).startswith(query)
            ):
                continue
            items.append({"id": identity.pk, "external_id": identity.external_id, "summary": facts})
        items.sort(
            key=lambda item: (item["summary"]["occurred_on"] or "", str(item["id"])), reverse=True
        )
        return Response(IdentityPageSerializer({"items": items[: values["limit"]]}).data)
