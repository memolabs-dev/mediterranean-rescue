# Rescue Atlas — Ingestion operations and monitoring

> Independent prototype; not an adopted Data For Good / SOS Méditerranée production policy. Do not enable external alerts, export operational data or purge records until the association approves ownership, scope and rights.

## Scheduled sources

- Google Sheets export reader: `python backend/manage.py sync_sheets --config <private-config> --every 300`.
- Public logbook reader: `python backend/manage.py sync_logbook --every 14400`. Cadences above are **examples**, not deployed or guaranteed production settings.
- Both readers stage data privately. **No automatic matching, approval, publication or withdrawal**.
- Per-source advisory locks prevent overlapping runs. A source failure must not block other sources.
- `SheetSync` tracks each reading with one of: `new_data`, `unchanged`, `refused`, `failed`. Retain the audit trail.

## Safe structured monitoring

Both commands accept optional `--json` and emit one JSON object **per completed reading**, containing only:
```json
{"schema":1,"sheet":"Data_operations","status":"unchanged","counts":{"to_look_at":2,"to_fix":0}}
```
- Never include CSV payloads, source URLs, witness quotes, error messages, SHA hashes, credentials or raw API responses in monitoring.
- A missing log line alone is **not** proof of failure: distinguish the one-shot command, a skipped advisory lock, stopped scheduler and network outage.
- Count `failed`/ `refused` separately. An `unchanged` run is healthy if sources legitimately have not changed.
- Private operators can cross-check `/api/private/v1/sync/` with appropriate role. Public `/api/v1/` never exposes internal sync statuses.

## Recovery checklist

1. Check the **healthy** state of the app, PostgreSQL/PostGIS and the scheduler containers.
2. Determine which configured source and which last **safe status** failed; do not paste secrets, URL query parameters or source content into tickets.
3. Verify network/TLS and the source's read permission without bypassing HTTPS host allowlists.
4. Fix the source or the contract by reviewed change; retry one reader against a safe staging copy.
5. Compare snapshot SHA and `SheetSync` history to confirm idempotence. A correction still needs explicit volunteer review.
6. Validate browser paths and release only after green PostGIS, OpenAPI and E2E.

## Data retention — **decision pending SOS and Data For Good**

No automatic cleanup command is installed. A retention policy must specify the data owner and legal basis, retention period per object type, process for source requests/withdrawals, backup retention, and recovery/rollback. In particular, do not delete `SheetSync`, snapshots, approvals, evidence or publication audit records just to reduce disk use. When approved, implement a dry-run/confirmation workflow with foreign-key safety checks and synthetic rollback tests in a separate issue/PR.

## Acceptance

- One failed source cannot interrupt others; repeated bytes are not duplicated.
- Structured `--json` monitoring is safe even when a source message contains sensitive text.
- Review and publication remain separate, human-controlled steps.
- No new database migrations, API contracts or frontend behaviors.
