# Native PostGIS ARM64 from the PostgreSQL project (experimental)

This is an **opt-in compatibility probe** for Apple Silicon. It does NOT change Rescue's production database image or existing local database. The `compose.arm64-pgdg-smoke.yaml` file uses a separate Compose project, has no published ports, uses `network_mode: none`, and stores PGDATA only in a small temporary `tmpfs`.

## Source and verified behavior

- Base: official `postgres:17-trixie` pinned by OCI index digest in `infra/Dockerfile.db.arm64-pgdg`.
- Native `postgresql-17-postgis-3` and SQL extension scripts from the PostgreSQL Global Development Group (PGDG) Debian Trixie ARM64 package repository.
- On 25 October 2026 the package install yielded PostgreSQL 17.11 and PostGIS 3.6.4, native ARM64. The temporary database initialized successfully using the real Rescue `infra/init-db.sh` file, created role `rescue`, answered a PostGIS query, then was removed.
- The parent image is pinned, but `apt-get install` selects the latest signed compatible PGDG packages at build time. For production-quality reproducibility, pin exact APT package versions and use an audited package mirror or artifact.

## Reproduce the isolated test

Requires Docker Desktop/Compose on Apple Silicon, and `openssl`. **No existing database volumes or credentials are used.**

```sh
export ARM64_PROBE_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export ARM64_PROBE_DB_PASSWORD="$(openssl rand -hex 24)"
docker compose -p rescue-arm64-pgdg-probe -f compose.arm64-pgdg-smoke.yaml config --quiet
docker compose -p rescue-arm64-pgdg-probe -f compose.arm64-pgdg-smoke.yaml up -d --build
docker compose -p rescue-arm64-pgdg-probe -f compose.arm64-pgdg-smoke.yaml exec -T db \
  psql -U postgres -d rescue -Atqc \
  "SELECT (SELECT count(*) FROM pg_roles WHERE rolname='rescue'), (SELECT extversion FROM pg_extension WHERE extname='postgis'); SELECT ST_AsText(ST_SetSRID(ST_MakePoint(2.35,48.86),4326));"
docker compose -p rescue-arm64-pgdg-probe -f compose.arm64-pgdg-smoke.yaml down --volumes --remove-orphans
unset ARM64_PROBE_POSTGRES_PASSWORD ARM64_PROBE_DB_PASSWORD
```

Expected: the application role exists (`1`), a compatible PostGIS version is installed, and the spatial result is `POINT(2.35 48.86)`. Always run `down` even if a probe fails. All probe data are ephemeral.

## Initial controlled synthetic comparison — 25 October 2026

On the same Apple M4, two fresh throwaway containers per architecture were benchmarked sequentially in ABBA order (amd64, ARM64, ARM64, amd64). Every container had `--cpus 2`, `--memory 512m`, `--network none`, and `tmpfs` PGDATA. Both used PostgreSQL **17.11** and PostGIS **3.6.4** and the same Rescue initialization script; no real project data was accessed. After one warm-up query in each run, four `EXPLAIN (ANALYZE, TIMING OFF)` executions measured a deterministic synthetic aggregate of `ST_Distance` on 10,000 generated geography points.

| Architecture | Runs | Measured SQL executions | Median execution |
| --- | ---: | ---: | ---: |
| AMD64 / Rosetta, existing `rescue-smoke-db` image | 2 | 8 | 346.12 ms |
| Native ARM64 / official PGDG build | 2 | 8 | 27.21 ms |

**Observed ratio: 12.72x** faster in this particular CPU-heavy spatial query, under these test conditions. Startup times and memory readings varied across runs; they are **not** treated as a reliable performance or RAM saving. This is not a general application speedup, nor a safety justification for a database switch. Repeat with realistic workloads, whole-application migration checks, storage I/O, concurrency, and a reviewed backup/rollback plan.

## Full data and permissions rehearsal (2026-10-25)

The optional `scripts/verify_arm64_full_parity.py` reads the **local `rescue-smoke-db-1` test container only**, creates a new disposable ARM64 container, then streams a PostgreSQL custom-format dump directly from the original container into `pg_restore` on the ARM64 target. It never stops the original database, publishes no ports, exposes no network, mounts no existing data volume and writes no dump file. The test container is removed in a `finally` block.

```sh
docker build --platform linux/arm64 -t rescue-pgdg-arm64:parity \
  -f infra/Dockerfile.db.arm64-pgdg .
python3 scripts/verify_arm64_full_parity.py
# Optional after other local experiments finish:
docker image rm rescue-pgdg-arm64:parity
```

The probe rejects a missing source or an already-existing target. It checks table names, per-table row counts and fingerprints (not raw values), PostGIS version, owners, grants, index definitions, sequence state, constraint/index/sequence counts and login/read access through the application role. The dump/restore preserves SQL object owners and grants; disabling ownership/ACL restoration would invalidate this check. Sensitive row contents are neither printed nor written to files.

**Measured on 25 October 2026**: a full copy of the local Rescue smoke database passed the checks for **32 tables / 10,744 rows, 117 indexes, 12 sequences, 129 constraints**, PostGIS 3.6.4 and real `rescue` account access; the temporary container was removed. The test reports only aggregate counts.

This is a **read-only migration rehearsal**, not a production backup, hot replication, or automatic cutover. Source data can change after the dump snapshot, so a real cutover requires pausing writers, creating a durable encrypted backup, validating it, restoring into a fresh **persistent** volume, performing real application end-to-end checks and maintaining a tested rollback.

## Do not treat this as a migration plan yet

Before proposing a default-image change, run the full Django migrations against a **new** database, repeat randomized AMD64-vs-ARM64 benchmarks on representative synthetic operations with matching versions, audit the image and packages, and rehearse `pg_dump` + `pg_restore` into a fresh volume. Never mount or copy the existing PostgreSQL PGDATA directory into an unverified image; check schema, index and collation compatibility and a rollback path.

References: https://www.postgresql.org/download/linux/debian/ , https://wiki.postgresql.org/wiki/Apt , https://postgis.net/documentation/getting_started/install_ubuntu/ , https://github.com/docker-library/postgres
