"""The browser fixture must be safe even if someone tries it on a production DB."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.models import Event, SheetSnapshot, Source


class ReviewBrowserDemoSeedTests(TestCase):
    def seed(self):
        with patch.dict("os.environ", {"RESCUE_REVIEW_DEMO_PASSWORD": "fictional-" + "X" * 32}):
            call_command("seed_review_browser_demo", confirm_local_training=True, stdout=StringIO())

    def test_refuses_production_or_missing_confirmation(self):
        with override_settings(DEBUG=False, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                self.seed()
        with override_settings(DEBUG=True, DATA_MODE="production"):
            with self.assertRaises(CommandError):
                self.seed()
        with override_settings(DEBUG=True, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                call_command("seed_review_browser_demo", stdout=StringIO())
        self.assertFalse(Source.objects.exists())

    @override_settings(DEBUG=True, DATA_MODE="training")
    def test_synthetic_fixture_permissions_and_repeated_seed(self):
        self.seed()
        source = Source.objects.get(key="fictional-browser-review")
        self.assertTrue(source.synthetic)
        self.assertEqual(source.url, "https://example.org/fictional/review")
        self.assertEqual(SheetSnapshot.objects.filter(source=source).count(), 1)
        self.assertEqual(SheetSnapshot.objects.get(source=source).rows.count(), 1)
        self.assertFalse(Event.objects.exists())

        user_model = get_user_model()
        reviewer = user_model.objects.get(username="fictional-ci-reviewer")
        publisher = user_model.objects.get(username="fictional-ci-publisher")
        outsider = user_model.objects.get(username="fictional-ci-outsider")
        self.assertTrue(reviewer.has_perm("catalog.review_identity"))
        self.assertFalse(reviewer.has_perm("catalog.publish_event"))
        self.assertTrue(publisher.has_perm("catalog.publish_event"))
        self.assertFalse(publisher.has_perm("catalog.review_identity"))
        self.assertFalse(outsider.has_perm("catalog.review_identity"))

        self.seed()
        self.assertEqual(SheetSnapshot.objects.filter(source=source).count(), 1)
