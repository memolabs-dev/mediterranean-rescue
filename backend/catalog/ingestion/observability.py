"""Privacy-safe, structured summary of a scheduled source reading.

Never export source URLs, raw CSV rows, error messages, quotes, hashes or credentials
to the monitoring stream. The underlying SheetSync audit record remains private.
"""

STATUSES = frozenset({"new_data", "unchanged", "refused", "failed"})
SHEETS = frozenset({"Data_operations", "Other_data", "Data_ports"})
COUNTS = frozenset({"rows", "unchanged", "to_look_at", "to_fix", "already_verified"})


def safe_sync_observation(run):
    """Stable JSON-serializable status event, independent of DB or HTTP responses."""
    summary = run.summary if isinstance(run.summary, dict) else {}
    return {
        "schema": 1,
        "sheet": run.sheet if run.sheet in SHEETS else "unknown",
        "status": run.status if run.status in STATUSES else "unknown",
        "counts": {
            key: value
            for key, value in summary.items()
            if key in COUNTS and type(value) is int and value >= 0
        },
    }
