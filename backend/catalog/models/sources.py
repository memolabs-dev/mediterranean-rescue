from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .base import UUIDModel


class Source(UUIDModel):
    key = models.SlugField(_("short key"), unique=True)
    name = models.CharField(_("name"), max_length=200, help_text=_("As shown to the public."))
    url = models.URLField(_("address"), max_length=1000)
    license_note = models.TextField(
        _("licence and agreement"),
        blank=True,
        help_text=_("Who agreed to the publication, when, and under which terms."),
    )
    rights_approved = models.BooleanField(
        _("publication agreed"),
        default=False,
        help_text=_(
            "Tick only once the data owner has agreed in writing. Until then nothing from this "
            "source can be published."
        ),
    )
    synthetic = models.BooleanField(
        _("fictitious data"),
        default=False,
        help_text=_("Training data: shown publicly only in training mode."),
    )

    class Meta:
        verbose_name = _("source")
        verbose_name_plural = _("sources")
        constraints = [
            models.CheckConstraint(
                condition=Q(rights_approved=False) | ~Q(license_note__regex=r"^\s*$"),
                name="approved_source_has_licence_note",
                violation_error_message=_(
                    "Write who agreed and on which terms before ticking “publication agreed”."
                ),
            )
        ]

    def clean(self):
        if self.rights_approved and not self.license_note.strip():
            # Tied to the field: Django then skips the same check of the constraint, so the
            # message is shown once, next to the box to fill (acceptance of 25 October, L3).
            raise ValidationError(
                {
                    "license_note": _(
                        "Write who agreed and on which terms before ticking “publication agreed”."
                    )
                }
            )

    def __str__(self):
        return self.name
