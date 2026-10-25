"""Invited volunteers may establish their own sign-in only while already authenticated."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase

from catalog.invitations import create_invitation

User = get_user_model()
URL = "/api/private/v1/credentials/"


class FirstLoginCredentialsTests(TestCase):
    def setUp(self):
        self.coordinator = User.objects.create_user(username="inviter", is_staff=True)
        self.coordinator.groups.add(Group.objects.get(name="Coordinator"))
        self.verify = Group.objects.get(name="Verify events")
        self.client = Client(enforce_csrf_checks=True)

    def csrf(self):
        return self.client.get("/api/csrf/").json()["csrfToken"]

    def invited(self):
        _, token = create_invitation(
            actor=self.coordinator, email="example-volunteer@example.org", groups=[self.verify]
        )
        first = self.client.post(
            "/api/private/v1/invitations/accept/",
            {"token": token},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf(),
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.user = User.objects.get(email="example-volunteer@example.org")
        return self.user

    def setup_password(
        self, value="Lighthouse#2026TeamCredential", *, confirmation=None, use_csrf=True
    ):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf()} if use_csrf else {}
        return self.client.post(
            URL,
            json.dumps(
                {
                    "password": value,
                    "confirmation": confirmation if confirmation is not None else value,
                }
            ),
            content_type="application/json",
            **headers,
        )

    def test_invited_person_sets_password_and_returns_after_sign_out(self):
        user = self.invited()
        self.assertFalse(user.has_usable_password())
        self.assertEqual(self.client.get(URL).json(), {"needs_setup": True})
        response = self.setup_password()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"needs_setup": False})
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password("Lighthouse#2026TeamCredential"))
        self.assertEqual(self.client.get(URL).json(), {"needs_setup": False})
        self.assertEqual(self.client.get("/api/private/v1/me/").status_code, 200)
        self.assertEqual(
            self.client.delete(
                "/api/private/v1/session/", HTTP_X_CSRFTOKEN=self.csrf()
            ).status_code,
            204,
        )
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/private/v1/session/",
                json.dumps(
                    {"username": user.username, "password": "Lighthouse#2026TeamCredential"}
                ),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=self.csrf(),
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/private/v1/me/").json()["username"], user.username)

    def test_password_setup_is_one_time(self):
        user = self.invited()
        self.assertEqual(self.setup_password().status_code, 200)
        self.assertEqual(self.setup_password("Another#SafeCredential2026").status_code, 409)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Lighthouse#2026TeamCredential"))

    def test_missing_csrf_and_weak_inputs_leave_credentials_unusable(self):
        user = self.invited()
        self.assertEqual(self.setup_password(use_csrf=False).status_code, 403)
        for value, confirmation in (
            ("12345", "12345"),
            ("123456789012", "123456789012"),
            ("Lighthouse#2026TeamCredential", "different"),
        ):
            response = self.setup_password(value, confirmation=confirmation)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(value, response.content.decode())
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    def test_anonymous_user_cannot_read_or_write(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.assertEqual(self.setup_password().status_code, 401)

    def test_privileged_groups_are_excluded(self):
        user = self.invited()
        for group in ("Publish events", "Coordinator"):
            assignment = Group.objects.get(name=group)
            user.groups.add(assignment)
            self.assertEqual(self.client.get(URL).json(), {"needs_setup": False})
            self.assertEqual(self.setup_password().status_code, 409)
            user.groups.remove(assignment)
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    def test_staff_and_individual_publish_permission_are_excluded(self):
        user = self.invited()
        user.user_permissions.add(Permission.objects.get(codename="publish_event"))
        self.assertEqual(self.client.get(URL).json(), {"needs_setup": False})
        self.assertEqual(self.setup_password().status_code, 409)
        user.user_permissions.clear()
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(URL).json(), {"needs_setup": False})
        self.assertEqual(self.setup_password().status_code, 409)

    def test_manual_passwordless_account_has_no_invitation_proof(self):
        manual = User.objects.create_user(username="manual-volunteer")
        manual.set_unusable_password()
        manual.save()
        self.client.force_login(manual)
        self.assertEqual(self.client.get(URL).json(), {"needs_setup": False})
        self.assertEqual(self.setup_password().status_code, 409)

    def test_get_is_never_cached(self):
        self.invited()
        self.assertEqual(self.client.get(URL)["Cache-Control"], "no-store")
