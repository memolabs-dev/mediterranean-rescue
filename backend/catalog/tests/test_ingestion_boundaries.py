"""Existing job entrypoints and private APIs keep shared implementation functions."""

from django.test import SimpleTestCase

from catalog import logbook_sync, sync
from catalog.ingestion import logbook_sync as logbook_impl
from catalog.ingestion import sync as sync_impl


class IngestionBoundaryTests(SimpleTestCase):
    def test_sheet_reader_import_paths_are_compatible(self):
        for name in ("fetch_csv", "sync_all", "sync_sheet", "sync_actor", "summarize", "_try_lock"):
            self.assertIs(getattr(sync, name), getattr(sync_impl, name))

    def test_logbook_reader_import_paths_are_compatible(self):
        for name in ("sync_logbook", "sheet_last_date", "current_logbook_snapshot"):
            self.assertIs(getattr(logbook_sync, name), getattr(logbook_impl, name))
