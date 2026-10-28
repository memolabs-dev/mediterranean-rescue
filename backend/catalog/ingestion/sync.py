"""Scheduled reading of the Google Sheets exports (ADR 0012).

Every few minutes each configured tab is downloaded from its public CSV export. Bytes identical
to the previous reading are recorded as "unchanged"; new bytes go through `stage_snapshot`, which
diagnoses them again and keeps them in private staging. Nothing is linked, drafted or published
here, and one failing tab never stops the others or the loop.
"""

import hashlib
import http.client
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection

from catalog.models import SHEETS, SheetSync, Source
from catalog.review.crosswalk import (
    STAGE_PERMISSION,
    blocking_reason,
    diagnose_for,
    propose_links,
    stage_snapshot,
)
from catalog.sheets import load_contract

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = ("docs.google.com",)
ALLOWED_HOST_SUFFIXES = (".googleusercontent.com",)
SOCKET_TIMEOUT_SECONDS = 30
DOWNLOAD_DEADLINE_SECONDS = 90
CHUNK_BYTES = 64 * 1024
REVIEW_SHEETS = ("Data_operations", "Other_data")
# One reading at a time, whatever the number of loops started.
ADVISORY_LOCK_KEY = 72_430_118


class FetchRefused(Exception):
    """The address or the answer is not one this reader accepts."""


def _check_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not (
        host in ALLOWED_HOSTS or host.endswith(ALLOWED_HOST_SUFFIXES)
    ):
        raise FetchRefused("Only https Google Sheets export addresses are read.")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    # Google answers an export with a redirect to a googleusercontent host; nothing else is followed.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_body(response, max_bytes, deadline_seconds=DOWNLOAD_DEADLINE_SECONDS):
    """Reads at most max_bytes within a total deadline; a body shorter than announced is refused."""
    started = time.monotonic()
    chunks, size = [], 0
    while True:
        if time.monotonic() - started > deadline_seconds:
            raise FetchRefused("The download took too long.")
        chunk = response.read(CHUNK_BYTES)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > max_bytes:
            raise FetchRefused("The export is larger than the accepted size.")
    content = b"".join(chunks)
    announced = response.headers.get("Content-Length")
    # A dropped connection returns the bytes received so far: a cut file must not pass as complete.
    if announced is not None and announced.isdigit() and int(announced) != len(content):
        raise FetchRefused("The download was cut before the end.")
    return content


def fetch_csv(url, max_bytes):
    _check_url(url)
    opener = urllib.request.build_opener(_CheckedRedirects)
    request = urllib.request.Request(url, headers={"User-Agent": "mediterranean-rescue-sync"})
    with opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
        return read_body(response, max_bytes)


def check_config(config):
    """Refuses a configuration that names an unknown source, an unknown tab or a foreign address."""
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("tabs"), dict)
        or not config["tabs"]
    ):
        raise ValueError("The configuration needs a source key and at least one tab.")
    if not Source.objects.filter(key=config.get("source")).exists():
        raise ValueError("The configured source does not exist.")
    known = {key for key, _ in SHEETS}
    for sheet, url in config["tabs"].items():
        if sheet not in known:
            raise ValueError(f"Unknown tab in the configuration: {sheet}.")
        _check_url(url)


def sync_actor(username="sheets-sync"):
    """The account that signs automatic updates. It never signs in: a usable password is refused."""
    user, created = get_user_model().objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
        user.save()
        app_label, codename = STAGE_PERMISSION.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    elif user.has_usable_password():
        raise ValueError(f"The account {username} can sign in; it cannot sign automatic updates.")
    # Read again so a permission removed or an account deactivated is seen at the next pass.
    return get_user_model().objects.get(pk=user.pk)


def summarize(snapshot):
    """What an update brings, in counts the team can act on."""
    if snapshot.sheet not in REVIEW_SHEETS:
        return {"rows": snapshot.row_count}
    counts = {"unchanged": 0, "to_look_at": 0, "to_fix": 0, "already_verified": 0}
    for proposal in propose_links(snapshot):
        if proposal.kind == "exact_carry":
            counts["unchanged"] += 1
        elif proposal.kind in ("new", "candidates"):
            counts["to_look_at"] += 1
        elif proposal.kind in ("blocked", "repeat"):
            counts["to_fix"] += 1
        else:
            counts["already_verified"] += 1
    return counts


def sync_sheet(*, source, sheet, url, actor, fetch=fetch_csv):
    """Reads one tab once and records what happened. Never raises for an expected failure."""
    max_bytes = load_contract()["input"]["max_bytes"]
    try:
        content = fetch(url, max_bytes)
    except (FetchRefused, urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        message = str(exc) if isinstance(exc, FetchRefused) else "The sheet could not be reached."
        return SheetSync.objects.create(
            source=source, sheet=sheet, status="failed", message=message
        )
    sha = hashlib.sha256(content).hexdigest()
    # "Unchanged" means the same bytes as the previous reading, whatever was imported by hand since.
    previous = (
        SheetSync.objects.filter(source=source, sheet=sheet)
        .exclude(status="failed")
        .order_by("-created_at")
        .first()
    )
    if previous is not None and previous.sha256 == sha:
        return SheetSync.objects.create(
            source=source,
            sheet=sheet,
            status="unchanged" if previous.status != "refused" else "refused",
            snapshot=previous.snapshot,
            sha256=sha,
            message=previous.message,
        )
    try:
        snapshot, _ = stage_snapshot(source=source, sheet=sheet, content=content, actor=actor)
    except ValidationError:
        reason = blocking_reason(diagnose_for(source, sheet, content)) or "invalid"
        return SheetSync.objects.create(
            source=source, sheet=sheet, status="refused", sha256=sha, message=reason
        )
    return SheetSync.objects.create(
        source=source,
        sheet=sheet,
        status="new_data",
        snapshot=snapshot,
        sha256=sha,
        summary=summarize(snapshot),
    )


def _try_lock():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
        return cursor.fetchone()[0]


def _unlock():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])


def sync_all(config, actor=None, fetch=fetch_csv):
    """One pass over every configured tab: {"source": key, "tabs": {sheet: url}}.

    Returns the readings recorded, or None when another pass holds the lock.
    """
    if not _try_lock():
        return None
    try:
        source = Source.objects.get(key=config["source"])
        actor = actor or sync_actor()
        runs = []
        for sheet, url in config["tabs"].items():
            try:
                runs.append(
                    sync_sheet(source=source, sheet=sheet, url=url, actor=actor, fetch=fetch)
                )
            except Exception:
                # An unexpected failure on one tab is recorded and never stops the others.
                logger.exception("Unexpected failure while reading the %s tab", sheet)
                runs.append(
                    SheetSync.objects.create(
                        source=source, sheet=sheet, status="failed", message="Unexpected error."
                    )
                )
        return runs
    finally:
        _unlock()
