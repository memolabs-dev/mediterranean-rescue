"""Backward compatible review imports, with no domain policy duplication."""

from django.test import SimpleTestCase

from catalog import crosswalk, drafts, revisions
from catalog.review import crosswalk as review_crosswalk
from catalog.review import drafts as review_drafts
from catalog.review import revisions as review_revisions


class ReviewBoundaryTests(SimpleTestCase):
    def test_crosswalk_imports_share_the_same_implementation(self):
        for name in (
            "stage_snapshot",
            "propose_links",
            "approve_link",
            "approve_exact_carries",
            "approve_port_alias",
            "classify_port_label",
            "_port_name_index",
            "_suggest",
        ):
            self.assertIs(getattr(crosswalk, name), getattr(review_crosswalk, name))

    def test_draft_and_revision_imports_share_the_same_implementation(self):
        self.assertIs(drafts.create_drafts, review_drafts.create_drafts)
        self.assertIs(drafts.plan_drafts, review_drafts.plan_drafts)
        self.assertIs(revisions.apply_revision, review_revisions.apply_revision)
        self.assertIs(revisions.reject_revision, review_revisions.reject_revision)
