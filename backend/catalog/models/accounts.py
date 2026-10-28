from django.conf import settings
from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _
from .base import UUIDModel


class Invitation(UUIDModel):
    """A single-use link that signs a volunteer in without a password (ADR 0015).

    Only the SHA-256 of the token is stored: the link exists once, in the coordinator's hands.
    It works once, until it expires, unless revoked; it never signs in a staff or superuser
    account."""

    email = models.EmailField(_("email"))
    groups = models.ManyToManyField("auth.Group", blank=True, verbose_name=_("roles"))
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="invitations_sent",
        verbose_name=_("invited by"),
    )
    expires_at = models.DateTimeField(_("expires at"))
    used_at = models.DateTimeField(_("used at"), null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invitations_used",
        verbose_name=_("used by"),
    )
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    # The account the link opens when one already had this address at creation; a link made for a
    # new address never opens an account created later with it.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        # A nulled binding is refused at use as soon as any account holds the address.
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        verbose_name=_("account"),
    )

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        ordering = ["-created_at"]

    def __str__(self):
        return self.email
