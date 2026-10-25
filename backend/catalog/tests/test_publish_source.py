"""Publishing a sheet that its owner already publishes (ADR 0016). Synthetic inputs, PostGIS."""

from io import StringIO

from django.contrib.auth.models import Permission
from django.core.management import CommandError, call_command

from catalog.logbook_sync import LOGBOOK_SOURCE_KEY
from catalog.models import Event, PublicationAudit, RowIdentityLink, Source
from catalog.tests.test_drafts import DraftTestCase
from catalog.tests.test_sheets import ops_csv, ops_row

REASON = "Rows already shown on the public CartONG map; decision of the project owner"


class PublishSourceTests(DraftTestCase):
    def setUp(self):
        super().setUp()
        self.reviewer.user_permissions.add(Permission.objects.get(codename="publish_event"))
        self.source.rights_approved = True
        self.source.license_note = "Synthetic fixture approved for tests"
        self.source.save()
        self.stage(
            ops_csv(
                ops_row(nb_survivor="42"),
                ops_row(date="04/02/2024", nb_survivor="-1"),  # in error: never published
            )
        )

    def run_command(self, *extra):
        out = StringIO()
        call_command(
            "publish_source", "--source", "fixture", "--actor", "reviewer",
            "--reason", REASON, *extra, stdout=out,
        )  # fmt: skip
        return out.getvalue()

    def test_without_apply_nothing_is_written(self):
        output = self.run_command()
        self.assertIn("Data_operations: 1 new, 1 blocked", output)
        self.assertIn("dry run: would publish 1", output)
        self.assertEqual(RowIdentityLink.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)

    def test_apply_links_drafts_and_publishes_under_the_named_person(self):
        output = self.run_command("--apply")
        self.assertIn("published 1", output)
        event = Event.objects.get()
        self.assertEqual((event.status, event.reviewed_by), ("published", self.reviewer))
        link = RowIdentityLink.objects.get()
        self.assertEqual(
            (link.match, link.approved_by, link.reason), ("new", self.reviewer, REASON)
        )
        audit = PublicationAudit.objects.get()
        self.assertEqual(
            (audit.action, audit.actor, audit.reason), ("published", self.reviewer, REASON)
        )
        # Replaying finds nothing more to do and publishes nothing twice.
        self.assertIn("published 0", self.run_command("--apply"))
        self.assertEqual(PublicationAudit.objects.count(), 1)

    def test_refused_without_the_source_agreement(self):
        Source.objects.filter(pk=self.source.pk).update(rights_approved=False, license_note="")
        with self.assertRaisesMessage(CommandError, "publication agreement"):
            self.run_command("--apply")
        self.assertEqual(RowIdentityLink.objects.count(), 0)

    def test_refused_without_the_publication_permission(self):
        self.reviewer.user_permissions.remove(Permission.objects.get(codename="publish_event"))
        with self.assertRaisesMessage(CommandError, "publish_event"):
            self.run_command("--apply")
        self.assertEqual(RowIdentityLink.objects.count(), 0)

    def test_the_logbook_is_never_published_in_bulk(self):
        Source.objects.create(key=LOGBOOK_SOURCE_KEY, name="Logbook", url="https://example.org/l")
        with self.assertRaisesMessage(CommandError, "one by one"):
            call_command(
                "publish_source", "--source", LOGBOOK_SOURCE_KEY, "--actor", "reviewer",
                "--reason", REASON, "--apply", stdout=StringIO(),
            )  # fmt: skip

    def test_rows_with_the_same_content_are_left_for_the_team(self):
        self.stage(
            ops_csv(
                ops_row(nb_survivor="42"),
                ops_row(nb_survivor="042"),
                ops_row(date="05/02/2024", nb_survivor="7"),
            )
        )
        output = self.run_command("--apply")
        self.assertIn("left for the team 2 same-content rows", output)
        self.assertIn("published 1", output)
        self.assertEqual(Event.objects.get().people, 7)
