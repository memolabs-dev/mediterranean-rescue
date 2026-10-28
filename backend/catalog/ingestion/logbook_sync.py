"""Scheduled reading of the SOS MEDITERRANEE public logbook into private staging (ADR 0014).

The operations sheet behind the public map stopped on 6 February 2024; the logbook did not. Each
reading rebuilds, from the logbook, the rows that come after the sheet's last operation and stages
them as a snapshot of their own source, next to the sheet's. Volunteers then verify them like any
other row; nothing is linked, drafted or published here. Each staged row keeps its evidence (page,
entry, quote, what to check).
"""

import logging
from collections import defaultdict
from datetime import date

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction

from catalog.ingestion.sync import summarize, sync_actor
from catalog.logbook import Fetcher, ReadFailed, extract, rows_csv
from catalog.models import LogbookEvidence, RowIdentityLink, SheetSnapshot, SheetSync, Source
from catalog.review.crosswalk import stage_snapshot

logger = logging.getLogger(__name__)

LOGBOOK_SOURCE_KEY = "sos-logbook"
LOGBOOK_SOURCE = {
    "name": "SOS MEDITERRANEE public logbook",
    "url": "https://www.sosmediterranee.org/operation-archived/",
}
SHEET = "Data_operations"
# One logbook reading at a time; a different key from the sheet reading.
ADVISORY_LOCK_KEY = 72_430_119
# The date the public map's sheet stopped (export of 24 October 2026). The rebuild always starts
# here, whatever the sheet holds later: rows a volunteer has not verified yet must not vanish
# because the association pasted some of them into the sheet.
SHEET_LAST_KNOWN = date(2024, 2, 6)


def current_logbook_snapshot():
    """The rows the logbook holds now: those of the last successful reading, not of whatever
    snapshot was created last (a bad reading must never replace verified work)."""
    run = (
        SheetSync.objects.filter(source__key=LOGBOOK_SOURCE_KEY)
        .exclude(snapshot=None)
        .select_related("snapshot")
        .order_by("-created_at")
        .first()
    )
    if run is not None:
        return run.snapshot
    return (
        SheetSnapshot.objects.filter(source__key=LOGBOOK_SOURCE_KEY, sheet=SHEET)
        .order_by("-created_at")
        .first()
    )


def logbook_source():
    source, _ = Source.objects.get_or_create(key=LOGBOOK_SOURCE_KEY, defaults=LOGBOOK_SOURCE)
    return source


def sheet_last_date():
    """The last operation in the association's sheet, as the team sees how far it lags. Fictitious
    training sources never count (acceptance of 24 October 2026, D3)."""
    last = None
    for snapshot in current_sheets():
        for value in snapshot.rows.values_list("candidate__occurred_on", flat=True):
            if value and (last is None or value > last):
                last = value
    return date.fromisoformat(last) if last else SHEET_LAST_KNOWN


def current_sheets():
    """The association's own sheets as they are now: never the logbook nor training data.

    "Now" is the snapshot of the last successful reading of each source, not the one created
    last: a sheet back to older content gives back an older snapshot (backend audit of 25
    October 2026). A source never read automatically falls back to its latest manual import."""
    current = []
    for source_id in (
        SheetSnapshot.objects.filter(sheet=SHEET, source__synthetic=False)
        .exclude(source__key=LOGBOOK_SOURCE_KEY)
        .values_list("source_id", flat=True)
        .distinct()
    ):
        run = (
            SheetSync.objects.filter(source_id=source_id, sheet=SHEET)
            .exclude(snapshot=None)
            .select_related("snapshot")
            .order_by("-created_at")
            .first()
        )
        snapshot = (
            run.snapshot
            if run is not None
            else SheetSnapshot.objects.filter(source_id=source_id, sheet=SHEET)
            .order_by("-created_at")
            .first()
        )
        current.append(snapshot)
    return current


def rows_already_in_sheet(logbook_rows):
    """Rebuilt rows the association has since pasted into its sheet: row id -> sheet line.

    A rescue matches a sheet row of the same day and number of people, each sheet row at most
    once, so two rescues of the same size need two rows in the sheet (audit of 25 October 2026).
    """
    lines = defaultdict(list)
    for snapshot in current_sheets():
        for line, candidate in snapshot.rows.order_by("line").values_list("line", "candidate"):
            candidate = candidate or {}
            if candidate.get("kind") in ("rescue", "transfer") and candidate.get("nb_survivor"):
                lines[(candidate.get("occurred_on"), candidate["nb_survivor"])].append(line)
    logbook_rows = list(logbook_rows)
    # Verified rows take the sheet's lines first: the one SOS pasted is the one it was given.
    verified = set(
        RowIdentityLink.objects.filter(row__in=logbook_rows).values_list("row_id", flat=True)
    )
    found = {}
    for row in sorted(logbook_rows, key=lambda row: (row.pk not in verified, row.line)):
        candidate = row.candidate or {}
        key = (candidate.get("occurred_on"), candidate.get("nb_survivor"))
        if candidate.get("kind") in ("rescue", "transfer") and lines.get(key):
            found[row.pk] = lines[key].pop(0)
    return found


def _try_lock():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
        return cursor.fetchone()[0]


def _unlock():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])


def sync_logbook(*, actor=None, get=None):
    """One reading. Returns the SheetSync recorded, or None when another reading holds the lock."""
    if not _try_lock():
        return None
    try:
        source = logbook_source()
        actor = actor or sync_actor()
        try:
            result = extract(get or Fetcher().get, SHEET_LAST_KNOWN)
        except (ReadFailed, OSError) as exc:
            logger.warning("Logbook reading failed: %s", exc.__class__.__name__)
            return SheetSync.objects.create(
                source=source,
                sheet=SHEET,
                status="failed",
                message="The logbook could not be read.",
            )
        except Exception as exc:  # a markup change the reader did not expect: never fatal
            logger.warning("Logbook reading failed: %s", exc.__class__.__name__)
            return SheetSync.objects.create(
                source=source,
                sheet=SHEET,
                status="failed",
                message="The logbook could not be understood.",
            )
        content = rows_csv(result.sheet_rows)
        try:
            with transaction.atomic():
                snapshot, created = stage_snapshot(
                    source=source, sheet=SHEET, content=content, actor=actor
                )
                rows = {row.line: row for row in snapshot.rows.all()}
                # Rows are written in provenance order, one CSV line each: line N is item N - 2.
                if len(rows) != len(result.provenance):
                    raise ValidationError("The rebuilt rows and their evidence do not line up.")
                for index, item in enumerate(result.provenance):
                    # Also refreshed when only a quote or a note changed and the rows did not.
                    LogbookEvidence.objects.update_or_create(
                        row=rows[index + 2],
                        defaults={
                            "source_url": item["source_url"][:1000],
                            "rotation": item["rotation"][:200],
                            "logged_at": item["entry"][:40],
                            "quote": item["quote"][:500],
                            "to_check": item["to_check"],
                        },
                    )
                return SheetSync.objects.create(
                    source=source,
                    sheet=SHEET,
                    status="new_data" if created else "unchanged",
                    snapshot=snapshot,
                    sha256=snapshot.sha256,
                    summary=summarize(snapshot),
                )
        except (ValidationError, DatabaseError) as exc:
            # Refused by the checks: recorded like a refused sheet export, the previous rows stay.
            message = " ".join(getattr(exc, "messages", [])) or "The rebuilt rows were refused."
            return SheetSync.objects.create(
                source=source, sheet=SHEET, status="refused", message=message[:300]
            )
    finally:
        _unlock()
