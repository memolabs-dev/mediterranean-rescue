"""Volunteer roles, the coordinator's limited user administration, the reason asked before an
admin publication and the platform settings hardened after the Django audit (ADR 0013)."""

from django.conf import settings
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase

from catalog.models import Event, PublicationAudit, Source

User = get_user_model()


class RoleTests(TestCase):
    def test_each_role_is_a_group_with_exactly_its_permission(self):
        expected = {
            "Verify events": {"catalog.review_identity"},
            "Prepare events": {"catalog.add_event"},
            "Publish events": {"catalog.publish_event"},
            "Manual import": {"catalog.add_sheetsnapshot"},
            "Coordinator": {
                "auth.view_user",
                "auth.add_user",
                "auth.change_user",
                "auth.view_group",
                # Invitations by link (ADR 0015, migration 0011).
                "catalog.add_invitation",
                "catalog.view_invitation",
                "catalog.delete_invitation",
            },
        }
        for name, permissions in expected.items():
            group = Group.objects.get(name=name)
            found = {
                f"{permission.content_type.app_label}.{permission.codename}"
                for permission in group.permissions.select_related("content_type")
            }
            self.assertEqual(found, permissions, name)

    def test_a_volunteer_with_a_role_gets_its_permission(self):
        volunteer = User.objects.create_user(username="volunteer", password=None)
        volunteer.groups.add(Group.objects.get(name="Publish events"))
        volunteer = User.objects.get(pk=volunteer.pk)
        self.assertTrue(volunteer.has_perm("catalog.publish_event"))
        self.assertFalse(volunteer.has_perm("catalog.review_identity"))


class CoordinatorTests(TestCase):
    def setUp(self):
        self.coordinator = User.objects.create_user(
            username="coordinator", password=None, is_staff=True
        )
        self.coordinator.groups.add(Group.objects.get(name="Coordinator"))
        self.volunteer = User.objects.create_user(username="volunteer", password=None)
        self.lead = User.objects.create_superuser(username="lead", password=None)
        self.client = Client()
        self.client.force_login(self.coordinator)

    def test_sees_volunteers_only_and_cannot_open_staff_accounts(self):
        page = self.client.get("/admin/auth/user/")
        self.assertContains(page, "volunteer")
        self.assertNotContains(page, ">lead<")
        # A staff account is outside the coordinator's list: the admin answers as for a missing one.
        self.assertEqual(
            self.client.get(f"/admin/auth/user/{self.lead.pk}/change/").status_code, 302
        )

    def test_can_give_volunteer_roles_but_not_coordinator_or_staff(self):
        url = f"/admin/auth/user/{self.volunteer.pk}/change/"
        form = self.client.get(url)
        self.assertNotContains(form, 'name="is_staff"')
        self.assertNotContains(form, 'name="user_permissions"')
        verify = Group.objects.get(name="Verify events")
        coordinator = Group.objects.get(name="Coordinator")
        base = {
            "username": "volunteer",
            "first_name": "",
            "last_name": "",
            "email": "",
            "is_active": "on",
        }
        refused = self.client.post(url, {**base, "groups": [coordinator.pk], "is_staff": "on"})
        self.assertEqual(refused.status_code, 200)  # form shown again with the invalid choice
        self.assertFalse(User.objects.get(pk=self.volunteer.pk).groups.exists())
        saved = self.client.post(url, {**base, "groups": [verify.pk], "is_staff": "on"})
        self.assertEqual(saved.status_code, 302)
        volunteer = User.objects.get(pk=self.volunteer.pk)
        self.assertEqual(list(volunteer.groups.all()), [verify])
        self.assertFalse(volunteer.is_staff)

    def test_roles_are_named_in_the_readers_language(self):
        # Acceptance of 24 October 2026, D7: role names stayed English in the French admin.
        form = self.client.get(
            f"/admin/auth/user/{self.volunteer.pk}/change/", HTTP_ACCEPT_LANGUAGE="fr"
        )
        self.assertContains(form, "Vérifier les événements")
        self.assertNotContains(form, ">Verify events<")

    def test_cannot_take_over_someone_who_may_publish_through_a_permission(self):
        from django.contrib.auth.models import Permission

        self.volunteer.user_permissions.add(Permission.objects.get(codename="publish_event"))
        password = f"/admin/auth/user/{self.volunteer.pk}/password/"
        self.assertEqual(self.client.get(password).status_code, 403)

    def test_cannot_make_a_publisher_or_take_over_one(self):
        url = f"/admin/auth/user/{self.volunteer.pk}/change/"
        publish = Group.objects.get(name="Publish events")
        base = {
            "username": "volunteer",
            "first_name": "",
            "last_name": "",
            "email": "",
            "is_active": "on",
        }
        self.client.post(url, {**base, "groups": [publish.pk]})
        self.assertFalse(User.objects.get(pk=self.volunteer.pk).groups.exists())

        # A publisher given by a superuser keeps the role when the coordinator edits the account,
        # and their password is out of the coordinator's reach.
        self.volunteer.groups.add(publish)
        verify = Group.objects.get(name="Verify events")
        self.assertEqual(self.client.post(url, {**base, "groups": [verify.pk]}).status_code, 302)
        self.assertEqual(
            set(User.objects.get(pk=self.volunteer.pk).groups.values_list("name", flat=True)),
            {"Publish events", "Verify events"},
        )
        password = f"/admin/auth/user/{self.volunteer.pk}/password/"
        self.assertEqual(self.client.get(password).status_code, 403)


class AdminPublicationReasonTests(TestCase):
    def setUp(self):
        self.source = Source.objects.create(
            key="fixture",
            name="Fictitious source",
            url="https://example.org",
            synthetic=True,
            rights_approved=True,
            license_note="Fictitious licence for tests",
        )
        self.event = Event.objects.create(
            source=self.source,
            external_id="e1",
            kind="rescue",
            occurred_on="2024-02-03",
            title="Fictitious rescue",
            source_url="https://example.org/e1",
        )
        self.lead = User.objects.create_superuser(username="lead", password=None)
        self.client = Client()
        self.client.force_login(self.lead)

    def test_publishing_in_the_admin_asks_for_a_reason_and_records_it(self):
        action = {"action": "publish_reviewed", ACTION_CHECKBOX_NAME: [str(self.event.pk)]}
        asked = self.client.post("/admin/catalog/event/", action)
        self.assertContains(asked, 'name="reason"')
        self.assertEqual(Event.objects.get(pk=self.event.pk).status, "draft")
        empty = self.client.post("/admin/catalog/event/", {**action, "apply": "1", "reason": " "})
        self.assertContains(empty, 'name="reason"')
        self.client.post(
            "/admin/catalog/event/", {**action, "apply": "1", "reason": "Checked with SOS"}
        )
        self.assertEqual(Event.objects.get(pk=self.event.pk).status, "published")
        self.assertEqual(PublicationAudit.objects.get().reason, "Checked with SOS")


class ConstraintTests(TestCase):
    def test_the_licence_refusal_is_said_once_next_to_the_field(self):
        from django.core.exceptions import ValidationError

        source = Source(key="s", name="S", url="https://example.org", rights_approved=True)
        with self.assertRaises(ValidationError) as refused:
            source.full_clean()
        self.assertEqual(list(refused.exception.message_dict), ["license_note"])
        self.assertEqual(len(refused.exception.message_dict["license_note"]), 1)

    def test_the_database_refuses_what_the_forms_refuse(self):
        source = Source.objects.create(key="s", name="S", url="https://example.org")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Source.objects.filter(pk=source.pk).update(rights_approved=True, license_note=" ")
        base = {
            "source": source,
            "kind": "rescue",
            "occurred_on": "2024-02-03",
            "title": "Fictitious",
            "source_url": "https://example.org",
        }
        with self.assertRaises(IntegrityError), transaction.atomic():
            Event.objects.create(**{**base, "kind": "invented"}, external_id="a")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Event.objects.create(**base, external_id="b", location_precision="reported")


class PlatformSettingsTests(TestCase):
    def test_proxies_and_shared_cache(self):
        # X-Forwarded-For is ignored unless the deployment declares its proxies.
        self.assertEqual(settings.REST_FRAMEWORK["NUM_PROXIES"], 0)
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.db.DatabaseCache"
        )
        cache.set("probe", "value")
        self.assertEqual(cache.get("probe"), "value")
        self.assertTrue(settings.DATABASES["default"]["CONN_HEALTH_CHECKS"])

    def test_the_administration_speaks_french_when_asked(self):
        lead = User.objects.create_superuser(username="lead", password=None)
        client = Client(HTTP_ACCEPT_LANGUAGE="fr")
        client.force_login(lead)
        self.assertContains(client.get("/admin/"), "Administration de Mediterranean Rescue")
        english = Client(HTTP_ACCEPT_LANGUAGE="en")
        english.force_login(lead)
        self.assertContains(english.get("/admin/"), "Mediterranean Rescue administration")
        self.assertEqual(Permission.objects.filter(codename="publish_event").count(), 1)


class TransitionTests(TestCase):
    def test_the_service_refuses_a_decision_that_changes_nothing(self):
        from django.core.exceptions import ValidationError

        from catalog.services import set_publication

        source = Source.objects.create(
            key="t",
            name="T",
            url="https://example.org",
            rights_approved=True,
            license_note="Fictitious",
        )
        event = Event.objects.create(
            source=source,
            external_id="t1",
            kind="rescue",
            occurred_on="2024-02-03",
            title="Fictitious",
            source_url="https://example.org",
        )
        lead = User.objects.create_superuser(username="lead", password=None)
        with self.assertRaises(ValidationError) as withdrawn_draft:
            set_publication(event_id=event.pk, actor=lead, publish=False, reason="x")
        self.assertEqual(withdrawn_draft.exception.error_list[0].code, "invalid_transition")
        set_publication(event_id=event.pk, actor=lead, publish=True, reason="x")
        with self.assertRaises(ValidationError):
            set_publication(event_id=event.pk, actor=lead, publish=True, reason="again")
        self.assertEqual(PublicationAudit.objects.count(), 1)


class LocalAutoLoginTests(TestCase):
    def test_signs_in_the_local_account_only_when_it_exists_and_is_active(self):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.http import HttpResponse
        from django.test import RequestFactory, override_settings
        from rescue.middleware import LocalAutoLogin

        def run():
            request = RequestFactory().get("/api/private/v1/me/")
            SessionMiddleware(lambda r: HttpResponse()).process_request(request)
            request.user = AnonymousUser()
            LocalAutoLogin(lambda r: HttpResponse())(request)
            return request.user

        with override_settings(LOCAL_AUTO_LOGIN="local-team"):
            self.assertFalse(run().is_authenticated)
            User.objects.create_user(username="local-team", password=None, is_active=False)
            self.assertFalse(run().is_authenticated)
            User.objects.filter(username="local-team").update(is_active=True)
            self.assertEqual(run().username, "local-team")
            # Never an account that holds the admin (security audit of 25 October 2026).
            User.objects.filter(username="local-team").update(is_staff=True)
            self.assertFalse(run().is_authenticated)
            User.objects.filter(username="local-team").update(is_staff=False, is_superuser=True)
            self.assertFalse(run().is_authenticated)

    def test_a_sign_out_holds_in_this_browser_and_can_be_undone(self):
        # Guillaume, 25 October 2026: signing out did nothing, the next request signed in again.
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.http import HttpResponse
        from django.test import Client, RequestFactory, override_settings
        from rescue.middleware import LOCAL_AUTO_LOGIN_OFF, LocalAutoLogin

        User.objects.create_user(username="local-team", password=None)
        with override_settings(LOCAL_AUTO_LOGIN="local-team"):
            client = Client(enforce_csrf_checks=True)
            client.force_login(User.objects.get(username="local-team"))
            token = client.get("/api/csrf/").json()["csrfToken"]
            state = client.get("/api/private/v1/session/").json()
            self.assertEqual(state, {"signed_in": True, "local_auto_login": True})
            client.delete("/api/private/v1/session/", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(client.cookies[LOCAL_AUTO_LOGIN_OFF].value, "1")
            self.assertFalse(client.get("/api/private/v1/session/").json()["signed_in"])

            request = RequestFactory().get("/api/private/v1/me/")
            request.COOKIES[LOCAL_AUTO_LOGIN_OFF] = "1"
            SessionMiddleware(lambda r: HttpResponse()).process_request(request)
            request.user = AnonymousUser()
            LocalAutoLogin(lambda r: HttpResponse())(request)
            self.assertFalse(request.user.is_authenticated)

            token = client.get("/api/csrf/").json()["csrfToken"]
            resumed = client.put("/api/private/v1/session/", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(resumed.status_code, 200)
            self.assertEqual(resumed.json()["username"], "local-team")
            self.assertEqual(client.cookies[LOCAL_AUTO_LOGIN_OFF].value, "")
        # Without the local setting there is nothing to resume.
        self.assertEqual(Client().put("/api/private/v1/session/").status_code, 404)

    def test_production_settings_refuse_it(self):
        import os
        import subprocess
        import sys

        env = {**os.environ, "DJANGO_ENV": "production", "LOCAL_AUTO_LOGIN": "anyone"}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rescue.settings'); django.setup()",
            ],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LOCAL_AUTO_LOGIN is allowed only with DJANGO_ENV=development", result.stderr)
