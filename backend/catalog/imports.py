"""Compatible import surface; implementation lives in ingestion module."""

from catalog.ingestion.imports import (
    InputEvent,
    apply_batch,
    normalize,
    stage_payload,
)

__all__ = ["InputEvent", "normalize", "stage_payload", "apply_batch"]
