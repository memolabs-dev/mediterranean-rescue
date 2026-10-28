"""Prove model refactoring preserves Django registry and existing import contracts."""

from django.apps import apps
from django.test import SimpleTestCase

import catalog.api as api_compat
import catalog.imports as imports_compat
import catalog.services as publication_compat
from catalog import models
from catalog.ingestion.imports import apply_batch, normalize, stage_payload
from catalog.public_api.views import EventsView, exception_handler
from catalog.publication.services import set_publication


class DomainBoundaryTests(SimpleTestCase):
    def test_model_label_and_table_identity_remain_in_catalog(self):
        for name in models.__all__:
            if name in {"SHEETS", "EventKind", "EventQuerySet", "UUIDModel"}:
                continue
            model = getattr(models, name)
            self.assertIs(apps.get_model("catalog", name), model, name)
            self.assertEqual(model._meta.app_label, "catalog", name)
            self.assertEqual(model._meta.db_table, f"catalog_{name.lower()}", name)

    def test_related_models_resolve_across_domain_modules(self):
        self.assertIs(models.Event._meta.get_field("source").remote_field.model, models.Source)
        self.assertIs(models.Event._meta.get_field("port").remote_field.model, models.Port)
        self.assertIs(
            models.SourceIdentity._meta.get_field("event").remote_field.model, models.Event
        )
        self.assertIs(
            models.PublicationAudit._meta.get_field("event").remote_field.model,
            models.Event,
        )
        self.assertIs(
            models.PortAlias._meta.get_field("ports").remote_field.model,
            models.Port,
        )

    def test_legacy_import_paths_keep_the_same_functions(self):
        self.assertIs(api_compat.EventsView, EventsView)
        self.assertIs(api_compat.exception_handler, exception_handler)
        self.assertIs(imports_compat.stage_payload, stage_payload)
        self.assertIs(imports_compat.apply_batch, apply_batch)
        self.assertIs(imports_compat.normalize, normalize)
        self.assertIs(publication_compat.set_publication, set_publication)
