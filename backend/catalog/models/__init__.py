"""Catalog's stable Django app label and backwards-compatible model registry.

Model implementations are split by business domain. Keep `catalog` as INSTALLED_APPS,
all historical migration names and default catalog_* table names unchanged.
Do not change a model class name or its app label without a reviewed migration plan.
"""

from .base import UUIDModel
from .sources import Source
from .events import Event, EventKind, EventQuerySet, EventRevision, Evidence, Vessel, Voyage
from .geography import Port, PortAlias, PortAliasPort
from .ingestion import (
    SHEETS,
    ImportBatch,
    LogbookEvidence,
    RowIdentityLink,
    SheetRow,
    SheetSnapshot,
    SheetSync,
    SourceIdentity,
    StagedRecord,
)
from .publication import PublicationAudit
from .accounts import Invitation

__all__ = [
    "UUIDModel",
    "Source",
    "Vessel",
    "Voyage",
    "EventKind",
    "EventQuerySet",
    "Event",
    "Evidence",
    "Port",
    "PortAlias",
    "PortAliasPort",
    "ImportBatch",
    "StagedRecord",
    "SHEETS",
    "SheetSnapshot",
    "SheetSync",
    "SheetRow",
    "LogbookEvidence",
    "SourceIdentity",
    "RowIdentityLink",
    "PublicationAudit",
    "EventRevision",
    "Invitation",
]
