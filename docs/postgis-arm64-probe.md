# Experimental ARM64 PostGIS probe (Apple Silicon)

Production/default stays on `postgis/postgis:17-3.6` (amd64). **Never mount an existing rescue database volume in the ARM64 probe.**

The opt-in Dockerfile pins the multi-arch digest of community-maintained `imresamu/postgis:17-3.6.1-trixie`. It provides PostgreSQL 17 / PostGIS 3.6.1 on ARM64, but the official current image uses PostGIS 3.6.4. This is a compatibility experiment, **not a production substitution**.

## Alternative: native ARM64 from official PostgreSQL + PGDG

An additional experimental image is available in [`infra/Dockerfile.db.arm64-pgdg`](../infra/Dockerfile.db.arm64-pgdg) with an isolated [`compose.arm64-pgdg-smoke.yaml`](../compose.arm64-pgdg-smoke.yaml). It builds on digest-pinned `postgres:17-trixie` and installs PostGIS from the official PGDG ARM64 repository rather than reusing the community image. See [the isolated PGDG probe guide](postgis-arm64-pgdg.md). Neither probe changes the default database or an existing Docker volume.

## Reproduce the disposable smoke test

Requires Docker Compose >=2.20.2. The probe uses a distinct Compose project, no published ports, no network, no host data mounts, a 512 MiB limit, and a disposable tmpfs database. It loses all data on stop.

```sh
export ARM64_PROBE_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export ARM64_PROBE_DB_PASSWORD="$(openssl rand -hex 24)"
docker compose -p rescue-arm64-probe -f compose.arm64-smoke.yaml up -d --build
docker compose -p rescue-arm64-probe -f compose.arm64-smoke.yaml ps
docker compose -p rescue-arm64-probe -f compose.arm64-smoke.yaml exec -T db psql -U postgres -d rescue -Atqc "SELECT (SELECT count(*) FROM pg_roles WHERE rolname='rescue'), (SELECT extversion FROM pg_extension WHERE extname='postgis'); SELECT ST_AsText(ST_SetSRID(ST_MakePoint(2.35,48.86),4326));"
docker compose -p rescue-arm64-probe -f compose.arm64-smoke.yaml down --volumes --remove-orphans
unset ARM64_PROBE_POSTGRES_PASSWORD ARM64_PROBE_DB_PASSWORD
```

Expected: role count `1`, PostGIS `3.6.1`, point `POINT(2.35 48.86)`. Always run `down` even if a check fails.

## Required before changing any real database

1. Audit image source, SBOM, maintainer, CVEs, and verify the pinned digest.
2. Benchmark identical synthetic datasets under isolated AMD64 and ARM64 runs, repeating startup, CPU, memory and SQL measurements.
3. Test Django migrations, imports, exports, extension versions and spatial index behavior.
4. Back up using `pg_dump`, restore into a **fresh ARM64 volume**, validate data and rollback. Never reuse existing PGDATA directly between variants.
5. Obtain review before making this the default or modifying production.

References: https://hub.docker.com/r/postgis/postgis/ ; https://hub.docker.com/r/imresamu/postgis ; https://docs.docker.com/reference/compose-file/services/#healthcheck
