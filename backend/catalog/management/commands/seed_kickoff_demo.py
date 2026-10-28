"""Seed an isolated local training database with fictional kickoff events.

This command deliberately refuses production and non-training modes. It never fetches
network data, creates an externally usable login, or touches a real SOS source.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.imports import apply_batch, stage_payload
from catalog.models import Event, Source
from catalog.services import set_publication

FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/kickoff_synthetic_events.json"
SOURCE_KEY = "fictional-kickoff"
REVIEWER_NAME = "__fictional_kickoff_reviewer__"
PUBLISHED = ("fictional-rescue-001", "fictional-rescue-002")
LICENSE_NOTE = "Original fictional training dataset, authored for the independent kickoff demo."


class Command(BaseCommand):
    help = "Seed five fictional events and publish two for a local training-only demo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-local-training",
            action="store_true",
            help="Explicitly acknowledge that this must run in a disposable local training DB",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if (
            not options["confirm_local_training"]
            or not settings.DEBUG
            or settings.DATA_MODE != "training"
        ):
            raise CommandError(
                "Refused: requires --confirm-local-training, DEBUG=True and DATA_MODE=training"
            )

        source, _ = Source.objects.get_or_create(
            key=SOURCE_KEY,
            defaults={
                "name": "SYNTHETIC — kickoff training source",
                "url": "https://example.org/fictional/",
                "license_note": LICENSE_NOTE,
                "synthetic": True,
                "rights_approved": True,
            },
        )
        if (
            not source.synthetic
            or not source.rights_approved
            or source.license_note != LICENSE_NOTE
        ):
            raise CommandError("Source key already exists with incompatible metadata")

        user_model = get_user_model()
        reviewer, created = user_model.objects.get_or_create(
            username=REVIEWER_NAME,
            defaults={"is_active": True},
        )
        if not created and (
            reviewer.has_usable_password() or reviewer.is_superuser or reviewer.is_staff
        ):
            raise CommandError("Refused: demo reviewer username is occupied by an active login")
        if created:
            reviewer.set_unusable_password()
            reviewer.save(update_fields=["password"])
        permission = Permission.objects.get(
            content_type__app_label="catalog", codename="publish_event"
        )
        reviewer.user_permissions.add(permission)

        batch, _ = stage_payload(source=source, content=FIXTURES.read_bytes())
        created_drafts = apply_batch(batch_id=batch.pk)

        for external_id in PUBLISHED:
            event = Event.objects.get(source=source, external_id=external_id)
            if event.status == "draft":
                set_publication(
                    event_id=event.pk,
                    actor=reviewer,
                    publish=True,
                    reason="Fictional kickoff training preview, not real rescue data",
                )
            elif event.status != "published":
                raise CommandError("Demo event was withdrawn; refusing implicit republication")

        self.stdout.write(
            self.style.SUCCESS(
                f"TRAINING ONLY: drafts_created={created_drafts}; "
                f"events={Event.objects.filter(source=source).count()}; "
                f"public_training_events={Event.objects.public().filter(source=source).count()}; "
                "no real SOS MEDITERRANEE data loaded"
            )
        )
