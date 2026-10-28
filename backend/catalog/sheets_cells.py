"""Strict, pure Sheets cell parsers and CSV quoting checks."""

import json
import re
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlsplit

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "sheets-v1.json"

COORDINATE_DECIMALS = 10
# Longer numeric cells are refused before int()/Fraction(), which reject over 4300 digits.
MAX_NUMBER_CHARS = 64


def load_contract(path=CONTRACT_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class CellError(ValueError):
    """A cell that cannot become a candidate value; the message is the anomaly code."""


# Cell parsers. Each returns a candidate or raises CellError(code). Unknown markers are
# handled before parsing, so an empty cell never reaches them.


def parse_date(value, fmt):
    sep = "/" if fmt == "DD/MM/YYYY" else "-"
    other = "-" if sep == "/" else "/"
    match = re.fullmatch(
        rf"([0-9]{{1,2}}){re.escape(sep)}([0-9]{{1,2}}){re.escape(sep)}([0-9]{{4}})", value
    )
    if not match:
        if re.fullmatch(
            rf"[0-9]{{1,2}}{re.escape(other)}[0-9]{{1,2}}{re.escape(other)}[0-9]{{4}}", value
        ):
            raise CellError("date_format_of_other_sheet")
        raise CellError("invalid_date_format")
    day, month, year = (int(part) for part in match.groups())
    try:
        parsed = date(year, month, day)
    except ValueError as exc:
        raise CellError("impossible_date") from exc
    return parsed.isoformat()


def parse_count(value, maximum):
    if len(value) > MAX_NUMBER_CHARS:
        raise CellError("invalid_count")
    if re.fullmatch(r"-[0-9]+", value):
        raise CellError("negative_count")
    if re.fullmatch(r"-?[0-9]+[.,][0-9]+", value):
        raise CellError("fractional_count")
    if not re.fullmatch(r"[0-9]+", value):
        raise CellError("invalid_count")
    result = int(value)
    if result > maximum:
        raise CellError("count_above_limit")
    return result


def parse_decimal(value):
    if len(value) > MAX_NUMBER_CHARS:
        raise CellError("invalid_decimal")
    if re.fullmatch(r"-[0-9]+(?:[.,][0-9]+)?", value):
        raise CellError("negative_decimal")
    if not re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", value):
        raise CellError("invalid_decimal")
    # A string keeps the exact value; float or parseInt would change it.
    return str(Decimal(value.replace(",", ".")))


_DECIMAL_COORDINATE = re.compile(r"[+-]?[0-9]{1,3}(?:[.,][0-9]+)?")
_DM_COORDINATE = re.compile(
    r"([0-9]{1,3})\s*°\s*([0-9]{1,2}(?:[.,][0-9]+)?)\s*['′]?\s*([NSEWnsew])?"
)


def parse_coordinate(value, axis, region=None):
    """Return (WGS84 decimal string, source format); bounds are checked on exact values.

    Degrees and minutes without a hemisphere are only resolved when `region` (contract
    hemisphere_inference) leaves a single signed reading inside it; otherwise refused.
    """
    maximum = Fraction(90 if axis == "latitude" else 180)
    if len(value) > MAX_NUMBER_CHARS:
        raise CellError("invalid_coordinate")
    if _DECIMAL_COORDINATE.fullmatch(value):
        exact = Fraction(value.replace(",", "."))
        fmt = "decimal_degrees_comma" if "," in value else "decimal_degrees"
        text = str(Decimal(value.replace(",", ".")))
    else:
        match = _DM_COORDINATE.fullmatch(value)
        if not match:
            if re.search(r"[0-9]", value) and re.search(r"[NSEWnsew]", value):
                raise CellError("unsupported_coordinate_format")
            raise CellError("invalid_coordinate")
        degrees = Fraction(match[1])
        minutes = Fraction(match[2].replace(",", "."))
        if minutes >= 60:
            raise CellError("coordinate_minutes_out_of_range")
        unsigned = degrees + minutes / 60
        text = None
        if match[3]:
            hemisphere = match[3].upper()
            if hemisphere not in ("NS" if axis == "latitude" else "EW"):
                raise CellError("coordinate_axis_mismatch")
            exact = unsigned * (-1 if hemisphere in "SW" else 1)
            fmt = "degrees_decimal_minutes_hemisphere"
        else:
            if region is None:
                raise CellError("hemisphere_missing")
            low, high = (Fraction(bound) for bound in region[axis])
            inside = {reading for reading in (unsigned, -unsigned) if low <= reading <= high}
            if len(inside) > 1:
                raise CellError("hemisphere_ambiguous")
            if not inside:
                raise CellError("coordinate_outside_region")
            exact = inside.pop()
            fmt = "degrees_decimal_minutes_inferred_hemisphere"
    if abs(exact) > maximum:
        raise CellError("coordinate_out_of_range")
    if text is None:
        quantum = Decimal(1).scaleb(-COORDINATE_DECIMALS)
        text = str((Decimal(exact.numerator) / Decimal(exact.denominator)).quantize(quantum))
    return text, fmt


def check_url(value):
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise CellError("invalid_url")
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError as exc:
        raise CellError("invalid_url") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise CellError("unsafe_url_scheme")
    if parts.username is not None or parts.password is not None:
        raise CellError("url_with_credentials")
    if not parts.hostname:
        raise CellError("invalid_url")
    return value


def split_list(value):
    return [item.strip() for item in value.split(";")]


def scan_quoting(text):
    """Return (code, physical line) for the first RFC 4180 quoting violation, else None.

    csv.reader(strict=True) tolerates a quote inside an unquoted field and reads an
    unterminated quote to the end of the file; both would hide guessed cell boundaries.
    """
    state, line, opened_on = "start", 1, 1
    previous = ""
    for char in text:
        if state == "start":
            if char == '"':
                state, opened_on = "quoted", line
            elif char not in ",\r\n":
                state = "unquoted"
        elif state == "unquoted":
            if char == '"':
                return "quote_in_unquoted_field", line
            if char in ",\r\n":
                state = "start"
        elif state == "quoted":
            if char == '"':
                state = "after_quote"
        elif char == '"':
            state = "quoted"
        elif char in ",\r\n":
            state = "start"
        else:
            return "text_after_closing_quote", line
        if char == "\r" or (char == "\n" and previous != "\r"):
            line += 1  # CR, LF and CRLF each end one physical line, as csv.reader counts them
        previous = char
    if state == "quoted":
        return "unterminated_quoted_field", opened_on
    return None


