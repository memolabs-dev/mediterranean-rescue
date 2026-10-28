"""Compatible import surface; implementation lives in ingestion module."""

from catalog.ingestion.imports import (
    InputEvent,
    normalize,
    stage_payload,
    apply_batch,
)

__all__ = ["InputEvent", "normalize", "stage_payload", "apply_batch"]
