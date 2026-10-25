"""First-login credentials for a volunteer already authenticated by invitation.

No email messages, unauthenticated reset links or password exposure.
"""

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .invitations import RESTRICTED_ROLES
from .models import Invitation
from .private_api import ERRORS, Conflict, PrivateView


def eligible_for_setup(user):
    """Only active ordinary invited accounts, never privileged accounts."""
    return bool(
        user.is_authenticated
        and user.is_active
        and not user.is_staff
        and not user.is_superuser
        and not user.has_usable_password()
        and not user.groups.filter(name__in=RESTRICTED_ROLES).exists()
        and not user.has_perm("catalog.publish_event")
        and not user.has_perm("catalog.add_invitation")
        and Invitation.objects.filter(used_by=user, used_at__isnull=False).exists()
    )


class SetupState(serializers.Serializer):
    needs_setup = serializers.BooleanField()


class SetupBody(serializers.Serializer):
    password = serializers.CharField(
        min_length=12, max_length=128, trim_whitespace=False, write_only=True
    )
    confirmation = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate(self, values):
        if values["password"] != values["confirmation"]:
            raise exceptions.ValidationError({"confirmation": "Passwords do not match."})
        try:
            validate_password(values["password"], user=self.context["request"].user)
        except DjangoValidationError:
            raise exceptions.ValidationError({"password": "Choose a stronger password."}) from None
        return values


class VolunteerCredentialsView(PrivateView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sign_in"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(responses={200: SetupState, **ERRORS}, operation_id="private_credentials_status")
    def get(self, request):
        return Response({"needs_setup": eligible_for_setup(request.user)})

    @extend_schema(
        request=SetupBody,
        responses={200: SetupState, **ERRORS},
        operation_id="private_credentials_setup",
    )
    def post(self, request):
        if not eligible_for_setup(request.user):
            raise Conflict("Password setup is not available for this account.")
        body = SetupBody(data=request.data, context={"request": request})
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not eligible_for_setup(user):
                raise Conflict("Password setup is not available for this account.")
            user.set_password(body.validated_data["password"])
            user.save(update_fields=["password"])
        # Preserve just the current session; changing the password invalidates others.
        update_session_auth_hash(request._request, user)
        return Response({"needs_setup": False})
