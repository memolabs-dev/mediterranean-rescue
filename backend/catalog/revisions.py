"""Legacy import path; implementation is in catalog.review.revisions.

Prefer importing directly from catalog.review.revisions for new code.
"""

from catalog.review.revisions import (
    REVISION_PERMISSION,
    RevisionProposal,
    _authorize,
    _is_latest,
    _load,
    _locked,
    _proposal,
    apply_revision,
    propose_revision,
    reject_revision,
)

__all__ = [
    "REVISION_PERMISSION",
    "RevisionProposal",
    "_authorize",
    "_is_latest",
    "_load",
    "_locked",
    "_proposal",
    "apply_revision",
    "propose_revision",
    "reject_revision",
]
