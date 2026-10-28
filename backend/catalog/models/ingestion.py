from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from .base import UUIDModel


class ImportBatch(UUIDModel):
    source = models.ForeignKey("catalog.Source", on_delete=models.PROTECT)
    checksum = models.CharField(max_length=64)
    contract_version = models.CharField(max_length=16, default="1")
    status = models.CharField(
        max_length=16, default="staged", choices=[("staged", "En attente"), ("applied", "Appliqué")]
    )
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("import batch")
        verbose_name_plural = _("import batches")
        constraints = [
            models.UniqueConstraint(fields=["source", "checksum"], name="import_content_idempotent")
        ]


class StagedRecord(UUIDModel):
    batch = models.ForeignKey("catalog.ImportBatch", related_name="records", on_delete=models.CASCADE)
    ordinal = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    payload = models.JSONField()

    class Meta:
        verbose_name = _("staged record")
        verbose_name_plural = _("staged records")
        constraints = [
            models.UniqueConstraint(fields=["batch", "ordinal"], name="import_row_identity")
        ]
SHEETS = [
    ("Data_operations", "Data_operations"),
    ("Other_data", "Other_data"),
    ("Data_ports", "Data_ports"),
]


class SheetSnapshot(UUIDModel):
    """One diagnosed Sheets export in private staging; raw cells never leave it."""

    source = models.ForeignKey("catalog.Source", on_delete=models.PROTECT, related_name="sheet_snapshots")
    sheet = models.CharField(max_length=32, choices=SHEETS)
    sha256 = models.CharField(max_length=64)
    contract_version = models.CharField(max_length=40)
    source_read = models.CharField(max_length=16)
    byte_count = models.PositiveIntegerField()
    row_count = models.PositiveIntegerField()
    # Header row as received, so a row can be shown with its exact column names.
    header_cells = models.JSONField(default=list, blank=True)
    staged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        verbose_name = _("data update")
        verbose_name_plural = _("data updates")
        constraints = [
            models.UniqueConstraint(
                fields=["source", "sheet", "sha256", "contract_version"],
                name="sheet_snapshot_idempotent",
            )
        ]

    def __str__(self):
        return f"{self.sheet}@{self.sha256[:12]}"


class SheetSync(UUIDModel):
    """One scheduled reading of a Google Sheets tab and what it found (ADR 0012)."""

    source = models.ForeignKey("catalog.Source", on_delete=models.PROTECT, related_name="sheet_syncs")
    sheet = models.CharField(max_length=32, choices=SHEETS)
    status = models.CharField(
        max_length=16,
        choices=[
            ("new_data", "New data saved"),
            ("unchanged", "Unchanged"),
            ("refused", "Refused by the checks"),
            ("failed", "Could not read"),
        ],
    )
    snapshot = models.ForeignKey(
        "catalog.SheetSnapshot", on_delete=models.PROTECT, null=True, blank=True, related_name="syncs"
    )
    sha256 = models.CharField(max_length=64, blank=True)
    # Counts only (to look at, unchanged, to fix); never source values.
    summary = models.JSONField(default=dict, blank=True)
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = _("sheet reading")
        verbose_name_plural = _("sheet readings")
        indexes = [models.Index(fields=["source", "sheet", "-created_at"])]

    def __str__(self):
        return f"{self.sheet} {self.status} {self.created_at:%Y-%m-%d %H:%M}"


class SheetRow(UUIDModel):
    snapshot = models.ForeignKey("catalog.SheetSnapshot", on_delete=models.PROTECT, related_name="rows")
    line = models.PositiveIntegerField(validators=[MinValueValidator(2)])
    raw_cells = models.JSONField()
    candidate = models.JSONField(null=True, blank=True)
    # SHA-256 of the canonical candidate JSON; empty when the row could not be normalized.
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    error_codes = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _("row of a data update")
        verbose_name_plural = _("rows of data updates")
        ordering = ["snapshot", "line"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "line"], name="sheet_row_location")
        ]

    @property
    def row_ref(self):
        return f"{self.snapshot.sheet}@sha256:{self.snapshot.sha256}#L{self.line}"

    def __str__(self):
        return self.row_ref


class LogbookEvidence(UUIDModel):
    """Where a row rebuilt from the public logbook comes from (ADR 0014): the page, the entry and
    a short quote, shown next to the row so a volunteer can check it against the source."""

    row = models.OneToOneField("catalog.SheetRow", on_delete=models.CASCADE, related_name="logbook")
    source_url = models.URLField(max_length=1000)
    rotation = models.CharField(max_length=200)
    logged_at = models.CharField(max_length=40, help_text="Day and time of the logbook entry.")
    quote = models.TextField(max_length=500)
    to_check = models.TextField(blank=True)

    class Meta:
        verbose_name = _("logbook sentence")
        verbose_name_plural = _("logbook sentences")

    def __str__(self):
        return f"{self.rotation} {self.logged_at}"


class SourceIdentity(UUIDModel):
    """Durable identity we assign to a source record; created only by human approval."""

    source = models.ForeignKey("catalog.Source", on_delete=models.PROTECT, related_name="identities")
    sheet = models.CharField(max_length=32, choices=SHEETS)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()
    # Draft event created from this identity (ADR 0006); never overwritten once set.
    event = models.OneToOneField(
        "catalog.Event", null=True, blank=True, on_delete=models.PROTECT, related_name="source_identity"
    )
    drafted_from = models.ForeignKey(
        "SheetRow", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    drafted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    drafted_at = models.DateTimeField(null=True, blank=True)
    draft_reason = models.TextField(blank=True)
    # Translated field values the draft holds from its source row (after the last applied
    # revision); a later difference on the event means a hand edit.
    drafted_values = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("followed event")
        verbose_name_plural = _("followed events")
        permissions = [
            ("review_identity", "Can approve source identities, row links and port aliases")
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(reason__regex=r"^\s*$"), name="source_identity_has_reason"
            ),
            models.CheckConstraint(
                condition=(
                    Q(event__isnull=True)
                    & Q(drafted_from__isnull=True)
                    & Q(drafted_by__isnull=True)
                    & Q(drafted_at__isnull=True)
                    & Q(draft_reason="")
                )
                | (
                    Q(event__isnull=False)
                    & Q(drafted_from__isnull=False)
                    & Q(drafted_by__isnull=False)
                    & Q(drafted_at__isnull=False)
                    & ~Q(draft_reason__regex=r"^\s*$")
                ),
                name="source_identity_draft_traced",
            ),
        ]

    @property
    def external_id(self):
        return f"{self.sheet}:{self.pk}"

    def __str__(self):
        return self.external_id


class RowIdentityLink(UUIDModel):
    """Approved decision that a snapshot row describes a source identity."""

    row = models.OneToOneField("catalog.SheetRow", on_delete=models.PROTECT, related_name="identity_link")
    # Copy of row.snapshot so the database can refuse one identity twice in a snapshot.
    snapshot = models.ForeignKey("catalog.SheetSnapshot", on_delete=models.PROTECT, related_name="+")
    identity = models.ForeignKey("catalog.SourceIdentity", on_delete=models.PROTECT, related_name="links")
    match = models.CharField(
        max_length=16,
        choices=[
            ("new", "New identity"),
            ("exact_carry", "Unchanged content carried over"),
            ("reviewed_match", "Reviewed match"),
        ],
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()

    class Meta:
        verbose_name = _("verification")
        verbose_name_plural = _("verifications")
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "snapshot"], name="identity_once_per_snapshot"
            ),
            models.CheckConstraint(
                condition=~Q(reason__regex=r"^\s*$"), name="row_link_has_reason"
            ),
        ]

    def save(self, *args, **kwargs):
        # Guard writes that bypass catalog.crosswalk (shell, scripts).
        row = SheetRow.objects.select_related("snapshot").get(pk=self.row_id)
        identity = SourceIdentity.objects.get(pk=self.identity_id)
        if self.snapshot_id != row.snapshot_id:
            raise ValidationError("Link snapshot must be the row snapshot")
        if (identity.source_id, identity.sheet) != (row.snapshot.source_id, row.snapshot.sheet):
            raise ValidationError("Identity belongs to another source or sheet")
        super().save(*args, **kwargs)
