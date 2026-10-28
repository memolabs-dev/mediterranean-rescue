from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .base import UUIDModel


class Vessel(UUIDModel):
    name = models.CharField(_("name"), max_length=200)
    imo = models.CharField(_("IMO number"), max_length=7, blank=True)

    class Meta:
        verbose_name = _("ship")
        verbose_name_plural = _("ships")

    def __str__(self):
        return self.name
class Voyage(UUIDModel):
    vessel = models.ForeignKey("catalog.Vessel", on_delete=models.PROTECT, related_name="voyages")
    title = models.CharField(max_length=200)
    started_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True)
    logbook_url = models.URLField(max_length=1000, blank=True)

    class Meta:
        verbose_name = _("voyage")
        verbose_name_plural = _("voyages")
        constraints = [
            models.CheckConstraint(
                condition=Q(ended_on__isnull=True) | Q(ended_on__gte=models.F("started_on")),
                name="voyage_dates_ordered",
            )
        ]

    def __str__(self):
        return self.title


class EventKind(models.TextChoices):
    RESCUE = "rescue", "Sauvetage"
    TRANSFER = "transfer", "Transfert"
    MEDEVAC = "medevac", "Évacuation médicale"
    INCIDENT = "incident", "Incident"
    SHIPWRECK = "shipwreck", "Naufrage"
    DEAD_MISSING = "dead_missing", "Décès / disparitions"


class EventQuerySet(models.QuerySet):
    def public(self):
        return self.filter(
            status="published",
            source__rights_approved=True,
            source__synthetic=settings.DATA_MODE == "training",
        ).exclude(source__license_note__regex=r"^\s*$")


class Event(UUIDModel):
    source = models.ForeignKey("catalog.Source", on_delete=models.PROTECT, related_name="events")
    external_id = models.CharField(max_length=200)
    kind = models.CharField(_("kind"), max_length=20, choices=EventKind.choices)
    occurred_on = models.DateField(_("date"), db_index=True)
    title = models.CharField(_("title"), max_length=240)
    summary = models.TextField(_("summary"), blank=True)
    source_url = models.URLField(_("source address"), max_length=1000)
    location = models.PointField(_("position"), srid=4326, null=True, blank=True)
    location_precision = models.CharField(
        max_length=16,
        choices=[
            ("unknown", "Inconnue"),
            ("approximate", "Approximative"),
            ("reported", "Rapportée"),
        ],
        default="unknown",
    )
    people = models.PositiveIntegerField(
        _("people"), null=True, blank=True, help_text=_("Leave empty when not known; never 0.")
    )
    women = models.PositiveIntegerField(_("women"), null=True, blank=True)
    minors = models.PositiveIntegerField(_("minors"), null=True, blank=True)
    vessel = models.ForeignKey("catalog.Vessel", null=True, blank=True, on_delete=models.PROTECT)
    voyage = models.ForeignKey("catalog.Voyage", null=True, blank=True, on_delete=models.PROTECT)
    port = models.ForeignKey("catalog.Port", null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12,
        choices=[("draft", "Brouillon"), ("published", "Publié"), ("withdrawn", "Retiré")],
        default="draft",
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")
        ordering = ["-occurred_on", "id"]
        permissions = [("publish_event", "Can publish or withdraw reviewed events")]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=EventKind.values), name="event_kind_known"),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "published", "withdrawn"]),
                name="event_status_known",
            ),
            # A position always says how precise it is; no position, no precision.
            models.CheckConstraint(
                condition=(Q(location__isnull=True) & Q(location_precision="unknown"))
                | (Q(location__isnull=False) & ~Q(location_precision="unknown")),
                name="event_position_has_precision",
            ),
            models.UniqueConstraint(fields=["source", "external_id"], name="event_source_identity"),
            models.CheckConstraint(
                condition=~Q(status="published")
                | (Q(published_at__isnull=False) & Q(reviewed_by__isnull=False)),
                name="published_event_has_review",
            ),
            models.CheckConstraint(
                condition=Q(people__isnull=True)
                | Q(women__isnull=True)
                | Q(women__lte=models.F("people")),
                name="women_within_total",
            ),
            models.CheckConstraint(
                condition=Q(people__isnull=True)
                | Q(minors__isnull=True)
                | Q(minors__lte=models.F("people")),
                name="minors_within_total",
            ),
        ]
        indexes = [models.Index(fields=["status", "occurred_on"], name="event_public_date")]

    def clean(self):
        URLValidator(schemes=["https", "http"])(self.source_url)
        if self.location:
            if not (-180 <= self.location.x <= 180 and -90 <= self.location.y <= 90):
                raise ValidationError("Invalid WGS84 coordinates")
            if self.location_precision == "unknown":
                raise ValidationError("A position needs an explicit precision")
        elif self.location_precision != "unknown":
            raise ValidationError("Position precision must be unknown without a position")
        if self.voyage_id and self.vessel_id and self.voyage.vessel_id != self.vessel_id:
            raise ValidationError("Voyage and event vessels differ")

    def __str__(self):
        return self.title


class Evidence(UUIDModel):
    event = models.ForeignKey("catalog.Event", related_name="evidence", on_delete=models.CASCADE)
    label = models.CharField(_("label"), max_length=200)
    url = models.URLField(_("address"), max_length=1000)

    class Meta:
        verbose_name = _("source document")
        verbose_name_plural = _("source documents")

    def __str__(self):
        return self.label
class EventRevision(UUIDModel):
    """Reviewed decision on a corrected source row for an existing draft (ADR 0007)."""

    event = models.ForeignKey("catalog.Event", on_delete=models.PROTECT, related_name="revisions")
    identity = models.ForeignKey("catalog.SourceIdentity", on_delete=models.PROTECT, related_name="revisions")
    from_row = models.ForeignKey("catalog.SheetRow", on_delete=models.PROTECT, related_name="+")
    to_row = models.ForeignKey("catalog.SheetRow", on_delete=models.PROTECT, related_name="+")
    # {field: [value before, value after]} for the translated fields that differ.
    changes = models.JSONField(default=dict, blank=True)
    decision = models.CharField(
        max_length=16, choices=[("applied", "Applied"), ("rejected", "Rejected")]
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()

    class Meta:
        verbose_name = _("correction")
        verbose_name_plural = _("corrections")
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(reason__regex=r"^\s*$"), name="event_revision_has_reason"
            ),
            models.CheckConstraint(
                condition=Q(decision__in=["applied", "rejected"]), name="event_revision_decision"
            ),
        ]
