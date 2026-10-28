from django.conf import settings
from django.contrib.gis.db import models
from django.utils.translation import gettext_lazy as _


class PublicationAudit(models.Model):
    event = models.ForeignKey("catalog.Event", on_delete=models.PROTECT, related_name="audit")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_("decided by")
    )
    action = models.CharField(_("decision"), max_length=20)
    reason = models.TextField(_("reason"))
    snapshot = models.JSONField(_("event as decided"))
    created_at = models.DateTimeField(_("decided at"), auto_now_add=True)

    class Meta:
        verbose_name = _("publication decision")
        verbose_name_plural = _("publication decisions")

    def __str__(self):
        return f"{self.action} · {self.event} · {self.created_at:%Y-%m-%d}"
