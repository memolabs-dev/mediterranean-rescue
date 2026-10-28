"""Split Sheets modules keep the existing public Python API and privacy boundary."""

import unittest

from catalog import sheets, sheets_cells, sheets_reporting


class SheetsBoundaryTests(unittest.TestCase):
    def test_parser_exports_are_compatible(self):
        for name in (
            "CellError",
            "load_contract",
            "parse_coordinate",
            "parse_date",
            "parse_count",
            "parse_decimal",
            "check_url",
            "split_list",
            "scan_quoting",
        ):
            self.assertIs(getattr(sheets, name), getattr(sheets_cells, name))

    def test_rendering_contract_remains_private(self):
        self.assertIs(sheets.render_report, sheets_reporting.render_report)
        self.assertEqual(set(sheets_reporting.TEXT), {"en", "fr"})
        result = sheets.diagnose(b"date,type_ops\n03/02/2024,Rescue\n", "Data_operations")
        report = sheets.render_report(result, language="fr")
        self.assertNotIn("03/02/2024", report)
        self.assertNotIn("Rescue", report)
