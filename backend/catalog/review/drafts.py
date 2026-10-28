"""Event drafts from approved source identities (ADR 0006).

Drafts are private: publication still goes through services.set_publication (permission,
source rights, licence, reason, audit). Nothing here publishes, overwrites or guesses.
"""

from dataclasses import dataclass, field

from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Event, EventRevision, PortAlias, SheetSnapshot, SourceIdentity

DRAFT_PERMISSION = "catalog.add_event"
EVENT_SHEETS = ("Data_operations", "Other_data")
TITLES = {
    "rescue": "Rescue",
    "transfer": "Transfer",
    "medevac": "Medical evacuation",
    "incident": "Incident",
    "shipwreck": "Shipwreck",
    "dead_missing": "Dead and missing",
}


# Fields covered by Event's check constraints, already guaranteed when a draft is planned.
CHECKED_FIELDS = {
    "kind",
    "status",
    "location",
    "location_precision",
    "people",
    "women",
    "minors",
    "published_at",
    "reviewed_by",
}

# Event fields filled from a source row; their values at drafting time are kept on the identity.
DRAFT_FIELDS = (
    "kind",
    "occurred_on",
    "title",
    "location",
    "location_precision",
    "people",
    "women",
    "minors",
    "port",
)


def comparable_value(event, name):
    """JSON-friendly value used to compare and record a draft field."""
    if name == "port":
        return str(event.port_id) if event.port_id else None
    value = getattr(event, name)
    if name == "location":
        return [round(value.x, 10), round(value.y, 10)] if value else None
    if name == "occurred_on":
        return str(value)
    return value


def drafted_values(event):
    return {name: comparable_value(event, name) for name in DRAFT_FIELDS}


@dataclass(frozen=True)
class DraftPlan:
    row_id: object
    line: int
    # ready | not_linked | already_drafted | revision_needed | revision_rejected
    # | inconsistent_counts
    # | position_to_review | row_already_drafted | invalid_draft | stale_snapshot
    # | not_an_event_sheet
    outcome: str
    identity_id: object = None
    # For invalid_draft: names of the failing fields, never their values.
    detail: str = ""


@dataclass
class DraftResult:
    created: list = field(default_factory=list)  # (line, event id) pairs
    skipped: list = field(default_factory=list)


def _single_port(source, label):
    if not label:
        return None
    alias = PortAlias.objects.filter(source=source, label=label, target="ports").first()
    if alias is None:
        return None
    ports = list(alias.ports.all()[:2])
    return ports[0] if len(ports) == 1 else None


def _draft_event(row, identity):
    """Translate a linked row into an unsaved draft event. Unknown values stay null."""
    candidate = row.candidate
    source = identity.source
    position = candidate.get("position")
    counts = {}
    if row.snapshot.sheet == "Data_operations":
        # Deaths and missing (Other_data) never feed people: they are a different measure.
        counts = {
            "people": candidate.get("nb_survivor"),
            "women": candidate.get("female"),
            "minors": candidate.get("under_18"),
        }
    return Event(
        source=source,
        external_id=identity.external_id,
        kind=candidate["kind"],
        occurred_on=candidate["occurred_on"],
        title=f"{TITLES[candidate['kind']]} on {candidate['occurred_on']}",
        source_url=source.url,
        location=Point(float(position["longitude"]), float(position["latitude"]), srid=4326)
        if position
        else None,
        location_precision="reported" if position else "unknown",
        port=_single_port(source, candidate.get("Port_disembarkation")),
        status="draft",
        **counts,
    )


def _counts_consistent(event):
    return all(
        part is None or event.people is None or part <= event.people
        for part in (event.women, event.minors)
    )


def _plan_row(row):
    link = getattr(row, "identity_link", None)
    if link is None:
        return DraftPlan(row.pk, row.line, "not_linked"), None
    identity = link.identity
    if identity.event_id is not None:
        unchanged = identity.drafted_from.fingerprint == row.fingerprint
        rejected = EventRevision.objects.filter(
            identity=identity,
            decision="rejected",
            from_row__fingerprint=identity.drafted_from.fingerprint,
            to_row__fingerprint=row.fingerprint,
        ).exists()
        if unchanged:
            outcome = "already_drafted"
        else:
            # A rejected correction stays rejected while the export keeps that content.
            outcome = "revision_rejected" if rejected else "revision_needed"
        return DraftPlan(row.pk, row.line, outcome, identity.pk), None
    if SourceIdentity.objects.filter(drafted_from=row).exclude(pk=identity.pk).exists():
        # A row relinked to another identity must not describe a second event.
        return DraftPlan(row.pk, row.line, "row_already_drafted", identity.pk), None
    position = row.candidate.get("position")
    if position and float(position["longitude"]) == 0 and float(position["latitude"]) == 0:
        # 0,0 is usually a default value: never turn it into a reported location.
        return DraftPlan(row.pk, row.line, "position_to_review", identity.pk), None
    event = _draft_event(row, identity)
    if not _counts_consistent(event):
        return DraftPlan(row.pk, row.line, "inconsistent_counts", identity.pk), None
    try:
        # Check constraints cost one query each; every one they cover is already guaranteed here
        # (known kind by its choices, draft status, precision set with the position, counts checked
        # above) and the database still enforces them on insert. Only the identity's uniqueness
        # (source, external id) needs the database, so it is the one constraint validated.
        event.full_clean(validate_constraints=False)
        event.validate_constraints(exclude=CHECKED_FIELDS)
    except ValidationError as exc:
        fields = ",".join(sorted(getattr(exc, "message_dict", {"__all__": None})))
        return DraftPlan(row.pk, row.line, "invalid_draft", identity.pk, fields), None
    return DraftPlan(row.pk, row.line, "ready", identity.pk), event


def _plan(snapshot):
    rows = snapshot.rows.select_related(
        "snapshot", "identity_link__identity__source", "identity_link__identity__drafted_from"
    ).order_by("line")
    if snapshot.sheet not in EVENT_SHEETS:
        return [(DraftPlan(row.pk, row.line, "not_an_event_sheet"), None) for row in rows]
    latest = (
        SheetSnapshot.objects.filter(source=snapshot.source, sheet=snapshot.sheet)
        .order_by("-created_at", "-pk")
        .values_list("pk", flat=True)
        .first()
    )
    if latest != snapshot.pk:
        # Drafting from an older export would replay outdated content.
        return [(DraftPlan(row.pk, row.line, "stale_snapshot"), None) for row in rows]
    return [_plan_row(row) for row in rows]


def plan_drafts(snapshot):
    """One outcome per row of the snapshot, in line order. Writes nothing."""
    return [plan for plan, _ in _plan(snapshot)]


@transaction.atomic
def create_drafts(*, snapshot, actor, reason):
    """Create drafts for the ready rows in one transaction; list every skipped row."""
    if not actor.is_active or not actor.has_perm(DRAFT_PERMISSION):
        raise PermissionDenied(f"{DRAFT_PERMISSION} permission required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A review reason is required")
    identity_ids = snapshot.rows.filter(identity_link__isnull=False).values_list(
        "identity_link__identity", flat=True
    )
    # Lock the identities so two reviewers cannot draft the same one concurrently.
    # Locked in primary-key order so concurrent calls cannot deadlock each other.
    list(SourceIdentity.objects.select_for_update().filter(pk__in=identity_ids).order_by("pk"))
    result = DraftResult()
    now = timezone.now()
    for plan, event in _plan(snapshot):
        if plan.outcome != "ready":
            result.skipped.append(plan)
            continue
        try:
            with transaction.atomic():
                event.save()
        except IntegrityError as exc:
            raise ValidationError("Identity was drafted concurrently; nothing was created") from exc
        traced = SourceIdentity.objects.filter(pk=plan.identity_id, event__isnull=True).update(
            event=event,
            drafted_from=plan.row_id,
            drafted_by=actor,
            drafted_at=now,
            draft_reason=reason,
            drafted_values=drafted_values(event),
            updated_at=now,
        )
        if traced != 1:
            raise ValidationError("Identity was drafted concurrently; nothing was created")
        result.created.append((plan.line, event.pk))
    return result
