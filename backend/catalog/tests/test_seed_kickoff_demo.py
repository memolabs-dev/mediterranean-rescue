"""Safety and repeatability checks for the local synthetic walkthrough command."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.models import Event, PublicationAudit, Source


class SeedKickoffDemoTests(TestCase):
    def run_demo(self):
        output = StringIO()
        call_command("seed_kickoff_demo", confirm_local_training=True, stdout=output)
        self.assertIn("TRAINING ONLY", output.getvalue())

    def test_refuses_without_confirmation_or_in_production(self):
        with override_settings(DEBUG=True, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                call_command("seed_kickoff_demo", stdout=StringIO())

        with override_settings(DEBUG=False, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                self.run_demo()

        with override_settings(DEBUG=True, DATA_MODE="production"):
            with self.assertRaises(CommandError):
                self.run_demo()

        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)

    @override_settings(DEBUG=True, DATA_MODE="training")
    def test_seed_is_idempotent_and_separated_from_production(self):
        self.run_demo()
        source = Source.objects.get(key="fictional-kickoff")
        self.assertTrue(source.synthetic)
        self.assertEqual(Event.objects.filter(source=source).count(), 5)
        self.assertEqual(Event.objects.public().filter(source=source).count(), 2)
        self.assertEqual(PublicationAudit.objects.count(), 2)

        # Two published records: one cartographic point, and one missing its location.
        self.assertEqual(self.client.get("/api/v1/events/", secure=True).json()["total_count"], 2)
        self.assertEqual(
            self.client.get("/api/v1/map-points/", secure=True).json()["located_count"], 1
        )
        unknown = Event.objects.get(source=source, external_id="fictional-rescue-002")
        self.assertIsNone(unknown.people)
        self.assertIsNone(unknown.location)

        self.run_demo()
        self.assertEqual(Event.objects.count(), 5)
        self.assertEqual(PublicationAudit.objects.count(), 2)

        with override_settings(DATA_MODE="production"):
            self.assertEqual(
                self.client.get("/api/v1/events/", secure=True).json()["total_count"], 0
            )
