"""End-to-end data-contract checks for the independent DfG kickoff prototype.

These five records are intentionally fictional. The tests use the real Django/PostGIS
models, import services, publication audit and public HTTP API; no live SOS data or
network access is used.
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from catalog.imports import apply_batch, stage_payload
from catalog.models import Event, ImportBatch, PublicationAudit, Source, StagedRecord
from catalog.services import set_publication

FIXTURES = Path(__file__).parent / "fixtures" / "kickoff_synthetic_events.json"


@override_settings(DATA_MODE="training")
class KickoffVerticalSliceTests(TestCase):
    """A reproducible five-event exercise against the actual application boundaries."""

    @classmethod
    def setUpTestData(cls):
        cls.source = Source.objects.create(
            key="fictional-kickoff",
            name="SYNTHETIC — kickoff training source",
            url="https://example.org/fictional/",
            synthetic=True,
            rights_approved=True,
            license_note="Fictional records authored specifically for this automated test.",
        )
        user_model = get_user_model()
        cls.editor = user_model.objects.create_user(username="kickoff-reviewer")
        cls.visitor = user_model.objects.create_user(username="kickoff-no-permission")
        permission = Permission.objects.get(
            content_type__app_label="catalog", codename="publish_event"
        )
        cls.editor.user_permissions.add(permission)

    def rows(self):
        return json.loads(FIXTURES.read_text(encoding="utf-8"))

    def stage_and_apply(self):
        content = FIXTURES.read_bytes()
        batch, created = stage_payload(source=self.source, content=content)
        self.assertTrue(created)
        self.assertEqual(apply_batch(batch_id=batch.pk), 5)
        return batch

    def publish(self, external_id):
        event = Event.objects.get(source=self.source, external_id=external_id)
        return set_publication(
            event_id=event.pk, actor=self.editor, publish=True, reason="Synthetic QA review"
        )

    def test_import_remains_private_until_review_and_is_idempotent(self):
        payload = FIXTURES.read_bytes()
        batch, created = stage_payload(source=self.source, content=payload)
        self.assertTrue(created)
        self.assertEqual(StagedRecord.objects.filter(batch=batch).count(), 5)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(self.client.get("/api/v1/events/", secure=True).json()["total_count"], 0)

        same_batch, created_again = stage_payload(source=self.source, content=payload)
        self.assertFalse(created_again)
        self.assertEqual(same_batch.pk, batch.pk)
        self.assertEqual(ImportBatch.objects.count(), 1)

        self.assertEqual(apply_batch(batch_id=batch.pk), 5)
        self.assertEqual(apply_batch(batch_id=batch.pk), 0)
        self.assertEqual(Event.objects.filter(status="draft").count(), 5)
        self.assertEqual(self.client.get("/api/v1/events/", secure=True).json()["total_count"], 0)

    def test_unknowns_are_not_invented_and_map_has_no_ghost_pin(self):
        self.stage_and_apply()
        event = self.publish("fictional-rescue-002")
        self.assertIsNone(event.people)
        self.assertIsNone(event.location)
        self.assertEqual(event.location_precision, "unknown")

        feed = self.client.get("/api/v1/events/", secure=True)
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json()["total_count"], 1)
        self.assertIsNone(feed.json()["items"][0]["people"])
        self.assertIsNone(feed.json()["items"][0]["position"])

        points = self.client.get("/api/v1/map-points/", secure=True)
        self.assertEqual(points.status_code, 200)
        self.assertEqual(points.json()["points"], [])
        self.assertEqual(points.json()["located_count"], 0)

    def test_publishing_requires_both_permission_and_approved_rights(self):
        self.stage_and_apply()
        event = Event.objects.get(external_id="fictional-rescue-001")

        with self.assertRaises(PermissionDenied):
            set_publication(
                event_id=event.pk, actor=self.visitor, publish=True, reason="Not authorized"
            )
        self.source.rights_approved = False
        self.source.save(update_fields=["rights_approved"])
        with self.assertRaises(ValidationError):
            set_publication(
                event_id=event.pk, actor=self.editor, publish=True, reason="Not licensed"
            )
        event.refresh_from_db()
        self.assertEqual(event.status, "draft")
        self.assertFalse(PublicationAudit.objects.exists())

    def test_conflicting_identity_or_coordinates_cannot_be_silently_imported(self):
        rows = self.rows()
        conflict = dict(rows[0], latitude=36.1)
        with self.assertRaises(ValidationError):
            stage_payload(
                source=self.source,
                content=json.dumps([rows[0], conflict]).encode("utf-8"),
            )
        missing_coordinate = dict(rows[0], longitude=None)
        with self.assertRaises(ValidationError):
            stage_payload(
                source=self.source,
                content=json.dumps([missing_coordinate]).encode("utf-8"),
            )
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(Event.objects.exists())

    def test_reimport_cannot_overwrite_an_existing_event(self):
        self.stage_and_apply()
        original = Event.objects.get(external_id="fictional-rescue-001")
        rows = self.rows()
        changed = dict(rows[0], people=99)
        batch, created = stage_payload(
            source=self.source, content=json.dumps([changed]).encode("utf-8")
        )
        self.assertTrue(created)
        with self.assertRaises(ValidationError):
            apply_batch(batch_id=batch.pk)
        original.refresh_from_db()
        self.assertEqual(original.people, 18)
        self.assertEqual(Event.objects.count(), 5)

    def test_withdrawal_removes_the_public_event_and_keeps_audit(self):
        self.stage_and_apply()
        event = self.publish("fictional-rescue-001")
        self.assertEqual(self.client.get("/api/v1/events/", secure=True).json()["total_count"], 1)
        self.assertEqual(
            self.client.get("/api/v1/map-points/", secure=True).json()["located_count"], 1
        )

        set_publication(
            event_id=event.pk, actor=self.editor, publish=False, reason="Synthetic QA withdrawal"
        )
        self.assertEqual(self.client.get("/api/v1/events/", secure=True).json()["total_count"], 0)
        self.assertEqual(
            self.client.get("/api/v1/map-points/", secure=True).json()["located_count"], 0
        )
        self.assertEqual(
            list(PublicationAudit.objects.filter(event=event).values_list("action", flat=True)),
            ["published", "withdrawn"],
        )

    @override_settings(DATA_MODE="production")
    def test_production_api_never_exposes_training_records(self):
        self.stage_and_apply()
        self.publish("fictional-rescue-001")
        response = self.client.get("/api/v1/events/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_count"], 0)
