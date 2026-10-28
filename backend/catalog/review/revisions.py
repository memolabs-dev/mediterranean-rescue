"""Reviewed revisions of existing drafts from corrected source rows (ADR 0007).

A revision compares the translation of the row a draft came from with the translation of
the corrected row. It never overwrites a field edited by hand, never touches a published
event, and is always a single human decision with a reason.
"""

from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from catalog.review.drafts import DRAFT_FIELDS, _counts_consistent, _draft_event, comparable_value, drafted_values
from catalog.models import Event, EventRevision, SheetRow, SheetSnapshot, SourceIdentity

REVISION_PERMISSION = "catalog.change_event"


@dataclass(frozen=True)
class RevisionProposal:
    row_id: object
    identity_id: object = None
    event_id: object = None
    changes: dict = field(default_factory=dict)  # field -> (before, after)
    conflicts: tuple = ()
    # not_linked | not_drafted | stale_snapshot | no_change | revision_rejected
    # | event_published | position_to_review | inconsistent_counts | invalid_revision
    blocked_by: str | None = None


def _is_latest(snapshot):
    latest = (
        SheetSnapshot.objects.filter(source=snapshot.source, sheet=snapshot.sheet)
        .order_by("-created_at", "-pk")
        .values_list("pk", flat=True)
        .first()
    )
    return latest == snapshot.pk


def _proposal(row, event=None):
    """Return (proposal, translated corrected event or None)."""
    link = getattr(row, "identity_link", None)
    if link is None:
        return RevisionProposal(row.pk, blocked_by="not_linked"), None
    identity = link.identity
    base = RevisionProposal(row.pk, identity.pk, identity.event_id)
    if identity.event_id is None:
        return RevisionProposal(row.pk, identity.pk, blocked_by="not_drafted"), None

    def blocked(reason):
        return RevisionProposal(row.pk, identity.pk, identity.event_id, blocked_by=reason), None

    if not _is_latest(row.snapshot):
        return blocked("stale_snapshot")
    if identity.drafted_from.fingerprint == row.fingerprint:
        return blocked("no_change")
    if EventRevision.objects.filter(
        identity=identity,
        decision="rejected",
        from_row__fingerprint=identity.drafted_from.fingerprint,
        to_row__fingerprint=row.fingerprint,
    ).exists():
        # The same change was already refused; another change gets a new proposal.
        return blocked("revision_rejected")
    event = event or identity.event
    if event.status == "published":
        return blocked("event_published")
    position = row.candidate.get("position")
    if position and float(position["longitude"]) == 0 and float(position["latitude"]) == 0:
        return blocked("position_to_review")
    after = _draft_event(row, identity)
    if not _counts_consistent(after):
        return blocked("inconsistent_counts")
    try:
        # The draft keeps its identity, so uniqueness of (source, external_id) is not rechecked.
        after.full_clean(validate_unique=False, validate_constraints=False)
    except ValidationError:
        return blocked("invalid_revision")
    # Baseline: values recorded when the draft was made (or last revised), not a fresh
    # translation, so later alias or rule changes do not look like hand edits.
    before = identity.drafted_values
    current = {name: comparable_value(event, name) for name in DRAFT_FIELDS}
    target = {name: comparable_value(after, name) for name in DRAFT_FIELDS}
    changes = {
        name: (before.get(name), target[name])
        for name in DRAFT_FIELDS
        if before.get(name) != target[name]
    }
    edited = {name for name in DRAFT_FIELDS if current[name] != before.get(name)}
    conflicts = [name for name in changes if name in edited and current[name] != target[name]]
    if "title" in changes and "title" not in conflicts and edited & {"kind", "occurred_on"}:
        # A regenerated title would contradict a kind or date kept from a hand edit.
        conflicts.append("title")
    return (
        RevisionProposal(base.row_id, base.identity_id, base.event_id, changes, tuple(conflicts)),
        after,
    )


def _load(row):
    return SheetRow.objects.select_related(
        "snapshot__source",
        "identity_link__identity__source",
        "identity_link__identity__event",
        "identity_link__identity__drafted_from__snapshot",
    ).get(pk=row.pk)


def propose_revision(row):
    """Compute the revision a corrected row would make. Writes nothing."""
    return _proposal(_load(row))[0]


def _authorize(actor, reason):
    if not actor.is_active or not actor.has_perm(REVISION_PERMISSION):
        raise PermissionDenied(f"{REVISION_PERMISSION} permission required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A review reason is required")


def _locked(row):
    row = _load(row)
    link = getattr(row, "identity_link", None)
    if link is None or link.identity.event_id is None:
        raise ValidationError("This row has no drafted identity to revise")
    identity = SourceIdentity.objects.select_for_update().get(pk=link.identity_id)
    event = Event.objects.select_for_update().get(pk=identity.event_id)
    row = _load(row)  # reload after locking so the proposal sees committed state
    return row, identity, event


@transaction.atomic
def apply_revision(*, row, actor, reason):
    """Apply a corrected row to its draft, if nothing blocks and nothing conflicts."""
    _authorize(actor, reason)
    row, identity, event = _locked(row)
    proposal, after = _proposal(row, event)
    if proposal.blocked_by:
        raise ValidationError(f"Revision blocked: {proposal.blocked_by}")
    if proposal.conflicts:
        raise ValidationError(
            "Fields edited by hand would be overwritten: " + ", ".join(proposal.conflicts)
        )
    for name in proposal.changes:
        setattr(event, name, getattr(after, name))
    event.full_clean()
    event.save()
    from_row = identity.drafted_from
    identity.drafted_from = row
    identity.drafted_values = drafted_values(event)
    identity.save(update_fields=["drafted_from", "drafted_values", "updated_at"])
    return EventRevision.objects.create(
        event=event,
        identity=identity,
        from_row=from_row,
        to_row=row,
        changes={name: list(values) for name, values in proposal.changes.items()},
        decision="applied",
        decided_by=actor,
        reason=reason,
    )


@transaction.atomic
def reject_revision(*, row, actor, reason):
    """Record that this change must not be applied; conflicts do not prevent refusing."""
    _authorize(actor, reason)
    row, identity, event = _locked(row)
    proposal, _ = _proposal(row, event)
    if proposal.blocked_by:
        # Only a computed proposal can be refused, so the trace records what was refused.
        raise ValidationError(f"Revision blocked: {proposal.blocked_by}")
    return EventRevision.objects.create(
        event=event,
        identity=identity,
        from_row=identity.drafted_from,
        to_row=row,
        changes={name: list(values) for name, values in proposal.changes.items()},
        decision="rejected",
        decided_by=actor,
        reason=reason,
    )
