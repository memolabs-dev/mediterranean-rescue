"""Invitations by single-use link (ADR 0015): a coordinator invites a volunteer by email, with
roles; the link signs them in without a password, once, within 72 hours. Fictitious accounts."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.utils import timezone

from catalog.invitations import TOKEN_TTL, create_invitation
from catalog.models import Invitation

User = get_user_model()


class InvitationTestCase(TestCase):
    def setUp(self):
        self.coordinator = User.objects.create_user(
            username="coordinator", password=None, is_staff=True
        )
        self.coordinator.groups.add(Group.objects.get(name="Coordinator"))
        self.verify = Group.objects.get(name="Verify events")
        self.publish = Group.objects.get(name="Publish events")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.coordinator)
        self.token = self.client.get("/api/csrf/").json()["csrfToken"]

    def post(self, path, body, client=None, token=None):
        client = client or self.client
        return client.post(
            f"/api/private/v1/{path}",
            body,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token or self.token,
        )

    def visitor(self):
        client = Client(enforce_csrf_checks=True)
        return client, client.get("/api/csrf/").json()["csrfToken"]


class CreateTests(InvitationTestCase):
    def test_a_coordinator_invites_with_volunteer_roles_and_gets_the_link_once(self):
        response = self.post(
            "invitations/", {"email": "Volunteer@Example.org", "roles": [self.verify.pk]}
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertGreaterEqual(len(body["token"]), 40)
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.email, "volunteer@example.org")
        # Only a hash is kept: the database never holds a usable link.
        self.assertNotEqual(invitation.token_hash, body["token"])
        self.assertNotIn(body["token"], str(self.client.get("/api/private/v1/invitations/").json()))
        self.assertAlmostEqual(
            invitation.expires_at, timezone.now() + TOKEN_TTL, delta=timedelta(minutes=1)
        )

    def test_a_coordinator_cannot_hand_out_publishing_or_coordination(self):
        response = self.post("invitations/", {"email": "x@example.org", "roles": [self.publish.pk]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "role_not_allowed")
        self.assertFalse(Invitation.objects.exists())

    def test_nobody_without_the_right_invites(self):
        volunteer = User.objects.create_user(username="volunteer", password=None)
        volunteer.groups.add(self.verify)
        client = Client(enforce_csrf_checks=True)
        client.force_login(volunteer)
        token = client.get("/api/csrf/").json()["csrfToken"]
        response = self.post("invitations/", {"email": "x@example.org", "roles": []}, client, token)
        self.assertEqual(response.status_code, 403)

    def test_no_link_signs_in_an_account_that_holds_the_admin(self):
        User.objects.create_user(username="lead", email="lead@example.org", is_staff=True)
        response = self.post("invitations/", {"email": "lead@example.org", "roles": []})
        # Same answer as for any address: a coordinator learns nothing about admin accounts...
        self.assertEqual(response.status_code, 201)
        client, csrf = self.visitor()
        accepted = self.post(
            "invitations/accept/", {"token": response.json()["token"]}, client, csrf
        )
        # ...and the link never opens that account.
        self.assertEqual(accepted.status_code, 409)
        self.assertEqual(client.get("/api/private/v1/me/").status_code, 401)


class AcceptTests(InvitationTestCase):
    def invite(self, email="new@example.org", roles=None):
        _, token = create_invitation(
            actor=self.coordinator,
            email=email,
            groups=roles if roles is not None else [self.verify],
        )
        return token

    def test_the_link_creates_the_account_signs_in_once_and_never_again(self):
        token = self.invite()
        client, csrf = self.visitor()
        check = self.post("invitations/check/", {"token": token}, client, csrf)
        self.assertEqual(check.status_code, 200)
        self.assertEqual(check.json()["invited_by"], "coordinator")
        self.assertEqual(check.json()["roles"], ["verify"])
        # Reading the invitation changes nothing: a mail scanner opening the link uses nothing up.
        self.assertIsNone(Invitation.objects.get().used_at)
        accepted = self.post("invitations/accept/", {"token": token}, client, csrf)
        self.assertEqual(accepted.status_code, 200)
        user = User.objects.get(email="new@example.org")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(list(user.groups.all()), [self.verify])
        self.assertEqual(client.get("/api/private/v1/me/").json()["username"], user.username)
        again, csrf = self.visitor()
        reused = self.post("invitations/accept/", {"token": token}, again, csrf)
        self.assertEqual(reused.status_code, 409)
        self.assertEqual(reused.json()["code"], "invitation_unusable")

    def test_a_second_invitation_restores_an_existing_volunteers_session(self):
        first = self.invite(email="return@example.org")
        visitor, token = self.visitor()
        accepted = self.post("invitations/accept/", {"token": first}, visitor, token)
        self.assertEqual(accepted.status_code, 200)
        user = User.objects.get(email="return@example.org")
        self.assertFalse(user.has_usable_password())
        csrf = visitor.get("/api/csrf/").json()["csrfToken"]
        self.assertEqual(
            visitor.delete("/api/private/v1/session/", HTTP_X_CSRFTOKEN=csrf).status_code, 204
        )
        self.assertEqual(visitor.get("/api/private/v1/me/").status_code, 401)

        # An authorized staff coordinator can issue a new, independent single-use link.
        second = self.invite(email="RETURN@example.org")
        self.assertNotEqual(first, second)
        old, old_csrf = self.visitor()
        self.assertEqual(
            self.post("invitations/accept/", {"token": first}, old, old_csrf).status_code,
            409,
        )
        again, fresh_csrf = self.visitor()
        self.assertEqual(
            self.post("invitations/accept/", {"token": second}, again, fresh_csrf).status_code,
            200,
        )
        self.assertEqual(again.get("/api/private/v1/me/").json()["username"], user.username)
        self.assertEqual(User.objects.filter(email__iexact="return@example.org").count(), 1)
        self.assertEqual(
            self.post("invitations/accept/", {"token": second}, old, old_csrf).status_code,
            409,
        )

    def test_an_existing_volunteer_is_signed_in_and_keeps_their_account(self):
        volunteer = User.objects.create_user(username="ana", email="ana@example.org", password=None)
        token = self.invite(email="ANA@example.org", roles=[])
        client, csrf = self.visitor()
        self.assertEqual(
            self.post("invitations/accept/", {"token": token}, client, csrf).status_code, 200
        )
        self.assertEqual(client.get("/api/private/v1/me/").json()["username"], "ana")
        self.assertEqual(User.objects.filter(email__iexact="ana@example.org").count(), 1)
        self.assertEqual(Invitation.objects.get().used_by, volunteer)

    def test_expired_revoked_or_made_up_links_say_the_same_thing(self):
        expired = self.invite(email="a@example.org")
        Invitation.objects.filter(email="a@example.org").update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        revoked = self.invite(email="b@example.org")
        invitation = Invitation.objects.get(email="b@example.org")
        delete = self.client.delete(
            f"/api/private/v1/invitations/{invitation.pk}/", HTTP_X_CSRFTOKEN=self.token
        )
        self.assertEqual(delete.status_code, 204)
        for token in (expired, revoked, "made-up-" + "x" * 40):
            client, csrf = self.visitor()
            response = self.post("invitations/accept/", {"token": token}, client, csrf)
            self.assertEqual(response.status_code, 409, token)
            self.assertEqual(response.json()["code"], "invitation_unusable")
            self.assertEqual(client.get("/api/private/v1/me/").status_code, 401)

    def test_an_account_made_staff_after_the_invitation_is_not_signed_in(self):
        token = self.invite(email="later@example.org")
        User.objects.create_user(username="later", email="later@example.org", is_superuser=True)
        client, csrf = self.visitor()
        response = self.post("invitations/accept/", {"token": token}, client, csrf)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(client.get("/api/private/v1/me/").status_code, 401)

    def test_accepting_needs_the_csrf_token(self):
        token = self.invite()
        response = Client(enforce_csrf_checks=True).post(
            "/api/private/v1/invitations/accept/", {"token": token}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(Invitation.objects.get().used_at)


class TakeoverTests(InvitationTestCase):
    """Security review of 25 October 2026: a coordinator must not open a publisher's session,
    which the admin forbids (only a superuser resets a publisher's password)."""

    def accept_as_visitor(self, token):
        client, csrf = self.visitor()
        response = self.post("invitations/accept/", {"token": token}, client, csrf)
        return response, client

    def test_a_coordinator_cannot_open_a_publishers_account(self):
        publisher = User.objects.create_user(username="pub", email="pub@example.org")
        publisher.groups.add(self.publish)
        _, token = create_invitation(actor=self.coordinator, email="pub@example.org", groups=[])
        response, client = self.accept_as_visitor(token)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(client.get("/api/private/v1/me/").status_code, 401)

    def test_nor_one_who_may_publish_through_a_permission(self):
        from django.contrib.auth.models import Permission

        holder = User.objects.create_user(username="holder", email="holder@example.org")
        holder.user_permissions.add(Permission.objects.get(codename="publish_event"))
        _, token = create_invitation(actor=self.coordinator, email="holder@example.org", groups=[])
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_nor_another_coordinator(self):
        other = User.objects.create_user(username="other", email="other@example.org")
        other.groups.add(Group.objects.get(name="Coordinator"))
        _, token = create_invitation(actor=self.coordinator, email="other@example.org", groups=[])
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_a_superusers_link_may_open_a_publishers_account(self):
        superuser = User.objects.create_user(username="root", password=None, is_superuser=True)
        publisher = User.objects.create_user(username="pub", email="pub@example.org")
        publisher.groups.add(self.publish)
        _, token = create_invitation(actor=superuser, email="pub@example.org", groups=[])
        response, client = self.accept_as_visitor(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/private/v1/me/").json()["username"], "pub")

    def test_an_address_moved_onto_another_account_after_the_link_opens_nothing(self):
        # The link was made for a new address; a publisher's email is then set to it.
        _, token = create_invitation(actor=self.coordinator, email="fresh@example.org", groups=[])
        publisher = User.objects.create_user(username="pub", email="pub@example.org")
        publisher.groups.add(self.publish)
        publisher.email = "fresh@example.org"
        publisher.save()
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_an_account_whose_address_changed_is_not_opened_by_its_old_link(self):
        volunteer = User.objects.create_user(username="ana", email="ana@example.org")
        _, token = create_invitation(actor=self.coordinator, email="ana@example.org", groups=[])
        volunteer.email = "ana.new@example.org"
        volunteer.save()
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_a_link_dies_with_its_creators_right_to_invite(self):
        _, token = create_invitation(actor=self.coordinator, email="new@example.org", groups=[])
        self.coordinator.is_active = False
        self.coordinator.save()
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)
        self.assertFalse(User.objects.filter(email="new@example.org").exists())

    def test_a_role_given_before_the_link_is_used_is_seen(self):
        volunteer = User.objects.create_user(username="ana", email="ana@example.org")
        _, token = create_invitation(actor=self.coordinator, email="ana@example.org", groups=[])
        volunteer.groups.add(self.publish)
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_two_accounts_sharing_an_address_are_never_chosen_between(self):
        User.objects.create_user(username="a1", email="twin@example.org")
        User.objects.create_user(username="a2", email="TWIN@example.org")
        _, token = create_invitation(actor=self.coordinator, email="twin@example.org", groups=[])
        self.assertEqual(self.accept_as_visitor(token)[0].status_code, 409)

    def test_a_coordinator_without_the_admin_only_creates_new_accounts(self):
        coordinator = User.objects.create_user(username="field", password=None)
        coordinator.groups.add(Group.objects.get(name="Coordinator"))
        User.objects.create_user(username="ana", email="ana@example.org")
        _, existing = create_invitation(actor=coordinator, email="ana@example.org", groups=[])
        self.assertEqual(self.accept_as_visitor(existing)[0].status_code, 409)
        _, new = create_invitation(actor=coordinator, email="new@example.org", groups=[self.verify])
        self.assertEqual(self.accept_as_visitor(new)[0].status_code, 200)
