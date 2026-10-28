"""Offline diagnostic of local Sheets CSV exports: contract, candidates, provenance, anomalies.

Standard library only: no Django, no database, no network. Nothing is imported, merged or
published. Raw cells stay in the private JSON and the exact snapshot copy; the Markdown report
holds counts, contract field names and locations only.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .sheets_cells import (
    COORDINATE_DECIMALS,
    MAX_NUMBER_CHARS,
    CellError,
    check_url,
    load_contract,
    parse_coordinate,
    parse_count,
    parse_date,
    parse_decimal,
    scan_quoting,
    split_list,
)
from .sheets_reporting import (
    DEFAULT_LANGUAGE,
    EXPLANATIONS,
    LANGUAGES,
    REPORT_LOCATIONS,
    STATUS_TEXT,
    TEXT,
    render_report,
)

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "sheets-v1.json"
DIAGNOSTIC_FORMAT = 1

EXIT_OK = 0  # package written, no blocking anomaly (rows still need review)
EXIT_IO = 1  # input refused or output impossible; see stderr
EXIT_USAGE = 2  # argparse usage error
EXIT_BLOCKED = 3  # package written, normalization blocked by errors

__all__ = [
    "CONTRACT_PATH",
    "DIAGNOSTIC_FORMAT",
    "EXIT_OK",
    "EXIT_IO",
    "EXIT_USAGE",
    "EXIT_BLOCKED",
    "COORDINATE_DECIMALS",
    "MAX_NUMBER_CHARS",
    "CellError",
    "load_contract",
    "parse_date",
    "parse_count",
    "parse_decimal",
    "parse_coordinate",
    "check_url",
    "split_list",
    "scan_quoting",
    "DEFAULT_LANGUAGE",
    "EXPLANATIONS",
    "LANGUAGES",
    "REPORT_LOCATIONS",
    "STATUS_TEXT",
    "TEXT",
    "diagnose",
    "render_report",
    "write_package",
    "main",
]


class _Diagnostic:
    def __init__(self, content, sheet, contract, dataset_label):
        self.content = content
        self.sheet = sheet
        self.contract = contract
        self.config = contract["sheets"][sheet]
        self.columns = {column["name"]: column for column in self.config["columns"]}
        self.unknown_markers = {marker.casefold() for marker in contract["unknown_markers"]}
        self.sha256 = hashlib.sha256(content).hexdigest()
        self.issues = []
        self.rows = []
        self.blank_rows = 0
        self.records = 0
        self.source_read = "rejected"
        self.header_cells = []
        self.mapping_ok = False
        self.dataset_label = dataset_label
        self.unnamed_values = Counter()
        self.region = contract.get("hemisphere_inference")
        self.inferred_hemispheres = 0

    def issue(self, severity, code, line=None, column=None, field=None):
        self.issues.append(
            {"severity": severity, "code": code, "line": line, "column": column, "field": field}
        )

    def run(self):
        limits = self.contract["input"]
        if len(self.content) > limits["max_bytes"]:
            self.issue("error", "snapshot_too_large")
            return self.result()
        try:
            text = self.content.decode("utf-8")
        except UnicodeDecodeError:
            self.issue("error", "invalid_utf8")
            return self.result()
        if text.startswith("﻿"):
            text = text[1:]
        if "\x00" in text:
            self.issue("error", "nul_byte")
            return self.result()
        quoting = scan_quoting(text)
        if quoting:
            self.issue("error", quoting[0], line=quoting[1])
            return self.result()
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            header = next(reader)
        except StopIteration:
            self.issue("error", "missing_header")
            return self.result()
        except csv.Error:
            self.issue("error", "invalid_csv", line=1)
            return self.result()
        self.header_cells = header
        self.check_header(header)
        seen = {}
        while True:
            start = reader.line_num + 1
            try:
                cells = next(reader)
            except StopIteration:
                break
            except csv.Error:
                self.issue("error", "invalid_csv", line=start)
                self.source_read = "partial"
                self.rows = []
                return self.result()
            self.records += 1
            if len(cells) > limits.get("max_columns", 200):
                # One row of millions of cells would fill the worker's memory (security audit).
                self.issue("error", "too_many_columns", line=start)
                self.source_read = "partial"
                self.rows = []
                return self.result()
            if self.records > limits["max_records"]:
                # No truncated candidate set: the reader stopped, so nothing is kept.
                self.issue("error", "too_many_records", line=start)
                self.source_read = "partial"
                self.rows = []
                return self.result()
            if all(not cell.strip() for cell in cells):
                self.blank_rows += 1
                continue
            self.add_row(cells, start, reader.line_num, seen)
        for column in sorted(self.unnamed_values):
            # Values outside the contract are kept raw; mapped columns are not shifted.
            self.issue("warning", "unnamed_column_has_value", column=column)
        if self.inferred_hemispheres:
            self.issue("warning", "hemisphere_inferred_from_region")
        if text.endswith(("\n", "\r")):
            self.source_read = "complete"
        else:
            # Every byte was read, but a file cut at a cell boundary looks the same as a file
            # without a final line ending: completeness of the last record is not provable.
            self.source_read = "end_unverified"
            if self.records:
                self.issue("warning", "last_record_unterminated", line=reader.line_num)
        if not self.rows and not self.errors():
            self.issue("warning", "no_data_rows")
        return self.result()

    def check_header(self, header):
        named = [(index, name) for index, name in enumerate(header, 1) if name.strip()]
        counts = Counter(name for _, name in named)
        duplicated = {name for name, count in counts.items() if count > 1}
        for index, name in named:
            if name in duplicated:
                self.issue(
                    "error",
                    "duplicate_header",
                    line=1,
                    column=index,
                    field=name if name in self.columns else None,
                )
            elif name not in self.columns:
                self.issue("error", "unknown_column", line=1, column=index)
        present = {name for _, name in named}
        for name, column in self.columns.items():
            if name not in present:
                level = "error" if column.get("required") else "warning"
                code = (
                    "missing_required_column"
                    if column.get("required")
                    else "optional_column_absent"
                )
                self.issue(level, code, line=1, field=name)
        self.mapping_ok = not duplicated and all(
            name in present for name, column in self.columns.items() if column.get("required")
        )
        if self.config["binding"] == "position" and not duplicated:
            expected = [c["name"] for c in self.config["columns"]]
            actual = [name for _, name in named if name in self.columns]
            if actual != expected:
                self.issue("warning", "column_order_differs_from_consumer", line=1)

    def add_row(self, cells, start, end, seen):
        row = {
            "line": start,
            "end_line": end,
            "row_ref": f"{self.sheet}@sha256:{self.sha256}#L{start}",
            "raw_cells": cells,
            "candidate": None,
            "identity": "unresolved",
        }
        self.rows.append(row)
        key = tuple(cells)
        if key in seen:
            self.issue("warning", "exact_duplicate_row", line=start)
            row["duplicate_of_line"] = seen[key]
        else:
            seen[key] = start
        if len(cells) != len(self.header_cells):
            code = "extra_cells" if len(cells) > len(self.header_cells) else "missing_cells"
            self.issue("error", code, line=start)
            return  # no silent shift of cells into other columns
        for index, (name, value) in enumerate(zip(self.header_cells, cells), 1):
            if not name.strip() and value.strip():
                self.unnamed_values[index] += 1
        if not self.mapping_ok:
            return
        raw = {
            name: (index, value)
            for index, (name, value) in enumerate(zip(self.header_cells, cells), 1)
            if name in self.columns
        }
        row["candidate"] = self.normalize(raw, start)

    def normalize(self, raw, line):
        candidate = {}
        values = {}

        def flag(severity, code, name):
            self.issue(
                severity, code, line=line, column=raw[name][0] if name in raw else None, field=name
            )

        for name, column in self.columns.items():
            if name not in raw:
                continue
            value = raw[name][1].strip()
            values[name] = None if value.casefold() in self.unknown_markers else value

        def parsed(name, parser):
            value = values.get(name)
            if value is None:
                return None
            try:
                return parser(value)
            except CellError as exc:
                flag("error", str(exc), name)
                return None

        maximum = self.contract["limits"]["max_count"]
        for name, column in self.columns.items():
            if name not in raw:
                continue
            kind = column["type"]
            if kind == "date":
                candidate["occurred_on"] = parsed(
                    name, lambda v: parse_date(v, self.config["date_format"])
                )
                if values[name] is None:
                    flag("error", "missing_date", name)
            elif kind == "kind":
                value = values[name]
                candidate["kind"] = self.config["kinds"].get(value) if value else None
                if value is None:
                    flag("error", "missing_kind", name)
                elif candidate["kind"] is None:
                    flag("error", "unknown_kind", name)
            elif kind == "count":
                candidate[name] = parsed(name, lambda v: parse_count(v, maximum))
            elif kind == "decimal":
                candidate[name] = parsed(name, parse_decimal)
                if candidate[name] is not None and re.fullmatch(
                    r"[0-9]{1,3},[0-9]{3}", values[name]
                ):
                    flag("warning", "decimal_comma_or_thousands", name)
            elif kind == "text":
                candidate[name] = values[name]
                if column.get("required") and values[name] is None:
                    flag("error", "missing_required_value", name)
            elif kind == "text_list":
                candidate[name] = (
                    [item for item in split_list(values[name]) if item] if values[name] else None
                )
            elif kind == "url_list" and "paired_with" not in column:
                candidate[name] = self.url_list(values[name], name, flag)
        self.testimonies(values, candidate, flag)
        self.position(values, candidate, flag)
        self.relations(candidate, flag)
        return candidate

    def url_list(self, value, name, flag):
        if value is None:
            return None  # unknown, not a known empty list
        urls, valid = [], True
        for item in split_list(value):
            if not item:
                flag("warning", "empty_list_item", name)
                continue
            try:
                urls.append(check_url(item))
            except CellError as exc:
                valid = False
                flag("error", str(exc), name)
        # A ';' inside a URL also splits it; keeping the valid fragments would alter links.
        return urls if valid else None

    def testimonies(self, values, candidate, flag):
        if "testimony_name" not in self.columns:
            return
        candidate["testimonies"] = None
        names, sources = values.get("testimony_name"), values.get("testimony_src")
        if names is None and sources is None:
            return  # unknown or column absent: not a known empty list
        labels = split_list(names) if names is not None else []
        urls = split_list(sources) if sources is not None else []
        if len(labels) != len(urls):
            flag("error", "testimony_lists_misaligned", "testimony_src")
            return  # no pair is guessed from misaligned lists
        candidate["testimonies"] = []
        for label, url in zip(labels, urls):
            if not label or not url:
                flag("error", "testimony_pair_incomplete", "testimony_src")
                continue
            try:
                candidate["testimonies"].append({"label": label, "url": check_url(url)})
            except CellError as exc:
                flag("error", str(exc), "testimony_src")

    def position(self, values, candidate, flag):
        if "latitude" not in values or "longitude" not in values:
            candidate["position"] = None
            return
        lat_raw, lon_raw = values["latitude"], values["longitude"]
        candidate["position"] = None
        if lat_raw is None and lon_raw is None:
            flag("warning", "missing_position", "latitude")
            return
        if (lat_raw is None) != (lon_raw is None):
            flag(
                "error",
                "coordinate_pair_incomplete",
                "latitude" if lat_raw is None else "longitude",
            )
            return
        lat = lon = None
        try:
            lat = parse_coordinate(lat_raw, "latitude", self.region)
        except CellError as exc:
            flag("error", str(exc), "latitude")
        try:
            lon = parse_coordinate(lon_raw, "longitude", self.region)
        except CellError as exc:
            flag("error", str(exc), "longitude")
        if lat is None or lon is None:
            return
        if "inferred" in lat[1] or "inferred" in lon[1]:
            self.inferred_hemispheres += 1
        if Decimal(lat[0]) == 0 and Decimal(lon[0]) == 0:
            flag("warning", "coordinate_zero_zero", "latitude")
        candidate["position"] = {
            "longitude": lon[0],
            "latitude": lat[0],
            "longitude_format": lon[1],
            "latitude_format": lat[1],
            "precision": "unreviewed",
        }

    def relations(self, candidate, flag):
        # Review hints only: nothing is corrected, summed or deduced.
        for name, column in self.columns.items():
            parent = column.get("subset_of")
            if parent and candidate.get(name) is not None and candidate.get(parent) is not None:
                if candidate[name] > candidate[parent]:
                    flag("warning", "subpopulation_exceeds_total", name)

    def errors(self):
        return [issue for issue in self.issues if issue["severity"] == "error"]

    def result(self):
        errors = self.errors()
        error_lines = {issue["line"] for issue in errors}
        row_lines = {row["line"] for row in self.rows}
        warning_lines = {i["line"] for i in self.issues if i["severity"] == "warning"}
        return {
            "diagnostic_format": DIAGNOSTIC_FORMAT,
            "dataset_label": self.dataset_label,
            "contract": {"version": self.contract["version"], "status": self.contract["status"]},
            "snapshot": {
                "sheet": self.sheet,
                "sha256": self.sha256,
                "bytes": len(self.content),
                "utf8_bom": self.content.startswith(b"\xef\xbb\xbf"),
            },
            "status": {
                "source_read": self.source_read,
                "normalization": "blocked" if errors else "needs_review",
                "identity": "unresolved",
                "publication": "disabled",
            },
            "counts": {
                "records_read": self.records,
                "rows_diagnosed": len(self.rows),
                "blank_rows_skipped": self.blank_rows,
                "file_errors": sum(1 for issue in errors if issue["line"] not in row_lines),
                "rows_with_errors": sum(1 for row in self.rows if row["line"] in error_lines),
                "rows_with_warnings": sum(1 for row in self.rows if row["line"] in warning_lines),
                "errors": len(errors),
                "warnings": len(self.issues) - len(errors),
                "issues_by_code": dict(sorted(Counter(i["code"] for i in self.issues).items())),
            },
            "header": {"cells": self.header_cells},
            "rows": self.rows,
            "issues": self.issues,
        }


def diagnose(content, sheet, contract=None, dataset_label="unreviewed"):
    """Diagnose one CSV snapshot held in memory. Deterministic for the same bytes."""
    contract = contract or load_contract()
    if sheet not in contract["sheets"]:
        raise ValueError("unsupported sheet")
    if dataset_label not in ("synthetic", "unreviewed"):
        raise ValueError("unsupported dataset label")
    return _Diagnostic(content, sheet, contract, dataset_label).run()


def _private_write(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def write_package(output_dir, content, result, contract=None, language=DEFAULT_LANGUAGE):
    """Write a new private package. Raises FileExistsError rather than overwrite anything.

    MANIFEST.json is written last: without it the package is incomplete.
    """
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_dir.mkdir(mode=0o700)
    os.chmod(output_dir, 0o700)
    # Written first so raw outputs stay out of Git wherever the directory is.
    _private_write(output_dir / ".gitignore", b"*\n")
    files = {
        "snapshot.csv": content,
        "diagnostic.json": (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(),
        "report.md": render_report(result, contract, language).encode(),
    }
    for name, data in files.items():
        _private_write(output_dir / name, data)
    manifest = {
        "package_complete": True,
        "source_read": result["status"]["source_read"],
        "normalization": result["status"]["normalization"],
        "publication": "disabled",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    _private_write(output_dir / "MANIFEST.json", (json.dumps(manifest, indent=2) + "\n").encode())


def main(argv=None, contract=None):
    contract = contract or load_contract()
    parser = argparse.ArgumentParser(
        description="Diagnose one local CSV export offline. Never imports or publishes.",
        epilog="Exit codes: 0 package written without blocking error, 1 input refused or "
        "output impossible, 2 usage error, 3 package written with blocking errors.",
    )
    parser.add_argument("--sheet", choices=sorted(contract["sheets"]), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="new directory, never overwritten"
    )
    parser.add_argument(
        "--synthetic", action="store_true", help="label an independent fictitious fixture"
    )
    parser.add_argument(
        "--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE, help="report language"
    )
    args = parser.parse_args(argv)
    limit = contract["input"]["max_bytes"]
    try:
        with args.input.open("rb") as handle:
            content = handle.read(limit + 1)
    except OSError:
        print("Input unreadable; nothing written.", file=sys.stderr)
        return EXIT_IO
    if len(content) > limit:
        print(f"Input exceeds {limit} bytes; refused, nothing written.", file=sys.stderr)
        return EXIT_IO
    result = diagnose(
        content, args.sheet, contract, "synthetic" if args.synthetic else "unreviewed"
    )
    if args.output_dir.exists() or args.output_dir.is_symlink():
        print(
            "Output directory already exists; choose a new one. Nothing changed.", file=sys.stderr
        )
        return EXIT_IO
    try:
        write_package(args.output_dir, content, result, contract, args.language)
    except FileExistsError:
        print(
            "Output directory already exists; choose a new one. Nothing changed.", file=sys.stderr
        )
        return EXIT_IO
    except OSError:
        print(
            f"Package incomplete in {args.output_dir} (MANIFEST.json absent). No database touched.",
            file=sys.stderr,
        )
        return EXIT_IO
    local = Path(__file__).resolve().parents[2] / "data" / "local"
    if not args.output_dir.resolve().is_relative_to(local.resolve()):
        print("Note: output outside data/local; a local .gitignore protects it.", file=sys.stderr)
    status, counts = result["status"], result["counts"]
    print(
        f"sheet={args.sheet} source_read={status['source_read']} "
        f"normalization={status['normalization']} rows={counts['rows_diagnosed']} "
        f"blank_skipped={counts['blank_rows_skipped']} errors={counts['errors']} "
        f"warnings={counts['warnings']} publication=disabled output={args.output_dir}"
    )
    return EXIT_BLOCKED if status["normalization"] == "blocked" else EXIT_OK
