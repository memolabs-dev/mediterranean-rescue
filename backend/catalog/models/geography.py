from django.conf import settings
from django.contrib.gis.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .base import UUIDModel


class Port(UUIDModel):
    name = models.CharField(_("name"), max_length=200)
    country_code = models.CharField(_("country code"), max_length=2, blank=True)
    location = models.PointField(_("position"), srid=4326, null=True, blank=True)
    # Whether the location was taken from the source row (format kept on that row) or typed
    # by the reviewer; empty for ports created before the crosswalk.
    location_source = models.CharField(
        max_length=16,
        blank=True,
        choices=[("sheet_row", "Source row"), ("reviewer", "Reviewer")],
    )
    # Data_ports row the port was approved from, when it came from a Sheets snapshot.
    created_from = models.ForeignKey(
        "SheetRow", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        verbose_name = _("port")
        verbose_name_plural = _("ports")

    def __str__(self):
        return self.name


class PortAlias(UUIDModel):
    """Approved reading of an exact source port label.

    Port_disembarkation holds ports, but also several ports at once, transfer vessels and
    regions: a label maps to one or more ports, to a vessel, or is classified as not a port.
    """

    source = models.ForeignKey(
        "catalog.Source", on_delete=models.PROTECT, related_name="port_aliases"
    )
    label = models.CharField(max_length=200)
    target = models.CharField(
        max_length=16,
        choices=[
            ("ports", "One or more ports"),
            ("vessel", "A vessel (transfer)"),
            ("not_a_port", "Not a port (region or unknown)"),
        ],
    )
    ports = models.ManyToManyField(
        "catalog.Port", blank=True, related_name="aliases", through="PortAliasPort"
    )
    vessel = models.ForeignKey(
        "catalog.Vessel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="port_aliases",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()

    class Meta:
        verbose_name = _("port name reading")
        verbose_name_plural = _("port name readings")
        constraints = [
            models.UniqueConstraint(fields=["source", "label"], name="port_alias_per_source"),
            models.CheckConstraint(
                condition=~Q(reason__regex=r"^\s*$"), name="port_alias_has_reason"
            ),
            models.CheckConstraint(
                condition=(Q(target="vessel") & Q(vessel__isnull=False))
                | (~Q(target="vessel") & Q(vessel__isnull=True)),
                name="port_alias_vessel_target",
            ),
        ]

    def __str__(self):
        return f"{self.label} ({self.target})"


class PortAliasPort(models.Model):
    # Explicit through table: deleting a port never silently empties an approved reading.
    alias = models.ForeignKey("catalog.PortAlias", on_delete=models.CASCADE)
    port = models.ForeignKey("catalog.Port", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["alias", "port"], name="port_alias_port_once")
        ]
