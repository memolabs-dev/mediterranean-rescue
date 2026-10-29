"""Safety and repeatability checks for the local team account used by `make dev`."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

VOLUNTEER_ROLES = {"Verify events", "Prepare events", "Publish events", "Manual import"}


class SetupLocalTeamTests(TestCase):
    def run_setup(self):
        output = StringIO()
        call_command("setup_local_team", confirm_local_training=True, stdout=output)
        return output.getvalue()

    def test_refuses_without_confirmation_or_outside_local_training(self):
        with override_settings(DEBUG=True, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                call_command("setup_local_team", stdout=StringIO())

        with override_settings(DEBUG=False, DATA_MODE="training"):
            with self.assertRaises(CommandError):
                self.run_setup()

        with override_settings(DEBUG=True, DATA_MODE="production"):
            with self.assertRaises(CommandError):
                self.run_setup()

        self.assertFalse(get_user_model().objects.filter(username="local-team").exists())

    @override_settings(DEBUG=True, DATA_MODE="training")
    def test_creates_a_volunteer_account_without_password_or_admin_access(self):
        self.assertIn("local-team", self.run_setup())
        user = get_user_model().objects.get(username="local-team")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(set(user.groups.values_list("name", flat=True)), VOLUNTEER_ROLES)

        self.run_setup()
        self.assertEqual(get_user_model().objects.filter(username="local-team").count(), 1)

    @override_settings(DEBUG=True, DATA_MODE="training")
    def test_refuses_to_take_over_an_account_with_a_password_or_admin_access(self):
        model = get_user_model()
        model.objects.create_user(username="local-team", password="a-real-password-123")
        with self.assertRaises(CommandError):
            self.run_setup()

        model.objects.filter(username="local-team").update(password="!", is_staff=True)
        with self.assertRaises(CommandError):
            self.run_setup()
