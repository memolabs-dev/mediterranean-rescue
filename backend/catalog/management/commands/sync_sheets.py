"""Reads the configured Google Sheets tabs once, or every N seconds with --every (ADR 0012)."""

import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from catalog.ingestion.observability import safe_sync_observation
from catalog.sync import FetchRefused, check_config, sync_actor, sync_all


class Command(BaseCommand):
    help = "Read the Google Sheets exports and save new data privately; nothing is published."

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            default=settings.SHEETS_SYNC_CONFIG,
            help="JSON file: source key and tab URLs",
        )
        parser.add_argument("--every", type=int, default=0, help="Repeat every N seconds (0: once)")
        parser.add_argument("--json", dest="json_output", action="store_true", help="Privacy-safe JSON lines")

    def handle(self, *args, config, every, json_output=False, **options):
        if not config:
            raise CommandError("No sync configuration: set SHEETS_SYNC_CONFIG or pass --config.")
        settings_file = Path(config)
        if not settings_file.is_file():
            raise CommandError("The sync configuration file does not exist.")
        try:
            conf = json.loads(settings_file.read_text(encoding="utf-8"))
            check_config(conf)
            sync_actor()
        except (ValueError, FetchRefused) as exc:
            raise CommandError(str(exc)) from exc
        while True:
            # Between passes, drop a connection the database closed meanwhile.
            close_old_connections()
            try:
                runs = sync_all(conf)
            except Exception as exc:
                # The database or the account may come back: the loop keeps going.
                self.stderr.write(f"Reading skipped: {exc.__class__.__name__}")
                close_old_connections()
                runs = []
            if runs is None:
                self.stdout.write("Another reading is in progress; this pass is skipped.")
            for run in runs or []:
                # Status and counts only: source values never reach the logs.
                if json_output:
                    self.stdout.write(json.dumps(safe_sync_observation(run), sort_keys=True))
                else:
                    line = f"{run.sheet}: {run.status} {json.dumps(run.summary)} {run.message}"
                    self.stdout.write(line.rstrip())
            if every <= 0:
                return
            time.sleep(every)
