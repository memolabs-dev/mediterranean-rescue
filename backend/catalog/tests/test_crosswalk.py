"""Identity crosswalk and port referential (ADR 0005). Synthetic inputs, real PostGIS."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from catalog.crosswalk import (
    approve_exact_carries,
    approve_link,
    approve_port_alias,
    classify_port_label,
    propose_links,
    propose_ports,
    stage_snapshot,
    unresolved_port_labels,
)
from catalog.models import (
    Event,
    Port,
    PortAlias,
    RowIdentityLink,
    SheetRow,
    SheetSnapshot,
    Source,
    SourceIdentity,
    Vessel,
)
from catalog.sheets import load_contract
from catalog.tests.test_sheets import ops_csv, ops_row

PORTS_HEADER = "nom,latitude,longitude"


def ports_csv(*rows):
    return ("\n".join([PORTS_HEADER, *rows]) + "\n").encode()


def kinds(proposals):
    return [proposal.kind for proposal in proposals]


class CrosswalkTestCase(TestCase):
    def setUp(self):
        self.source = Source.objects.create(
            key="fixture", name="Synthetic fixture", url="https://example.org", synthetic=True
        )
        self.other_source = Source.objects.create(
            key="other", name="Other fixture", url="https://example.org/other", synthetic=True
        )
        user_model = get_user_model()
        self.reviewer = user_model.objects.create_user(username="reviewer", password=None)
        self.reviewer.user_permissions.add(
            Permission.objects.get(codename="review_identity"),
            Permission.objects.get(codename="add_sheetsnapshot"),
        )
        self.reviewer = user_model.objects.get(pk=self.reviewer.pk)  # reset permission cache
        self.outsider = user_model.objects.create_user(username="outsider", password=None)

    def stage(self, content, sheet="Data_operations", source=None):
        return stage_snapshot(
            source=source or self.source, sheet=sheet, content=content, actor=self.reviewer
        )


class SnapshotTests(CrosswalkTestCase):
    def test_snapshot_is_stored_with_provenance_and_replay_is_idempotent(self):
        content = ops_csv(ops_row(), ops_row(date="04/02/2024", nb_survivor="-1"))
        snapshot, created = self.stage(content)
        self.assertTrue(created)
        self.assertEqual(snapshot.row_count, 2)
        self.assertEqual(snapshot.source_read, "complete")
        self.assertEqual(snapshot.contract_version, "sheets-observed-v1")
        first, second = snapshot.rows.order_by("line")
        self.assertEqual((first.line, second.line), (2, 3))
        self.assertEqual(first.raw_cells[0], "03/02/2024")
        self.assertEqual(first.candidate["occurred_on"], "2024-02-03")
        self.assertEqual(len(first.fingerprint), 64)
        self.assertEqual(first.error_codes, [])
        self.assertEqual(second.error_codes, ["negative_count"])
        again, created_again = self.stage(content)
        self.assertEqual((again.pk, created_again), (snapshot.pk, False))
        self.assertEqual(SheetRow.objects.count(), 2)
        self.assertEqual(Event.objects.count(), 0)

    def test_rejected_partial_or_file_level_errors_are_refused(self):
        for content in (
            b'date,type_ops\n"unterminated',
            b"date,date,type_ops,latitude,longitude\n1,2,3,4,5\n",
            b"\xff\xfe",
        ):
            with self.assertRaises(ValidationError):
                self.stage(content)
        self.assertEqual(SheetSnapshot.objects.count(), 0)

    def test_unterminated_export_is_accepted_and_recorded(self):
        snapshot, _ = self.stage(ops_csv(ops_row())[:-1])
        self.assertEqual(snapshot.source_read, "end_unverified")

    def test_staging_needs_permission(self):
        with self.assertRaises(PermissionDenied):
            stage_snapshot(
                source=self.source,
                sheet="Data_operations",
                content=ops_csv(ops_row()),
                actor=self.outsider,
            )


class IdentityTests(CrosswalkTestCase):
    def test_first_export_proposes_new_identities_and_blocks_rows_in_error(self):
        snapshot, _ = self.stage(ops_csv(ops_row(), ops_row(date="31/02/2024")))
        self.assertEqual(kinds(propose_links(snapshot)), ["new", "blocked"])

    def test_approving_a_new_identity_records_who_why_and_how(self):
        snapshot, _ = self.stage(ops_csv(ops_row()))
        row = snapshot.rows.get()
        link = approve_link(row=row, actor=self.reviewer, reason="First observation")
        self.assertEqual(link.match, "new")
        self.assertEqual(link.approved_by, self.reviewer)
        identity = link.identity
        self.assertEqual((identity.source, identity.sheet), (self.source, "Data_operations"))
        self.assertEqual(identity.external_id, f"Data_operations:{identity.pk}")
        self.assertEqual(kinds(propose_links(snapshot)), ["linked"])
        self.assertEqual(Event.objects.count(), 0)

    def test_guards(self):
        snapshot, _ = self.stage(
            ops_csv(ops_row(), ops_row(date="04/02/2024"), ops_row(date="31/02/2024"))
        )
        first, second, broken = snapshot.rows.order_by("line")
        with self.assertRaises(PermissionDenied):
            approve_link(row=first, actor=self.outsider, reason="x")
        with self.assertRaises(ValidationError):
            approve_link(row=first, actor=self.reviewer, reason="  ")
        with self.assertRaises(ValidationError):
            approve_link(row=broken, actor=self.reviewer, reason="Row in error")
        link = approve_link(row=first, actor=self.reviewer, reason="ok")
        with self.assertRaises(ValidationError):
            approve_link(row=first, actor=self.reviewer, reason="Twice")
        with self.assertRaises(ValidationError):
            # One identity cannot describe two rows of the same snapshot.
            approve_link(row=second, actor=self.reviewer, reason="Same", identity=link.identity)
        foreign = SourceIdentity.objects.create(
            source=self.other_source, sheet="Data_operations", created_by=self.reviewer, reason="x"
        )
        with self.assertRaises(ValidationError):
            approve_link(row=second, actor=self.reviewer, reason="Foreign", identity=foreign)
        other_sheet = SourceIdentity.objects.create(
            source=self.source, sheet="Other_data", created_by=self.reviewer, reason="x"
        )
        with self.assertRaises(ValidationError):
            approve_link(row=second, actor=self.reviewer, reason="Sheet", identity=other_sheet)

    def test_database_enforces_one_identity_per_snapshot(self):
        snapshot, _ = self.stage(ops_csv(ops_row(), ops_row(date="04/02/2024")))
        first, second = snapshot.rows.order_by("line")
        link = approve_link(row=first, actor=self.reviewer, reason="ok")
        with self.assertRaises(IntegrityError), transaction.atomic():
            RowIdentityLink.objects.create(
                row=second,
                snapshot=snapshot,
                identity=link.identity,
                match="reviewed_match",
                approved_by=self.reviewer,
                reason="bypass",
            )

    def test_unchanged_rows_in_a_new_export_carry_their_identity_after_review(self):
        first_export, _ = self.stage(ops_csv(ops_row(), ops_row(date="04/02/2024")))
        links = [
            approve_link(row=row, actor=self.reviewer, reason="Initial")
            for row in first_export.rows.order_by("line")
        ]
        # Same rows, new order and a new row: line numbers change, identities do not.
        second_export, _ = self.stage(
            ops_csv(ops_row(date="04/02/2024"), ops_row(date="05/02/2024"), ops_row())
        )
        proposals = propose_links(second_export)
        self.assertEqual(kinds(proposals), ["exact_carry", "new", "exact_carry"])
        self.assertEqual(proposals[0].identity_ids, (links[1].identity_id,))
        self.assertEqual(proposals[2].identity_ids, (links[0].identity_id,))
        self.assertEqual(RowIdentityLink.objects.filter(snapshot=second_export).count(), 0)
        carried = approve_exact_carries(
            snapshot=second_export, actor=self.reviewer, reason="Unchanged"
        )
        self.assertEqual(carried, 2)
        self.assertEqual(SourceIdentity.objects.count(), 2)
        self.assertEqual(kinds(propose_links(second_export)), ["linked", "new", "linked"])

    def test_corrected_row_needs_an_explicit_match(self):
        first_export, _ = self.stage(ops_csv(ops_row(nb_survivor="40")))
        original = approve_link(row=first_export.rows.get(), actor=self.reviewer, reason="Initial")
        corrected, _ = self.stage(ops_csv(ops_row(nb_survivor="42")))
        proposal = propose_links(corrected)[0]
        self.assertEqual(proposal.kind, "candidates")
        self.assertEqual(proposal.identity_ids, (original.identity_id,))
        self.assertEqual(
            approve_exact_carries(snapshot=corrected, actor=self.reviewer, reason="x"), 0
        )
        link = approve_link(
            row=corrected.rows.get(),
            actor=self.reviewer,
            reason="Same rescue, count corrected",
            identity=original.identity,
        )
        self.assertEqual(link.match, "reviewed_match")
        self.assertEqual(original.identity.links.count(), 2)

    def test_duplicated_content_is_never_carried_automatically(self):
        first_export, _ = self.stage(ops_csv(ops_row()))
        approve_link(row=first_export.rows.get(), actor=self.reviewer, reason="Initial")
        doubled, _ = self.stage(ops_csv(ops_row(), ops_row()))
        self.assertEqual(kinds(propose_links(doubled)), ["candidates", "repeat"])

    def test_a_row_copied_twice_in_the_sheet_is_never_counted_twice(self):
        # Acceptance of 24 October 2026, D4: the copy stayed "looks new" and could not be decided.
        snapshot, _ = self.stage(ops_csv(ops_row(), ops_row(date="07/02/2024"), ops_row()))
        proposals = propose_links(snapshot)
        self.assertEqual(kinds(proposals), ["new", "new", "repeat"])
        self.assertEqual(proposals[2].repeats_line, 2)
        copy = snapshot.rows.get(line=4)
        with self.assertRaisesMessage(ValidationError, "repeats row 2"):
            approve_link(row=copy, actor=self.reviewer, reason="Looks new")
        self.assertFalse(RowIdentityLink.objects.filter(row=copy).exists())


class PortTests(CrosswalkTestCase):
    def test_ports_are_proposed_and_created_with_provenance(self):
        snapshot, _ = self.stage(
            ports_csv("Port fictif A,36° 48.0,10° 12.0", "Port fictif B,39° 26.32,0° 18.59"),
            sheet="Data_ports",
        )
        clear, ambiguous = snapshot.rows.order_by("line")
        self.assertEqual(kinds(propose_ports(snapshot)), ["new_port", "blocked"])
        alias = approve_port_alias(
            source=self.source,
            label="Port fictif A",
            actor=self.reviewer,
            reason="Port list",
            row=clear,
        )
        port = alias.ports.get()
        self.assertEqual(port.name, "Port fictif A")
        self.assertEqual(port.created_from, clear)
        self.assertAlmostEqual(port.location.x, 10.2)
        self.assertAlmostEqual(port.location.y, 36.8)
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source,
                label="Port fictif B",
                actor=self.reviewer,
                reason="No position",
                row=ambiguous,
            )
        west = approve_port_alias(
            source=self.source,
            label="Port fictif B",
            actor=self.reviewer,
            reason="West of Greenwich, checked on a chart",
            row=ambiguous,
            location=Point(-0.3098, 39.4387, srid=4326),
        )
        self.assertLess(west.ports.get().location.x, 0)
        self.assertEqual(kinds(propose_ports(snapshot)), ["linked", "linked"])
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source,
                label="Port fictif A",
                actor=self.reviewer,
                reason="Twice",
                ports=[port],
            )

    def test_existing_port_with_same_name_is_suggested_not_linked(self):
        Port.objects.create(name="Port Fictif A")
        snapshot, _ = self.stage(
            ports_csv("port fictif a,36° 48.0,10° 12.0", "Port fictif Z,36° 49.0,10° 13.0"),
            sheet="Data_ports",
        )
        proposal, similar = propose_ports(snapshot)
        # A similar name is never suggested: only exact case-insensitive equality.
        self.assertEqual(similar.kind, "new_port")
        self.assertEqual(proposal.kind, "existing_port")
        self.assertEqual(PortAlias.objects.count(), 0)

    def test_disembarkation_labels_are_listed_until_aliased(self):
        port = Port.objects.create(name="Port fictif")
        self.stage(
            ops_csv(
                ops_row(Port_disembarkation="Port fictif"),
                ops_row(date="04/02/2024", Port_disembarkation="Port fictif"),
                ops_row(date="05/02/2024", Port_disembarkation="Autre port"),
                ops_row(date="06/02/2024", Port_disembarkation="n/a"),
            )
        )
        labels = unresolved_port_labels(self.source)
        self.assertEqual(
            [(item.label, item.rows, item.suggested_port_id) for item in labels],
            [("Autre port", 1, None), ("Port fictif", 2, port.pk)],
        )
        approve_port_alias(
            source=self.source,
            label="Port fictif",
            actor=self.reviewer,
            reason="Same port",
            ports=[port],
        )
        self.assertEqual(
            [item.label for item in unresolved_port_labels(self.source)], ["Autre port"]
        )

    def test_alias_needs_permission_and_reason(self):
        port = Port.objects.create(name="Port fictif")
        with self.assertRaises(PermissionDenied):
            approve_port_alias(
                source=self.source,
                label="Port fictif",
                actor=self.outsider,
                reason="x",
                ports=[port],
            )
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source,
                label="Port fictif",
                actor=self.reviewer,
                reason="",
                ports=[port],
            )


class PortLabelReadingTests(CrosswalkTestCase):
    """Port_disembarkation also holds several ports, transfer vessels and regions."""

    def test_label_with_several_ports(self):
        first = Port.objects.create(name="Port fictif A")
        second = Port.objects.create(name="Port fictif B")
        alias = approve_port_alias(
            source=self.source,
            label="Port fictif A & Port fictif B",
            actor=self.reviewer,
            reason="Two disembarkation ports",
            ports=[first, second],
        )
        self.assertEqual(alias.target, "ports")
        self.assertEqual(set(alias.ports.all()), {first, second})

    def test_vessel_and_region_labels_are_not_ports(self):
        vessel = Vessel.objects.create(name="Navire fictif")
        transfer = classify_port_label(
            source=self.source,
            label="Navire fictif",
            actor=self.reviewer,
            reason="Transfer",
            vessel=vessel,
        )
        region = classify_port_label(
            source=self.source, label="Région fictive", actor=self.reviewer, reason="A region"
        )
        self.assertEqual((transfer.target, transfer.vessel), ("vessel", vessel))
        self.assertEqual((region.target, region.ports.count()), ("not_a_port", 0))
        self.stage(ops_csv(ops_row(Port_disembarkation="Navire fictif")))
        self.assertEqual(unresolved_port_labels(self.source), [])

    def test_database_refuses_inconsistent_vessel_target(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PortAlias.objects.create(
                source=self.source,
                label="x",
                target="vessel",
                approved_by=self.reviewer,
                reason="r",
            )

    def test_existing_ports_and_new_port_inputs_are_exclusive(self):
        port = Port.objects.create(name="Port fictif")
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source,
                label="Port fictif",
                actor=self.reviewer,
                reason="Both",
                ports=[port],
                location=Point(1, 1, srid=4326),
            )


class ReviewFindingTests(CrosswalkTestCase):
    """Regressions for the independent review of the crosswalk slice."""

    def link_all(self, snapshot, identity=None):
        return [
            approve_link(row=row, actor=self.reviewer, reason="r", identity=identity)
            for row in snapshot.rows.order_by("line")
        ]

    def test_identity_claimed_by_two_rows_is_never_carried(self):
        first, _ = self.stage(ops_csv(ops_row(nb_survivor="40")))
        (link,) = self.link_all(first)
        corrected, _ = self.stage(ops_csv(ops_row(nb_survivor="42")))
        self.link_all(corrected, identity=link.identity)
        both, _ = self.stage(ops_csv(ops_row(nb_survivor="40"), ops_row(nb_survivor="42")))
        self.assertEqual(kinds(propose_links(both)), ["candidates", "candidates"])
        self.assertEqual(approve_exact_carries(snapshot=both, actor=self.reviewer, reason="r"), 0)

    def test_content_seen_on_two_identities_is_never_carried(self):
        first, _ = self.stage(ops_csv(ops_row()))
        (link_a,) = self.link_all(first)
        second, _ = self.stage(ops_csv(ops_row(), ops_row(boat_type="Bateau fictif")))
        rows = list(second.rows.order_by("line"))
        approve_link(row=rows[0], actor=self.reviewer, reason="Distinct rescue", identity=None)
        approve_link(row=rows[1], actor=self.reviewer, reason="r", identity=link_a.identity)
        third, _ = self.stage(ops_csv(ops_row(), ops_row(date="09/02/2024")))
        self.assertEqual(kinds(propose_links(third))[0], "candidates")

    def test_rows_in_error_count_when_checking_uniqueness(self):
        first, _ = self.stage(ops_csv(ops_row(image_src="?")))
        self.link_all(first)
        second, _ = self.stage(
            ops_csv(ops_row(image_src="javascript:alert(1)"), ops_row(image_src="?"))
        )
        self.assertEqual(kinds(propose_links(second)), ["blocked", "candidates"])

    def test_manual_choice_is_recorded_as_reviewed_even_with_equal_content(self):
        first, _ = self.stage(ops_csv(ops_row()))
        (link,) = self.link_all(first)
        doubled, _ = self.stage(ops_csv(ops_row(), ops_row()))
        manual = approve_link(
            row=doubled.rows.order_by("line").first(),
            actor=self.reviewer,
            reason="Picked by hand",
            identity=link.identity,
        )
        self.assertEqual(manual.match, "reviewed_match")

    def test_model_guards_links_written_outside_services(self):
        first, _ = self.stage(ops_csv(ops_row()))
        other, _ = self.stage(ops_csv(ops_row(date="04/02/2024")))
        (link,) = self.link_all(first)
        with self.assertRaises(ValidationError):
            RowIdentityLink.objects.create(
                row=other.rows.get(),
                snapshot=first,
                identity=link.identity,
                match="reviewed_match",
                approved_by=self.reviewer,
                reason="bypass",
            )

    def test_blank_reasons_are_refused_by_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SourceIdentity.objects.create(
                source=self.source, sheet="Data_operations", created_by=self.reviewer, reason="  "
            )
        with self.assertRaises(ValidationError):
            approve_link(
                row=self.stage(ops_csv(ops_row()))[0].rows.get(), actor=self.reviewer, reason=None
            )

    def test_same_bytes_under_a_new_contract_version_is_a_new_snapshot(self):
        content = ops_csv(ops_row())
        first, _ = self.stage(content)
        contract = load_contract()
        contract["version"] = "sheets-observed-v2"
        with mock.patch("catalog.review.crosswalk.load_contract", return_value=contract):
            second, created = self.stage(content)
        self.assertTrue(created)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.contract_version, "sheets-observed-v2")

    def test_unknown_sheet_is_a_validation_error(self):
        with self.assertRaises(ValidationError):
            self.stage(ops_csv(ops_row()), sheet="Nope")

    def test_unresolved_labels_count_the_latest_export_only(self):
        rows = [
            ops_row(date=f"0{day}/02/2024", Port_disembarkation="Port fictif") for day in (1, 2)
        ]
        self.stage(ops_csv(*rows))
        self.stage(ops_csv(*rows, ops_row(date="03/02/2024", Port_disembarkation="Port fictif")))
        self.assertEqual(
            [(i.label, i.rows) for i in unresolved_port_labels(self.source)], [("Port fictif", 3)]
        )

    def test_new_port_needs_explicit_inputs_and_keeps_location_provenance(self):
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source, label="Port fictif", actor=self.reviewer, reason="r"
            )
        typed = approve_port_alias(
            source=self.source,
            label="Port fictif",
            actor=self.reviewer,
            reason="Position read on a chart",
            location=Point(12.5, 37.5, srid=4326),
        )
        self.assertEqual(typed.ports.get().location_source, "reviewer")
        snapshot, _ = self.stage(
            ports_csv("Port fictif A,36° 48.0,10° 12.0", "Port fictif B,0,0"), sheet="Data_ports"
        )
        from_row, null_island = snapshot.rows.order_by("line")
        alias = approve_port_alias(
            source=self.source, label="Port fictif A", actor=self.reviewer, reason="r", row=from_row
        )
        self.assertEqual(alias.ports.get().location_source, "sheet_row")
        with self.assertRaises(ValidationError):
            approve_port_alias(
                source=self.source,
                label="Port fictif B",
                actor=self.reviewer,
                reason="r",
                row=null_island,
            )

    def test_port_used_by_an_alias_cannot_be_deleted(self):
        port = Port.objects.create(name="Port fictif")
        approve_port_alias(
            source=self.source, label="Port fictif", actor=self.reviewer, reason="r", ports=[port]
        )
        with self.assertRaises(ProtectedError):
            port.delete()
