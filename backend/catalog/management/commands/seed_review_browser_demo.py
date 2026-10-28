"""Seed a disposable *fictional* sheet and narrowly scoped test identities.

Never run on a public database. CI credentials are random, not printed or persisted.
This command is a browser-test fixture, not a way to onboard real volunteers.
"""

import csv
import io
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.crosswalk import stage_snapshot
from catalog.models import Source

SOURCE_KEY = "fictional-browser-review"
LICENSE_NOTE = "Fictional browser test fixtures only. No SOS MEDITERRANEE data or rights."
HEADER = (
    "date,type_ops,nb_ops,nb_survivor,male,female,under_18,under_18_unacc,under_5,"
    "pregnant_women,latitude,longitude,wind_force,wave_height,boat_type,"
    "nb_nationalities,type_nationalities,transfer_type,Port_disembarkation,"
    "image_src,video_srv,testimony_name,testimony_src"
)
USERS = {
    "fictional-ci-reviewer": ("review_identity", "add_sheetsnapshot"),
    "fictional-ci-publisher": ("add_event", "publish_event"),
    "fictional-ci-outsider": (),
}


class Command(BaseCommand):
    help = "Prepare one fictitious, reviewable sheet and disposable CI-only logins"

    def add_arguments(self, parser):
        parser.add_argument("--confirm-local-training", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if (
            not options["confirm_local_training"]
            or not settings.DEBUG
            or settings.DATA_MODE != "training"
        ):
            raise CommandError("Refused: requires explicit confirmation, DEBUG and training mode")
        password = os.environ.get("RESCUE_REVIEW_DEMO_PASSWORD", "")
        if len(password) < 24:
            raise CommandError("Set a random, >=24 character RESCUE_REVIEW_DEMO_PASSWORD")

        source, _ = Source.objects.get_or_create(
            key=SOURCE_KEY,
            defaults={
                "name": "FICTIONAL review browser fixture",
                "url": "https://example.org/fictional/review",
                "synthetic": True,
                "rights_approved": True,
                "license_note": LICENSE_NOTE,
            },
        )
        if (
            not source.synthetic
            or not source.rights_approved
            or source.license_note != LICENSE_NOTE
        ):
            raise CommandError("Refused: source key is used by incompatible data")

        users = {}
        model = get_user_model()
        for username, codenames in USERS.items():
            user, created = model.objects.get_or_create(
                username=username,
                defaults={"is_active": True},
            )
            if not created and (
                user.is_staff or user.is_superuser or not user.is_active
            ):
                raise CommandError("Refused: a reserved test username is occupied")
            user.set_password(password)
            user.save(update_fields=["password"])
            user.user_permissions.set(
                Permission.objects.filter(
                    content_type__app_label="catalog", codename__in=codenames
                )
            )
            users[username] = user

        values = {
            "date": "12/01/2026",
            "type_ops": "Rescue",
            "nb_survivor": "7",
            "latitude": "35.2",
            "longitude": "12.4",
        }
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=HEADER.split(","))
        writer.writeheader()
        writer.writerow(values)
        snapshot, _ = stage_snapshot(
            source=source,
            sheet="Data_operations",
            content=out.getvalue().encode("utf-8"),
            actor=users["fictional-ci-reviewer"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"FICTIONAL ONLY: source={SOURCE_KEY}, "
                f"reviewable_rows={snapshot.rows.count()}, no real SOS records"
            )
        )
