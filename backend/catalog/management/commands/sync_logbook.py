"""Reads the SOS MEDITERRANEE public logbook once, or every N seconds with --every (ADR 0014)."""

import json
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from catalog.ingestion.observability import safe_sync_observation
from catalog.logbook_sync import sync_logbook


class Command(BaseCommand):
    help = "Rebuild the operations missing from the sheet from the public logbook, privately."

    def add_arguments(self, parser):
        # About 45 pages per reading at one per second: every few hours is plenty.
        parser.add_argument("--every", type=int, default=0, help="Repeat every N seconds (0: once)")
        parser.add_argument(
            "--json", dest="json_output", action="store_true", help="Privacy-safe JSON lines"
        )

    def handle(self, *args, every, json_output=False, **options):
        while True:
            close_old_connections()
            try:
                run = sync_logbook()
            except Exception as exc:
                self.stderr.write(f"Reading skipped: {exc.__class__.__name__}")
                close_old_connections()
                run = None
            if run is not None:
                # Status and counts only: source values never reach the logs.
                if json_output:
                    self.stdout.write(json.dumps(safe_sync_observation(run), sort_keys=True))
                else:
                    self.stdout.write(
                        f"logbook: {run.status} {json.dumps(run.summary)} {run.message}".rstrip()
                    )
            if every <= 0:
                return
            time.sleep(every)
