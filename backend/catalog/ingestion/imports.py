"""Local canonical imports. No network access or implicit publication."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Event, EventKind, ImportBatch, Source, StagedRecord


@dataclass(frozen=True)
class InputEvent:
    external_id: str
    kind: str
    occurred_on: date
    title: str
    source_url: str
    people: int | None
    longitude: float | None
    latitude: float | None
    location_precision: str
    summary: str


def normalize(row: Any) -> InputEvent:
    if not isinstance(row, dict):
        raise ValidationError("Each row must be an object")

    def string(key, max_length):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > max_length:
            raise ValidationError(f"Invalid {key}")
        return value

    external_id = string("external_id", 200)
    kind = string("kind", 20)
    if kind not in EventKind.values:
        raise ValidationError("Unknown event kind")
    raw_date = string("occurred_on", 10)
    try:
        occurred_on = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValidationError("Invalid ISO date") from exc
    if occurred_on.isoformat() != raw_date:
        raise ValidationError("Use YYYY-MM-DD")
    source_url = string("source_url", 1000)
    parsed = urlparse(source_url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValidationError("Invalid public source URL")
    people = row.get("people")
    if people is not None and (type(people) is not int or not 0 <= people <= 100000):
        raise ValidationError("Unknown counts must be null; known counts nonnegative integers")
    lon, lat = row.get("longitude"), row.get("latitude")
    if (lon is None) != (lat is None):
        raise ValidationError("Both coordinates or neither are required")
    if lon is not None:
        if (
            type(lon) not in {int, float}
            or type(lat) not in {int, float}
            or not (-180 <= lon <= 180 and -90 <= lat <= 90)
        ):
            raise ValidationError("Invalid WGS84 point")
    precision = row.get("location_precision", "unknown")
    if precision not in {"unknown", "approximate", "reported"} or (
        (lon is None) != (precision == "unknown")
    ):
        raise ValidationError("Position precision does not match coordinates")
    summary = row.get("summary", "")
    if not isinstance(summary, str) or len(summary) > 10000:
        raise ValidationError("Invalid summary")
    return InputEvent(
        external_id,
        kind,
        occurred_on,
        string("title", 240),
        source_url,
        people,
        lon,
        lat,
        precision,
        summary,
    )


@transaction.atomic
def stage_payload(*, source: Source, content: bytes) -> tuple[ImportBatch, bool]:
    if len(content) > 5 * 1024 * 1024:
        raise ValidationError("Import exceeds 5 MiB")
    try:
        rows = json.loads(content)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("Invalid JSON") from exc
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValidationError("Expected an array of at most 10000 rows")
    normalized = [normalize(row) for row in rows]
    keys = [row.external_id for row in normalized]
    if len(keys) != len(set(keys)):
        raise ValidationError("Duplicate external identity")
    checksum = hashlib.sha256(content).hexdigest()
    batch, created = ImportBatch.objects.get_or_create(
        source=source, checksum=checksum, defaults={"row_count": len(rows)}
    )
    if created:
        StagedRecord.objects.bulk_create(
            [StagedRecord(batch=batch, ordinal=i + 1, payload=row) for i, row in enumerate(rows)]
        )
    return batch, created


@transaction.atomic
def apply_batch(*, batch_id) -> int:
    batch = ImportBatch.objects.select_for_update().select_related("source").get(pk=batch_id)
    if batch.status == "applied":
        return 0
    records = list(batch.records.order_by("ordinal"))
    rows = [normalize(record.payload) for record in records]
    for row in rows:
        existing = Event.objects.filter(source=batch.source, external_id=row.external_id).first()
        if existing:
            raise ValidationError(
                "Existing identities require a reviewed revision; no silent overwrite"
            )
        event = Event(
            source=batch.source,
            external_id=row.external_id,
            kind=row.kind,
            occurred_on=row.occurred_on,
            title=row.title,
            summary=row.summary,
            source_url=row.source_url,
            people=row.people,
            location_precision=row.location_precision,
            location=Point(row.longitude, row.latitude, srid=4326)
            if row.longitude is not None
            else None,
        )
        event.full_clean()
        event.save()
    batch.status = "applied"
    batch.save(update_fields=["status", "updated_at"])
    return len(rows)
