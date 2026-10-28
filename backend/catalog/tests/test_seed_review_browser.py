"""Security and determinism of the disposable authenticated browser fixture."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.models import SheetSnapshot, Source

PASSWORD = "fictional-test-account-password-not-live"


class SeedReviewBrowserTests(TestCase):
    def command(self):
        call_command("seed_review_browser", confirm_local_training=True, stdout=StringIO())

    def test_refuses_production_and_missing_password(self):
        with override_settings(DEBUG=True, DATA_MODE="training"):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaises(CommandError):
                    self.command()
        with patch.dict("os.environ", {"KICKOFF_REVIEW_PASSWORD": PASSWORD}):
            with override_settings(DEBUG=False, DATA_MODE="training"):
                with self.assertRaises(CommandError):
                    self.command()
            with override_settings(DEBUG=True, DATA_MODE="production"):
                with self.assertRaises(CommandError):
                    self.command()
        self.assertFalse(Source.objects.exists())

    @override_settings(DEBUG=True, DATA_MODE="training")
    def test_roles_and_one_fictional_snapshot_are_repeatable(self):
        with patch.dict("os.environ", {"KICKOFF_REVIEW_PASSWORD": PASSWORD}):
            self.command()
            self.command()
        model = get_user_model()
        reviewer = model.objects.get(username="__fictional_review_browser__")
        publisher = model.objects.get(username="__fictional_publish_browser__")
        self.assertFalse(reviewer.is_staff)
        self.assertTrue(reviewer.check_password(PASSWORD))
        self.assertTrue(reviewer.has_perm("catalog.review_identity"))
        self.assertTrue(reviewer.has_perm("catalog.add_sheetsnapshot"))
        self.assertFalse(reviewer.has_perm("catalog.publish_event"))
        self.assertTrue(publisher.has_perm("catalog.publish_event"))
        self.assertTrue(publisher.has_perm("catalog.add_event"))
        self.assertFalse(publisher.has_perm("catalog.review_identity"))
        snapshot = SheetSnapshot.objects.get(source__key="fictional-review-browser")
        self.assertEqual(snapshot.row_count, 1)
        self.assertTrue(snapshot.source.synthetic)
        self.assertEqual(snapshot.rows.get().candidate["occurred_on"], "2026-01-17")
