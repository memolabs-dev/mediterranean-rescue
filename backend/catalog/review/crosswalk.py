"""Identity crosswalk and port referential for Sheets snapshots (ADR 0005).

Proposals are computed, never stored. Every identity, link and port alias is created by an
explicit human approval with a reason. Nothing here creates or publishes an event.
"""

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass

from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from catalog.models import Port, PortAlias, RowIdentityLink, SheetRow, SheetSnapshot, SourceIdentity
from catalog.sheets import diagnose, load_contract

REVIEW_PERMISSION = "catalog.review_identity"
STAGE_PERMISSION = "catalog.add_sheetsnapshot"


@dataclass(frozen=True)
class LinkProposal:
    row_id: object
    line: int
    kind: str  # linked | blocked | repeat | exact_carry | candidates | new
    identity_ids: tuple = ()
    # For a repeat: the earlier line of the same snapshot whose cells it copies exactly.
    repeats_line: int | None = None


@dataclass(frozen=True)
class PortProposal:
    row_id: object
    line: int
    label: str | None
    kind: str  # linked | blocked | existing_port | new_port
    port_ids: tuple = ()


@dataclass(frozen=True)
class PortLabel:
    label: str
    rows: int
    suggested_port_id: object = None


def candidate_fingerprint(candidate):
    canonical = json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _require(actor, permission):
    if not actor.is_active or not actor.has_perm(permission):
        raise PermissionDenied(f"{permission} permission required")


def _require_reason(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A review reason is required")


def diagnose_for(source, sheet, content, contract=None):
    contract = contract or load_contract()
    if sheet not in contract["sheets"]:
        raise ValidationError("Unknown sheet")
    return diagnose(content, sheet, contract, "synthetic" if source.synthetic else "unreviewed")


def blocking_reason(result):
    """Why a diagnosed export cannot be staged, or None. Shared with the private import API."""
    status = result["status"]["source_read"]
    if status in ("rejected", "partial"):
        return f"read_{status}"
    row_lines = {row["line"] for row in result["rows"]}
    if any(
        issue["severity"] == "error" and issue["line"] not in row_lines
        for issue in result["issues"]
    ):
        return "file_errors"
    return None


@transaction.atomic
def stage_snapshot(*, source, sheet, content, actor):
    """Diagnose an export and keep it in private staging. Idempotent per content."""
    _require(actor, STAGE_PERMISSION)
    result = diagnose_for(source, sheet, content)
    status = result["status"]["source_read"]
    blocking = blocking_reason(result)
    if blocking in ("read_rejected", "read_partial"):
        raise ValidationError(f"Snapshot not stageable: CSV reading is {status}")
    if blocking == "file_errors":
        raise ValidationError("Snapshot not stageable: file-level errors, see the diagnostic")
    row_lines = {row["line"] for row in result["rows"]}
    snapshot, created = SheetSnapshot.objects.get_or_create(
        source=source,
        sheet=sheet,
        sha256=result["snapshot"]["sha256"],
        # Same bytes under a new contract version are a new normalization, kept apart.
        contract_version=result["contract"]["version"],
        defaults={
            "source_read": status,
            "byte_count": result["snapshot"]["bytes"],
            "row_count": len(result["rows"]),
            "header_cells": result["header"]["cells"],
            "staged_by": actor,
        },
    )
    if not created:
        return snapshot, False
    errors_by_line = defaultdict(list)
    for issue in result["issues"]:
        if issue["severity"] == "error" and issue["line"] in row_lines:
            errors_by_line[issue["line"]].append(issue["code"])
    SheetRow.objects.bulk_create(
        [
            SheetRow(
                snapshot=snapshot,
                line=row["line"],
                raw_cells=row["raw_cells"],
                candidate=row["candidate"],
                fingerprint=candidate_fingerprint(row["candidate"]) if row["candidate"] else "",
                error_codes=errors_by_line[row["line"]],
            )
            for row in result["rows"]
        ]
    )
    return snapshot, True


def _is_linkable(row):
    return row.candidate is not None and not row.error_codes


def _linked_rows_elsewhere(snapshot):
    return (
        SheetRow.objects.filter(
            snapshot__source=snapshot.source,
            snapshot__sheet=snapshot.sheet,
            identity_link__isnull=False,
        )
        .exclude(snapshot=snapshot)
        .select_related("identity_link")
    )


def _two_rescues_on_purpose(row):
    # Two logbook rescues of the same size the same day, kept apart because the mission total
    # counts both (ADR 0014): equal cells, yet two rows.
    evidence = getattr(row, "logbook", None)
    return evidence is not None and "same_size_twice" in evidence.to_check


def repeated_lines(rows):
    """Row id -> the earlier line it copies cell for cell, for rows entered twice in a sheet.
    The diagnosis reports them (exact_duplicate_row); they are never merged nor counted twice."""
    first_line, repeats = {}, {}
    for row in sorted(rows, key=lambda row: row.line):
        if _two_rescues_on_purpose(row):
            continue
        key = json.dumps(row.raw_cells, ensure_ascii=False)
        if key in first_line:
            repeats[row.pk] = first_line[key]
        else:
            first_line[key] = row.line
    return repeats


def propose_links(snapshot):
    """Compute one proposal per row of the snapshot, in line order. Creates nothing."""
    rows = list(snapshot.rows.select_related("identity_link", "logbook").order_by("line"))
    repeats = repeated_lines(rows)
    taken = {row.identity_link.identity_id for row in rows if hasattr(row, "identity_link")}
    identities_by_fingerprint = defaultdict(set)
    latest_by_identity = {}
    for row in _linked_rows_elsewhere(snapshot).order_by("snapshot__created_at", "line"):
        identity_id = row.identity_link.identity_id
        identities_by_fingerprint[row.fingerprint].add(identity_id)
        latest_by_identity[identity_id] = row.candidate
    # Rows in error count too: their candidate can equal a sane row's candidate.
    fingerprint_counts = Counter(row.fingerprint for row in rows if row.fingerprint)
    carry_target = {}
    for row in rows:
        if hasattr(row, "identity_link") or not _is_linkable(row):
            continue
        matches = identities_by_fingerprint.get(row.fingerprint, set())
        # Exactly one identity ever had this content, it is free here, and the content is
        # unique in this snapshot.
        if len(matches) == 1 and fingerprint_counts[row.fingerprint] == 1:
            (identity_id,) = matches
            if identity_id not in taken:
                carry_target[row.pk] = identity_id
    claimed = Counter(carry_target.values())
    proposals = []
    for row in rows:
        if hasattr(row, "identity_link"):
            proposals.append(
                LinkProposal(row.pk, row.line, "linked", (row.identity_link.identity_id,))
            )
            continue
        if not _is_linkable(row):
            proposals.append(LinkProposal(row.pk, row.line, "blocked"))
            continue
        if row.pk in repeats:
            proposals.append(LinkProposal(row.pk, row.line, "repeat", repeats_line=repeats[row.pk]))
            continue
        identity_id = carry_target.get(row.pk)
        # An identity proposed for two rows (old and corrected content) is never automatic.
        if identity_id is not None and claimed[identity_id] == 1:
            proposals.append(LinkProposal(row.pk, row.line, "exact_carry", (identity_id,)))
            continue
        same_day = sorted(
            (
                identity_id
                for identity_id, candidate in latest_by_identity.items()
                if identity_id not in taken
                and candidate.get("occurred_on") == row.candidate.get("occurred_on")
                and candidate.get("kind") == row.candidate.get("kind")
            ),
            key=str,
        )
        kind = "candidates" if same_day else "new"
        proposals.append(LinkProposal(row.pk, row.line, kind, tuple(same_day)))
    return proposals


@transaction.atomic
def approve_link(*, row, actor, reason, identity=None, _exact_carry=False):
    """Link a row to an existing identity, or to a new one when identity is None.

    A manual choice is recorded as reviewed_match even when contents are equal; only
    approve_exact_carries records exact_carry, for proposals that were unambiguous.
    """
    _require(actor, REVIEW_PERMISSION)
    _require_reason(reason)
    row = SheetRow.objects.select_for_update().select_related("snapshot").get(pk=row.pk)
    snapshot = row.snapshot
    if not _is_linkable(row):
        raise ValidationError("A row in error cannot be linked; fix the source or the contract")
    if RowIdentityLink.objects.filter(row=row).exists():
        raise ValidationError("This row is already linked")
    earlier = (
        SheetRow.objects.filter(snapshot=snapshot, line__lt=row.line, raw_cells=row.raw_cells)
        .order_by("line")
        .values_list("line", flat=True)
        .first()
    )
    if earlier is not None and not _two_rescues_on_purpose(row):
        raise ValidationError(
            f"This row repeats row {earlier} of the same update; delete the copy in the sheet"
        )
    if identity is None:
        identity = SourceIdentity.objects.create(
            source=snapshot.source, sheet=snapshot.sheet, created_by=actor, reason=reason
        )
        match = "new"
    else:
        identity = SourceIdentity.objects.select_for_update().get(pk=identity.pk)
        if identity.source_id != snapshot.source_id or identity.sheet != snapshot.sheet:
            raise ValidationError("Identity belongs to another source or sheet")
        if RowIdentityLink.objects.filter(identity=identity, snapshot=snapshot).exists():
            raise ValidationError("This identity is already linked in this snapshot")
        match = "exact_carry" if _exact_carry else "reviewed_match"
    try:
        with transaction.atomic():
            return RowIdentityLink.objects.create(
                row=row,
                snapshot=snapshot,
                identity=identity,
                match=match,
                approved_by=actor,
                reason=reason,
            )
    except IntegrityError as exc:
        raise ValidationError("Concurrent link on this row or identity") from exc


@transaction.atomic
def approve_exact_carries(*, snapshot, actor, reason, rows=None):
    """Approve, in one human action, the exact_carry proposals of a snapshot.

    With `rows` (row ids), only that explicit selection is approved, and every selected row
    must still be an exact carry when the request runs; otherwise nothing is written.
    """
    _require(actor, REVIEW_PERMISSION)
    _require_reason(reason)
    snapshot = SheetSnapshot.objects.select_for_update().get(pk=snapshot.pk)
    carries = [p for p in propose_links(snapshot) if p.kind == "exact_carry"]
    if rows is not None:
        selected = {str(row_id) for row_id in rows}
        eligible = {str(p.row_id) for p in carries}
        if not selected or not selected <= eligible:
            raise ValidationError("Some selected rows are no longer unambiguous exact carries")
        carries = [p for p in carries if str(p.row_id) in selected]
    identities = {
        i.pk: i for i in SourceIdentity.objects.filter(pk__in=[p.identity_ids[0] for p in carries])
    }
    for proposal in carries:
        approve_link(
            row=SheetRow(pk=proposal.row_id),
            actor=actor,
            reason=reason,
            identity=identities[proposal.identity_ids[0]],
            _exact_carry=True,
        )
    return len(carries)


def _port_name_index():
    index = defaultdict(list)
    for port in Port.objects.only("id", "name"):
        index[port.name.casefold()].append(port.pk)
    return index


def _suggest(index, label):
    matches = index.get(label.casefold(), [])
    return matches[0] if len(matches) == 1 else None


def propose_ports(snapshot):
    """Proposals for a Data_ports snapshot: only exact case-insensitive names are suggested."""
    if snapshot.sheet != "Data_ports":
        raise ValidationError("Port proposals need a Data_ports snapshot")
    aliases = {
        alias.label: tuple(sorted((port.pk for port in alias.ports.all()), key=str))
        for alias in PortAlias.objects.filter(source=snapshot.source).prefetch_related("ports")
    }
    index = _port_name_index()
    proposals = []
    for row in snapshot.rows.order_by("line"):
        label = (row.candidate or {}).get("nom")
        if label and label in aliases:
            proposals.append(PortProposal(row.pk, row.line, label, "linked", aliases[label]))
        elif not label or not _is_linkable(row):
            proposals.append(PortProposal(row.pk, row.line, label, "blocked"))
        elif (port_id := _suggest(index, label)) is not None:
            proposals.append(PortProposal(row.pk, row.line, label, "existing_port", (port_id,)))
        else:
            proposals.append(PortProposal(row.pk, row.line, label, "new_port"))
    return proposals


def unresolved_port_labels(source):
    """Port_disembarkation labels of a source without an approved alias, with a suggestion."""
    aliased = set(PortAlias.objects.filter(source=source).values_list("label", flat=True))
    latest = (
        SheetSnapshot.objects.filter(source=source, sheet="Data_operations")
        .order_by("-created_at")
        .first()
    )
    if latest is None:
        return []
    counts = Counter()
    # Counts come from the latest export only, so re-exports do not inflate them.
    for candidate in latest.rows.values_list("candidate", flat=True):
        label = (candidate or {}).get("Port_disembarkation")
        if label and label not in aliased:
            counts[label] += 1
    index = _port_name_index()
    return [PortLabel(label, counts[label], _suggest(index, label)) for label in sorted(counts)]


def _check_label(source, label):
    if not label or label != label.strip():
        raise ValidationError("Port label must be the exact, non-empty source text")
    if PortAlias.objects.filter(source=source, label=label).exists():
        raise ValidationError("This label already has an approved reading")


def _create_alias(**fields):
    try:
        with transaction.atomic():
            return PortAlias.objects.create(**fields)
    except IntegrityError as exc:
        raise ValidationError("Concurrent reading for this label") from exc


@transaction.atomic
def approve_port_alias(
    *, source, label, actor, reason, ports=(), row=None, location=None, country_code=""
):
    """Map an exact source label to one or more ports; create the port when none is given.

    A port created from a Data_ports row takes the row position, unless the reviewer gives
    an explicit location. A row in error (e.g. ambiguous hemisphere) needs that location.
    """
    _require(actor, REVIEW_PERMISSION)
    _require_reason(reason)
    _check_label(source, label)
    ports = list(ports)
    location_source = "reviewer"
    if not ports:
        if row is not None:
            row = SheetRow.objects.select_related("snapshot").get(pk=row.pk)
            if row.snapshot.source_id != source.id or row.snapshot.sheet != "Data_ports":
                raise ValidationError("Port row must come from this source's Data_ports")
            if (row.candidate or {}).get("nom") != label:
                raise ValidationError("Port row label differs from the alias label")
            position = (row.candidate or {}).get("position")
            if location is None and position:
                location = Point(
                    float(position["longitude"]), float(position["latitude"]), srid=4326
                )
                location_source = "sheet_row"
                if location.x == 0 and location.y == 0:
                    raise ValidationError("Row position is 0,0; give the real one explicitly")
            if location is None:
                raise ValidationError("This row has no usable position; give one explicitly")
        if location is None:
            raise ValidationError("A new port needs a Data_ports row or an explicit location")
        if not (-180 <= location.x <= 180 and -90 <= location.y <= 90):
            raise ValidationError("Invalid WGS84 coordinates")
        ports = [
            Port.objects.create(
                name=label,
                country_code=country_code,
                location=location,
                location_source=location_source,
                created_from=row,
            )
        ]
    elif row is not None or location is not None:
        raise ValidationError("Give existing ports or a row/location for a new port, not both")
    alias = _create_alias(
        source=source, label=label, target="ports", approved_by=actor, reason=reason
    )
    alias.ports.set(ports)
    return alias


@transaction.atomic
def classify_port_label(*, source, label, actor, reason, vessel=None):
    """Record that a label is a transfer vessel, or not a port at all (region, unknown)."""
    _require(actor, REVIEW_PERMISSION)
    _require_reason(reason)
    _check_label(source, label)
    return _create_alias(
        source=source,
        label=label,
        target="vessel" if vessel is not None else "not_a_port",
        vessel=vessel,
        approved_by=actor,
        reason=reason,
    )
