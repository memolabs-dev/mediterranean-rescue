"""Structured ingestion monitoring must never expose source data or secrets."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from catalog.ingestion.observability import safe_sync_observation


class IngestionObservabilityTests(SimpleTestCase):
    def test_summary_emits_only_known_integer_counts(self):
        run = SimpleNamespace(
            sheet="Data_operations",
            status="refused",
            summary={
                "to_fix": 3,
                "unchanged": 0,
                "source_url": "https://example.invalid/private?token=TOP-SECRET",
                "quote": "SENSITIVE",
                "negative": -1,
                "boolean": True,
                "float": 3.5,
            },
            message="Row 4 includes a sensitive witness statement",
            sha256="SHA-SECRET",
        )
        self.assertEqual(
            safe_sync_observation(run),
            {
                "schema": 1,
                "sheet": "Data_operations",
                "status": "refused",
                "counts": {"to_fix": 3, "unchanged": 0},
            },
        )

    def test_malformed_fields_do_not_leak_payload(self):
        run = SimpleNamespace(
            sheet="private-source-name",
            status="unknown-SECRET",
            summary=["SECRET"],
            message="SECRET",
        )
        self.assertEqual(
            safe_sync_observation(run),
            {"schema": 1, "sheet": "unknown", "status": "unknown", "counts": {}},
        )

    def test_logbook_observation_is_aggregate_only(self):
        run = SimpleNamespace(
            sheet="Data_operations",
            status="new_data",
            summary={"already_verified": 4, "to_look_at": 2},
            message="internal evidence",
        )
        event = safe_sync_observation(run)
        self.assertEqual(event["counts"], {"already_verified": 4, "to_look_at": 2})
        self.assertNotIn("message", event)
