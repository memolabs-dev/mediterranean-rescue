"""Create the volunteer account that LOCAL_AUTO_LOGIN signs in on a contributor's laptop.

This command deliberately refuses production and non-training modes. The account has the
volunteer roles but no password, no administration access and no superuser rights.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

USERNAME = "local-team"
ROLES = ("Verify events", "Prepare events", "Publish events", "Manual import")


class Command(BaseCommand):
    help = "Create the password-less local volunteer account used by LOCAL_AUTO_LOGIN"

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

        user, created = get_user_model().objects.get_or_create(
            username=USERNAME, defaults={"is_active": True}
        )
        if not created and (user.has_usable_password() or user.is_staff or user.is_superuser):
            raise CommandError(f"Refused: {USERNAME} is already a real login")
        if not user.is_active:
            # LOCAL_AUTO_LOGIN never signs in an inactive account: say so instead of a silent no-op.
            raise CommandError(f"Refused: {USERNAME} was deactivated; reactivate it on purpose")
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        user.groups.set(Group.objects.filter(name__in=ROLES))

        self.stdout.write(
            self.style.SUCCESS(
                f"TRAINING ONLY: {USERNAME} has the volunteer roles, no password, no admin access"
            )
        )
