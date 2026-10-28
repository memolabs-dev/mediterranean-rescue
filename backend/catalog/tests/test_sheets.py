"""Offline Sheets diagnostic (D1-D5). Synthetic inputs only; no database is used.

Plain unittest so it runs both under the Django runner in CI and with
`python3 -m unittest` from backend/ on a host without Docker.
"""

import contextlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catalog import sheets, sheets_cells, sheets_reporting
from catalog.sheets import (
    CellError,
    check_url,
    diagnose,
    load_contract,
    main,
    parse_coordinate,
    parse_count,
    parse_date,
    parse_decimal,
    render_report,
    scan_quoting,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sheets"
OPS_HEADER = (
    "date,type_ops,nb_ops,nb_survivor,male,female,under_18,under_18_unacc,under_5,"
    "pregnant_women,latitude,longitude,wind_force,wave_height,boat_type,nb_nationalities,"
    "type_nationalities,transfer_type,Port_disembarkation,image_src,video_srv,"
    "testimony_name,testimony_src"
)
OTHER_HEADER = (
    "date,type,latitude,longitude,wind_force,wave_height,boat_type,death_nb_people,inc_action,"
    "shipwreck_nb,boat_involved,testimony_name,testimony_src,image_src,video_srv"
)


def ops_row(**values):
    names = OPS_HEADER.split(",")
    base = {"date": "03/02/2024", "type_ops": "Rescue", "latitude": "34.5", "longitude": "12.25"}
    base.update(values)
    unknown = set(base) - set(names)
    assert not unknown, unknown
    return ",".join(base.get(name, "") for name in names)


def ops_csv(*rows):
    return ("\n".join([OPS_HEADER, *rows]) + "\n").encode()


def codes(result, line=None):
    return [i["code"] for i in result["issues"] if line is None or i["line"] == line]


class ContractTests(unittest.TestCase):
    def test_contract_covers_inventory_and_marks_unknowns(self):
        contract = load_contract()
        self.assertEqual(contract["status"], "observed_not_association_approved")
        ops = [c["name"] for c in contract["sheets"]["Data_operations"]["columns"]]
        self.assertEqual(sorted(ops), sorted(OPS_HEADER.split(",")))
        other = [c["name"] for c in contract["sheets"]["Other_data"]["columns"]]
        self.assertEqual(other, OTHER_HEADER.split(","))  # positional order of the consumer
        ports = [c["name"] for c in contract["sheets"]["Data_ports"]["columns"]]
        self.assertEqual(ports, ["nom", "latitude", "longitude"])
        definitions = {
            c["name"]: c.get("definition_status")
            for sheet in contract["sheets"].values()
            for c in sheet["columns"]
        }
        for name in ("nb_ops", "wind_force", "shipwreck_nb", "death_nb_people"):
            self.assertEqual(definitions[name], "unknown", name)
        for sheet in ("Other_data", "Data_ports"):
            statuses = {c["name_status"] for c in contract["sheets"][sheet]["columns"]}
            self.assertEqual(statuses, {"snapshot_2026_10_24"})

    def test_module_has_no_django_database_or_network_dependency(self):
        source = Path(sheets.__file__).read_text(encoding="utf-8")
        for forbidden in ("django", "socket", "urllib.request", "http.client", "requests"):
            self.assertNotIn(f"import {forbidden}", source)
            self.assertNotIn(f"from {forbidden}", source)


class StructureTests(unittest.TestCase):
    """D1: explicit columns, drift reported, received cells kept."""

    def test_duplicate_header_blocks_mapping_but_keeps_raw_cells(self):
        content = (
            "date,date,type_ops,latitude,longitude\n03/02/2024,04/02/2024,Rescue,1,2\n"
        ).encode()
        result = diagnose(content, "Data_operations")
        self.assertIn("duplicate_header", codes(result, 1))
        self.assertEqual(result["status"]["normalization"], "blocked")
        self.assertEqual(
            result["rows"][0]["raw_cells"], ["03/02/2024", "04/02/2024", "Rescue", "1", "2"]
        )
        self.assertIsNone(result["rows"][0]["candidate"])

    def test_unknown_column_is_drift_and_value_is_kept(self):
        content = (OPS_HEADER + ",new_field\n" + ops_row() + ",secret-value\n").encode()
        result = diagnose(content, "Data_operations")
        unknown = [i for i in result["issues"] if i["code"] == "unknown_column"]
        self.assertEqual(unknown[0]["column"], 24)
        self.assertIsNone(unknown[0]["field"])
        self.assertEqual(result["rows"][0]["raw_cells"][-1], "secret-value")
        self.assertEqual(result["status"]["normalization"], "blocked")

    def test_missing_required_and_optional_columns(self):
        result = diagnose(b"date,type_ops,latitude\n03/02/2024,Rescue,1\n", "Data_operations")
        self.assertIn("missing_required_column", codes(result))
        self.assertIn("optional_column_absent", codes(result))
        self.assertIsNone(result["rows"][0]["candidate"])

    def test_extra_or_missing_cells_are_never_shifted(self):
        result = diagnose(ops_csv(ops_row() + ",extra", "03/02/2024,Rescue"), "Data_operations")
        self.assertEqual(codes(result, 2), ["extra_cells"])
        self.assertEqual(codes(result, 3), ["missing_cells"])
        self.assertTrue(all(row["candidate"] is None for row in result["rows"]))
        self.assertEqual(result["rows"][0]["raw_cells"][-1], "extra")

    def test_trailing_anonymous_column_ignored_only_when_empty(self):
        content = (
            OPS_HEADER
            + ",,\n"
            + ops_row()
            + ",,\n"
            + ops_row(date="04/02/2024")
            + ",oops,\n"
            + ops_row(date="05/02/2024")
            + ",again,\n"
        ).encode()
        result = diagnose(content, "Data_operations")
        anonymous = [i for i in result["issues"] if i["code"] == "unnamed_column_has_value"]
        # Reported once per column, as a warning: mapped columns are unaffected and kept.
        self.assertEqual([(i["severity"], i["column"]) for i in anonymous], [("warning", 24)])
        self.assertEqual(result["rows"][1]["raw_cells"][23], "oops")
        self.assertEqual(result["status"]["normalization"], "needs_review")

    def test_malformed_quotes_are_rejected_with_location(self):
        self.assertEqual(scan_quoting('a,b\nx,y"z\n'), ("quote_in_unquoted_field", 2))
        self.assertEqual(scan_quoting('a,b\n"x"y,z\n'), ("text_after_closing_quote", 2))
        self.assertEqual(
            scan_quoting('a,b\r\n1,2\r\n"open,3\r\n4,5'), ("unterminated_quoted_field", 3)
        )
        self.assertIsNone(scan_quoting('a,b\n"x ""quoted""",y\n"multi\nline",z\n'))
        result = diagnose(ops_csv(ops_row(boat_type='Rub"ber')), "Data_operations")
        self.assertEqual(result["status"]["source_read"], "rejected")
        self.assertEqual(result["rows"], [])
        self.assertEqual(codes(result), ["quote_in_unquoted_field"])

    def test_positional_sheet_order_drift_is_flagged(self):
        names = OTHER_HEADER.split(",")
        names[2], names[3] = names[3], names[2]
        result = diagnose((",".join(names) + "\n").encode(), "Other_data")
        self.assertIn("column_order_differs_from_consumer", codes(result))


class NormalizationTests(unittest.TestCase):
    """D2: dates, numbers, coordinates and links without invented values."""

    def test_dates(self):
        self.assertEqual(parse_date("29/02/2024", "DD/MM/YYYY"), "2024-02-29")
        self.assertEqual(parse_date("01-04-2024", "DD-MM-YYYY"), "2024-04-01")
        for value, code in [
            ("29/02/2023", "impossible_date"),
            ("31/04/2024", "impossible_date"),
            ("2024-02-03", "invalid_date_format"),
            ("03/02/24", "invalid_date_format"),
        ]:
            with self.assertRaisesRegex(CellError, code):
                parse_date(value, "DD/MM/YYYY")
        with self.assertRaisesRegex(CellError, "date_format_of_other_sheet"):
            parse_date("03-02-2024", "DD/MM/YYYY")
        with self.assertRaisesRegex(CellError, "date_format_of_other_sheet"):
            parse_date("03/02/2024", "DD-MM-YYYY")

    def test_counts_unknown_stays_null_and_zero_stays_zero(self):
        self.assertEqual(parse_count("0", 100000), 0)
        for value, code in [
            ("-2", "negative_count"),
            ("1.5", "fractional_count"),
            ("1,5", "fractional_count"),
            ("dix", "invalid_count"),
            ("100001", "count_above_limit"),
        ]:
            with self.assertRaisesRegex(CellError, code):
                parse_count(value, 100000)
        result = diagnose(
            ops_csv(
                ops_row(nb_survivor="0", male="n/a", female="", under_18="Inconnu", under_5="-")
            ),
            "Data_operations",
        )
        candidate = result["rows"][0]["candidate"]
        self.assertEqual(candidate["nb_survivor"], 0)
        for name in ("male", "female", "under_18", "under_5", "pregnant_women"):
            self.assertIsNone(candidate[name], name)

    def test_decimals_are_exact(self):
        self.assertEqual(parse_decimal("1,5"), "1.5")
        self.assertEqual(parse_decimal("0.10"), "0.10")
        with self.assertRaisesRegex(CellError, "negative_decimal"):
            parse_decimal("-1")
        with self.assertRaisesRegex(CellError, "invalid_decimal"):
            parse_decimal("1.2.3")

    def test_coordinates(self):
        self.assertEqual(parse_coordinate("34.5", "latitude"), ("34.5", "decimal_degrees"))
        self.assertEqual(parse_coordinate("36,9", "latitude"), ("36.9", "decimal_degrees_comma"))
        self.assertEqual(parse_coordinate("-12.25", "longitude")[0], "-12.25")
        value, fmt = parse_coordinate("35°30.5'N", "latitude")
        self.assertEqual((value, fmt), ("35.5083333333", "degrees_decimal_minutes_hemisphere"))
        self.assertEqual(parse_coordinate("12°15'W", "longitude")[0], "-12.2500000000")
        self.assertEqual(parse_coordinate("90", "latitude")[0], "90")
        self.assertEqual(parse_coordinate("180°0'E", "longitude")[0], "180.0000000000")
        for value, axis, code in [
            ("90.00000000000000000001", "latitude", "coordinate_out_of_range"),
            ("-180.000000000000000000001", "longitude", "coordinate_out_of_range"),
            ("90°0.0000000001'N", "latitude", "coordinate_out_of_range"),
            ("35°60'N", "latitude", "coordinate_minutes_out_of_range"),
            ("35°30'E", "latitude", "coordinate_axis_mismatch"),
            ("12°30'N", "longitude", "coordinate_axis_mismatch"),
            ("3530N", "latitude", "unsupported_coordinate_format"),
            ("-35°30'N", "latitude", "unsupported_coordinate_format"),
            ("nord", "latitude", "invalid_coordinate"),
        ]:
            with self.assertRaisesRegex(CellError, code, msg=value):
                parse_coordinate(value, axis)

    def test_position_pair_and_absence(self):
        result = diagnose(
            ops_csv(
                ops_row(latitude="34.1", longitude=""),
                ops_row(latitude="unknown", longitude="?"),
                ops_row(latitude="0", longitude="0"),
            ),
            "Data_operations",
        )
        self.assertIn("coordinate_pair_incomplete", codes(result, 2))
        self.assertIsNone(result["rows"][0]["candidate"]["position"])
        self.assertIn("missing_position", codes(result, 3))
        self.assertIsNone(result["rows"][1]["candidate"]["position"])
        self.assertIn("coordinate_zero_zero", codes(result, 4))

    def test_links(self):
        self.assertEqual(check_url("https://example.org/a.jpg"), "https://example.org/a.jpg")
        for value, code in [
            ("javascript:alert(1)", "unsafe_url_scheme"),
            ("file:///etc/passwd", "unsafe_url_scheme"),
            ("https://user:secret@example.org/x", "url_with_credentials"),
            ("https://example.org/a b", "invalid_url"),
            ("https://example.org:99999/", "invalid_url"),
            ("https:///nohost", "invalid_url"),
        ]:
            with self.assertRaisesRegex(CellError, code, msg=value):
                check_url(value)

    def test_testimonies_pair_only_when_aligned(self):
        result = diagnose(
            ops_csv(
                ops_row(testimony_name="A;B", testimony_src="https://example.org/a"),
                ops_row(
                    testimony_name="A;", testimony_src="https://example.org/a;https://example.org/b"
                ),
                ops_row(testimony_name="A", testimony_src="https://example.org/a"),
            ),
            "Data_operations",
        )
        self.assertIn("testimony_lists_misaligned", codes(result, 2))
        self.assertIsNone(result["rows"][0]["candidate"]["testimonies"])
        self.assertIn("testimony_pair_incomplete", codes(result, 3))
        self.assertEqual(len(result["rows"][1]["candidate"]["testimonies"]), 1)
        self.assertEqual(
            result["rows"][2]["candidate"]["testimonies"],
            [{"label": "A", "url": "https://example.org/a"}],
        )

    def test_review_hints_never_correct_values(self):
        result = diagnose(
            ops_csv(
                ops_row(
                    nb_survivor="3",
                    under_18="5",
                    type_nationalities="Pays A;Pays B",
                )
            ),
            "Data_operations",
        )
        candidate = result["rows"][0]["candidate"]
        self.assertIn("subpopulation_exceeds_total", codes(result, 2))
        self.assertEqual((candidate["nb_survivor"], candidate["under_18"]), (3, 5))
        self.assertEqual(candidate["type_nationalities"], ["Pays A", "Pays B"])

    def test_deaths_never_feed_survivors_and_kinds_are_distinct(self):
        content = (OTHER_HEADER + "\n02/04/2024,Dead & Missing,-,-,,,,3,,,,,,,\n").encode()
        candidate = diagnose(content, "Other_data")["rows"][0]["candidate"]
        self.assertEqual(candidate["kind"], "dead_missing")
        self.assertEqual(candidate["death_nb_people"], 3)
        self.assertNotIn("nb_survivor", candidate)
        result = diagnose(ops_csv(ops_row(type_ops="Shipwreck")), "Data_operations")
        self.assertIn("unknown_kind", codes(result, 2))
        self.assertIsNone(result["rows"][0]["candidate"]["kind"])


class ReviewRegressionTests(unittest.TestCase):
    """Defects found by the independent review of this slice."""

    def test_file_cut_on_a_cell_boundary_is_not_reported_complete(self):
        full = b"nom,latitude,longitude\r\nP,35.5,14.25\r\nQ,36.1,23.456\r\n"
        self.assertEqual(diagnose(full, "Data_ports")["status"]["source_read"], "complete")
        for cut in (2, 4, 6):
            result = diagnose(full[:-cut], "Data_ports")
            self.assertEqual(result["status"]["source_read"], "end_unverified", cut)
            self.assertIn("last_record_unterminated", codes(result))
            self.assertNotIn("ends with a line ending", render_report(result))

    def test_very_long_numeric_cells_are_anomalies_not_crashes(self):
        long_number = "1." + "1" * 5000
        result = diagnose(
            ops_csv(ops_row(latitude=long_number, nb_survivor="9" * 5000, wave_height=long_number)),
            "Data_operations",
        )
        self.assertIn("invalid_coordinate", codes(result, 2))
        self.assertIn("invalid_count", codes(result, 2))
        self.assertIn("invalid_decimal", codes(result, 2))

    def test_unknown_lists_stay_null(self):
        content = (OTHER_HEADER + "\n01/04/2024,Incident,34,13,,,,,,,,n/a,n/a,unknown,?\n").encode()
        candidate = diagnose(content, "Other_data")["rows"][0]["candidate"]
        for name in ("testimonies", "image_src", "video_srv"):
            self.assertIsNone(candidate[name], name)
        result = diagnose(
            ops_csv(ops_row(nb_nationalities="2", type_nationalities="?")), "Data_operations"
        )
        self.assertIsNone(result["rows"][0]["candidate"]["type_nationalities"])
        known_empty = diagnose(ops_csv(ops_row(testimony_name="A")), "Data_operations")
        self.assertIn("testimony_lists_misaligned", codes(known_empty, 2))

    def test_comma_followed_by_three_digits_is_flagged(self):
        result = diagnose(
            ops_csv(ops_row(wind_force='"1,500"', wave_height='"1,5"')), "Data_operations"
        )
        flagged = [
            i["field"] for i in result["issues"] if i["code"] == "decimal_comma_or_thousands"
        ]
        self.assertEqual(flagged, ["wind_force"])
        self.assertEqual(result["rows"][0]["candidate"]["wind_force"], "1.500")

    def test_rejection_after_the_header_counts_as_file_error(self):
        result = diagnose(b'nom,latitude,longitude\nA,1,2\nB,3,4\nC,5,6\nP,"1', "Data_ports")
        self.assertEqual(result["counts"]["file_errors"], 1)
        self.assertEqual(result["counts"]["errors"], 1)

    def test_missing_column_on_positional_sheet_breaks_consumer_layout(self):
        names = [name for name in OTHER_HEADER.split(",") if name != "wind_force"]
        result = diagnose((",".join(names) + "\n").encode(), "Other_data")
        self.assertIn("column_order_differs_from_consumer", codes(result))

    def test_url_list_with_invalid_fragment_keeps_no_partial_list(self):
        result = diagnose(
            ops_csv(ops_row(image_src="https://example.org/i;jsessionid=1")), "Data_operations"
        )
        self.assertIn("unsafe_url_scheme", codes(result, 2))
        self.assertIsNone(result["rows"][0]["candidate"]["image_src"])


class RealExportFormatTests(unittest.TestCase):
    """Formats seen in the public export of 2026-10-24; inputs here are fictitious."""

    REGION = load_contract()["hemisphere_inference"]

    def test_hemisphere_inferred_only_when_one_reading_is_in_region(self):
        self.assertEqual(
            parse_coordinate("35° 30.5", "latitude", self.REGION),
            ("35.5083333333", "degrees_decimal_minutes_inferred_hemisphere"),
        )
        self.assertEqual(parse_coordinate("15° 0", "longitude", self.REGION)[0], "15.0000000000")
        for value, axis, code in [
            ("0° 18.59", "longitude", "hemisphere_ambiguous"),  # Valencia lies west
            ("5° 21.43", "longitude", "hemisphere_ambiguous"),
            ("60° 0", "latitude", "coordinate_outside_region"),
            ("35° 60", "latitude", "coordinate_minutes_out_of_range"),
        ]:
            with self.assertRaisesRegex(CellError, code, msg=value):
                parse_coordinate(value, axis, self.REGION)
        with self.assertRaisesRegex(CellError, "hemisphere_missing"):
            parse_coordinate("35° 30.5", "latitude")
        self.assertEqual(
            parse_coordinate("0° 18.59'W", "longitude", self.REGION)[0], "-0.3098333333"
        )

    def test_region_inference_is_reported_once_and_ambiguity_blocks_the_row(self):
        content = "nom,latitude,longitude\nA,35° 30.5,14° 15.25\nB,39° 26.32,0° 18.59\n".encode()
        result = diagnose(content, "Data_ports")
        self.assertEqual(codes(result).count("hemisphere_inferred_from_region"), 1)
        self.assertEqual(codes(result, 3), ["hemisphere_ambiguous"])
        self.assertIsNone(result["rows"][1]["candidate"]["position"])
        position = result["rows"][0]["candidate"]["position"]
        self.assertEqual(
            (position["latitude"], position["longitude"]), ("35.5083333333", "14.2541666667")
        )

    def test_other_data_dates_use_slashes(self):
        content = (OTHER_HEADER + "\n21/06/2022,Incident,33° 55,13° 55,,,,,,,,,,,\n").encode()
        candidate = diagnose(content, "Other_data")["rows"][0]["candidate"]
        self.assertEqual(candidate["occurred_on"], "2022-06-21")


class ReportLanguageTests(unittest.TestCase):
    def test_every_language_explains_the_same_codes(self):
        self.assertEqual(sheets.DEFAULT_LANGUAGE, "en")
        self.assertEqual(set(sheets.EXPLANATIONS["en"]), set(sheets.EXPLANATIONS["fr"]))
        self.assertEqual(set(sheets.TEXT["en"]), set(sheets.TEXT["fr"]))
        self.assertEqual(set(sheets.STATUS_TEXT["en"]), set(sheets.STATUS_TEXT["fr"]))

    def test_every_emitted_code_is_explained(self):
        source = "\n".join(
            Path(module.__file__).read_text(encoding="utf-8")
            for module in (sheets, sheets_cells, sheets_reporting)
        )
        emitted = set(
            re.findall(
                r'(?:CellError|issue|flag)\(\s*"(?:error|warning)?"?,?\s*"([a-z_0-9]+)"', source
            )
        )
        emitted |= set(re.findall(r'CellError\("([a-z_0-9]+)"\)', source))
        self.assertTrue(emitted)
        self.assertLessEqual(emitted, set(sheets.EXPLANATIONS["en"]))


class ProvenanceTests(unittest.TestCase):
    """D3: exact provenance, determinism, no merge, no inferred identity."""

    def test_bom_multiline_cell_and_physical_lines(self):
        result = diagnose((FIXTURES / "synthetic-Other_data.csv").read_bytes(), "Other_data")
        self.assertTrue(result["snapshot"]["utf8_bom"] is False)
        first = result["rows"][0]
        self.assertEqual((first["line"], first["end_line"]), (2, 3))
        self.assertEqual(first["raw_cells"][8], "Action fictive\r\nsur deux lignes")
        self.assertEqual(result["rows"][1]["line"], 4)
        ports = diagnose((FIXTURES / "synthetic-Data_ports.csv").read_bytes(), "Data_ports")
        self.assertTrue(ports["snapshot"]["utf8_bom"])
        self.assertEqual(ports["header"]["cells"][0], "nom")

    def test_row_ref_identity_and_duplicates(self):
        content = ops_csv(ops_row(), ops_row(date="04/02/2024"), ops_row())
        result = diagnose(content, "Data_operations")
        sha = result["snapshot"]["sha256"]
        self.assertEqual(result["rows"][0]["row_ref"], f"Data_operations@sha256:{sha}#L2")
        self.assertEqual(len(result["rows"]), 3)  # duplicate kept, not merged
        self.assertIn("exact_duplicate_row", codes(result, 4))
        self.assertEqual(result["rows"][2]["duplicate_of_line"], 2)
        self.assertTrue(all(row["identity"] == "unresolved" for row in result["rows"]))
        self.assertTrue(
            all("external_id" not in (row["candidate"] or {}) for row in result["rows"])
        )

    def test_same_bytes_same_result_and_moved_row_changes_only_location(self):
        content = ops_csv(ops_row(), ops_row(date="04/02/2024"))
        self.assertEqual(
            json.dumps(diagnose(content, "Data_operations")),
            json.dumps(diagnose(content, "Data_operations")),
        )
        moved = ops_csv(ops_row(date="04/02/2024"), ops_row())
        a, b = diagnose(content, "Data_operations"), diagnose(moved, "Data_operations")
        self.assertNotEqual(a["snapshot"]["sha256"], b["snapshot"]["sha256"])
        self.assertEqual(a["rows"][0]["candidate"], b["rows"][1]["candidate"])
        self.assertNotEqual(a["rows"][0]["row_ref"], b["rows"][1]["row_ref"])

    def test_blank_rows_counted_and_publication_always_disabled(self):
        result = diagnose(
            ops_csv(ops_row(), "", ",,,", ops_row(date="04/02/2024")), "Data_operations"
        )
        self.assertEqual(result["counts"]["blank_rows_skipped"], 2)
        self.assertEqual(result["counts"]["records_read"], 4)
        self.assertEqual(result["counts"]["rows_diagnosed"], 2)
        self.assertEqual(result["status"]["publication"], "disabled")
        self.assertEqual(result["status"]["normalization"], "needs_review")


class BoundsTests(unittest.TestCase):
    """D4: bounded input, never a pretended complete read."""

    def test_invalid_utf8_and_too_large(self):
        result = diagnose(b"date\n\xff\n", "Data_operations")
        self.assertEqual(
            (result["status"]["source_read"], codes(result)), ("rejected", ["invalid_utf8"])
        )
        contract = load_contract()
        contract["input"]["max_bytes"] = 10
        result = diagnose(b"x" * 11, "Data_operations", contract)
        self.assertEqual(codes(result), ["snapshot_too_large"])
        self.assertEqual(result["status"]["source_read"], "rejected")

    def test_too_many_records_is_partial_and_keeps_no_candidates(self):
        contract = load_contract()
        contract["input"]["max_records"] = 2
        result = diagnose(ops_csv(ops_row(), ops_row(), ops_row()), "Data_operations", contract)
        self.assertEqual(result["status"]["source_read"], "partial")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["status"]["normalization"], "blocked")
        self.assertIn("too_many_records", codes(result))

    def test_a_row_with_too_many_cells_stops_the_reading(self):
        # Security audit of 25 October 2026: one huge row must not fill the worker's memory.
        content = ops_csv(ops_row()) + (",x" * 300).encode() + b"\n"
        result = diagnose(content, "Data_operations")
        self.assertEqual(result["status"]["source_read"], "partial")
        self.assertEqual(result["rows"], [])
        self.assertIn("too_many_columns", codes(result))

    def test_interrupted_csv_is_never_complete(self):
        truncated = ops_csv(ops_row())[:-1] + b'\n03/02/2024,Rescue,"interrupted'
        result = diagnose(truncated, "Data_operations")
        self.assertNotEqual(result["status"]["source_read"], "complete")
        self.assertEqual(codes(result), ["unterminated_quoted_field"])

    def test_default_limits_match_specification(self):
        self.assertEqual(load_contract()["input"]["max_bytes"], 5 * 1024 * 1024)
        self.assertEqual(load_contract()["input"]["max_records"], 10000)


SENTINELS = ("Témoin-sentinelle-XYZ", "https://example.org/sentinel-url", "Port-sentinelle")


class CliTests(unittest.TestCase):
    """D4/D5: private bounded CLI, no overwrite, no source value outside private files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input = self.root / "export.csv"
        self.input.write_bytes(
            ops_csv(
                ops_row(
                    testimony_name=SENTINELS[0],
                    testimony_src=SENTINELS[1],
                    Port_disembarkation=SENTINELS[2],
                ),
                ops_row(date="31/02/2024", image_src="javascript:" + SENTINELS[0]),
            )
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_package_contents_modes_and_privacy(self):
        output = self.root / "private" / "run-1"
        code, out, err = self.run_cli(
            "--sheet", "Data_operations", "--input", str(self.input), "--output-dir", str(output)
        )
        self.assertEqual(code, sheets.EXIT_BLOCKED)
        self.assertEqual(
            sorted(p.name for p in output.iterdir()),
            [".gitignore", "MANIFEST.json", "diagnostic.json", "report.md", "snapshot.csv"],
        )
        self.assertEqual((output / "snapshot.csv").read_bytes(), self.input.read_bytes())
        self.assertEqual((output / ".gitignore").read_text(), "*\n")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            for path in output.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)
        report = (output / "report.md").read_text()
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, out + err + report)
        self.assertIn(SENTINELS[0], (output / "diagnostic.json").read_text())
        self.assertIn("Unqualified source", report)
        manifest = json.loads((output / "MANIFEST.json").read_text())
        self.assertEqual(
            (manifest["package_complete"], manifest["source_read"]), (True, "complete")
        )
        self.assertEqual(manifest["publication"], "disabled")
        self.assertIn("source_read=complete", out)
        self.assertIn("impossible_date", report)

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "run"
        output.mkdir()
        (output / "keep.txt").write_text("previous")
        code, out, err = self.run_cli(
            "--sheet", "Data_operations", "--input", str(self.input), "--output-dir", str(output)
        )
        self.assertEqual(code, sheets.EXIT_IO)
        self.assertEqual([p.name for p in output.iterdir()], ["keep.txt"])
        self.assertEqual((output / "keep.txt").read_text(), "previous")
        # The writer itself refuses too, in case the directory appears after the CLI check.
        result = diagnose(self.input.read_bytes(), "Data_operations")
        with self.assertRaises(FileExistsError):
            sheets.write_package(output, self.input.read_bytes(), result)
        self.assertEqual([p.name for p in output.iterdir()], ["keep.txt"])

    def test_write_failure_leaves_identifiable_incomplete_package(self):
        output = self.root / "run"
        real = sheets._private_write

        def failing(path, data):
            if path.name == "report.md":
                raise OSError("disk full")
            real(path, data)

        with mock.patch.object(sheets, "_private_write", failing):
            code, out, err = self.run_cli(
                "--sheet",
                "Data_operations",
                "--input",
                str(self.input),
                "--output-dir",
                str(output),
            )
        self.assertEqual(code, sheets.EXIT_IO)
        self.assertFalse((output / "MANIFEST.json").exists())
        self.assertTrue((output / ".gitignore").exists())
        self.assertIn("MANIFEST.json absent", err)
        for sentinel in SENTINELS:
            self.assertNotIn(sentinel, out + err)

    def test_oversized_input_refused_without_output(self):
        contract = load_contract()
        contract["input"]["max_bytes"] = 50
        output = self.root / "run"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(
                [
                    "--sheet",
                    "Data_operations",
                    "--input",
                    str(self.input),
                    "--output-dir",
                    str(output),
                ],
                contract,
            )
        self.assertEqual(code, sheets.EXIT_IO)
        self.assertFalse(output.exists())

    def test_usage_error_exit_code(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--sheet", "Nope", "--input", "x", "--output-dir", "y"])
        self.assertEqual(raised.exception.code, sheets.EXIT_USAGE)

    def test_script_runs_without_django(self):
        script = Path(__file__).resolve().parents[3] / "scripts" / "diagnose_sheets.py"
        if not script.exists():
            self.skipTest("scripts/ is not shipped in the backend image")
        output = self.root / "run"
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(script),
                "--sheet",
                "Data_ports",
                "--synthetic",
                "--input",
                str(FIXTURES / "synthetic-Data_ports.csv"),
                "--output-dir",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, sheets.EXIT_BLOCKED, completed.stderr)
        self.assertIn("Synthetic data", (output / "report.md").read_text())


class SyntheticDemonstrationTests(unittest.TestCase):
    """D5: the three labelled fixtures trigger their intentional anomalies."""

    def test_operations_fixture(self):
        result = diagnose(
            (FIXTURES / "synthetic-Data_operations.csv").read_bytes(),
            "Data_operations",
            dataset_label="synthetic",
        )
        found = set(result["counts"]["issues_by_code"])
        self.assertLessEqual(
            {
                "impossible_date",
                "negative_count",
                "fractional_count",
                "coordinate_out_of_range",
                "unsafe_url_scheme",
                "testimony_lists_misaligned",
                "date_format_of_other_sheet",
                "unknown_kind",
                "coordinate_minutes_out_of_range",
                "url_with_credentials",
                "exact_duplicate_row",
                "coordinate_pair_incomplete",
                "missing_position",
                "subpopulation_exceeds_total",
            },
            found,
        )
        self.assertEqual(result["counts"]["blank_rows_skipped"], 1)
        candidate = result["rows"][1]["candidate"]
        self.assertEqual(candidate["position"]["latitude"], "35.5083333333")
        self.assertIsNone(candidate["nb_survivor"])
        self.assertIn("Synthetic data", render_report(result))
        self.assertIn("Données synthétiques", render_report(result, language="fr"))

    def test_other_and_ports_fixtures(self):
        other = diagnose((FIXTURES / "synthetic-Other_data.csv").read_bytes(), "Other_data")
        self.assertLessEqual(
            {
                "unnamed_column_has_value",
                "date_format_of_other_sheet",
                "impossible_date",
                "coordinate_out_of_range",
                "missing_position",
            },
            set(other["counts"]["issues_by_code"]),
        )
        self.assertEqual(other["rows"][0]["candidate"]["wave_height"], "2.5")
        ports = diagnose((FIXTURES / "synthetic-Data_ports.csv").read_bytes(), "Data_ports")
        self.assertEqual(ports["rows"][1]["candidate"]["position"]["latitude"], "36.9")
        self.assertIn("missing_cells", codes(ports, 4))


if __name__ == "__main__":
    unittest.main()
