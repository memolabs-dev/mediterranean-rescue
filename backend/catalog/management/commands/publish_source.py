from collections import Counter

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.crosswalk import approve_exact_carries, approve_link, propose_links
from catalog.drafts import EVENT_SHEETS, create_drafts
from catalog.logbook_sync import LOGBOOK_SOURCE_KEY
from catalog.models import SheetRow, SheetSnapshot, Source
from catalog.services import set_publication

PERMISSIONS = ("catalog.review_identity", "catalog.add_event", "catalog.publish_event")


class Command(BaseCommand):
    help = (
        "Publish the latest export of a sheet its owner already publishes (ADR 0016): every new "
        "row is linked, drafted and published under one named person and one reason. Rows in "
        "error, repeats and possible matches are left for the team space. Dry run unless --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--actor", required=True, help="username recorded on every decision")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        reason = options["reason"].strip()
        try:
            source = Source.objects.get(key=options["source"])
            actor = get_user_model().objects.get(username=options["actor"], is_active=True)
        except (Source.DoesNotExist, get_user_model().DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        if source.key == LOGBOOK_SOURCE_KEY:
            # Our own reading of a text, with doubts on half the rows: verified one by one.
            raise CommandError("Logbook rows are verified one by one in the team space")
        if not source.rights_approved:
            raise CommandError(f"{source.key} has no recorded publication agreement")
        missing = [p for p in PERMISSIONS if not actor.has_perm(p)]
        if missing:
            raise CommandError(f"{actor.username} lacks {', '.join(missing)}")
        if not reason:
            raise CommandError("A reason is required")

        snapshots = []
        for sheet in EVENT_SHEETS:
            latest = (
                SheetSnapshot.objects.filter(source=source, sheet=sheet)
                .order_by("-created_at", "-pk")
                .first()
            )
            if latest is not None:
                snapshots.append(latest)
        if not snapshots:
            raise CommandError(f"{source.key} has no staged export")

        published = 0
        try:
            with transaction.atomic():
                for snapshot in snapshots:
                    published += self.publish(snapshot, actor, reason)
                if not options["apply"]:
                    # The dry run goes through every step, then undoes it: its counts are exact.
                    transaction.set_rollback(True)
        except (PermissionDenied, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        if options["apply"]:
            self.stdout.write(f"published {published}")
        else:
            self.stdout.write(
                f"dry run: would publish {published}; nothing was written, add --apply to publish"
            )

    def publish(self, snapshot, actor, reason):
        proposals = propose_links(snapshot)
        counts = {}
        for proposal in proposals:
            counts[proposal.kind] = counts.get(proposal.kind, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: item[0] != "new")
        summary = ", ".join(f"{count} {kind}" for kind, count in ordered)
        self.stdout.write(f"{snapshot.sheet}: {summary}")
        approve_exact_carries(snapshot=snapshot, actor=actor, reason=reason)
        # Two rows with the same content but different unread cells are not flagged as repeats;
        # published both would show one operation twice. They wait for a person.
        fingerprints = dict(snapshot.rows.values_list("pk", "fingerprint"))
        seen = Counter(value for value in fingerprints.values() if value)
        twice = 0
        for proposal in proposals:
            if proposal.kind != "new":
                continue
            if seen[fingerprints[proposal.row_id]] > 1:
                twice += 1
                continue
            approve_link(row=SheetRow(pk=proposal.row_id), actor=actor, reason=reason)
        if twice:
            self.stdout.write(f"{snapshot.sheet}: left for the team {twice} same-content rows")
        result = create_drafts(snapshot=snapshot, actor=actor, reason=reason)
        skipped = {}
        for plan in result.skipped:
            skipped[plan.outcome] = skipped.get(plan.outcome, 0) + 1
        if skipped:
            self.stdout.write(
                f"{snapshot.sheet}: not drafted "
                + ", ".join(f"{count} {outcome}" for outcome, count in sorted(skipped.items()))
            )
        for _line, event_id in result.created:
            set_publication(event_id=event_id, actor=actor, publish=True, reason=reason)
        return len(result.created)
