#!/usr/bin/env python3
"""Read-only rescue-smoke source -> disposable ARM64 PostGIS full-restore parity probe.

Never modifies or stops source, never prints raw rows, never writes a dump to disk.
Requires local Docker, prebuilt rescue-pgdg-arm64:parity.
"""
import secrets
import subprocess
import time

SOURCE = "rescue-smoke-db-1"
TARGET = "rescue-arm64-full-parity"
IMAGE = "rescue-pgdg-arm64:parity"


def cmd(argv, *, timeout=30, check=True):
    done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if check and done.returncode:
        raise RuntimeError(f"command failed ({done.returncode}): {argv[:3]}")
    return done


def query(container, sql):
    return cmd(["docker", "exec", container, "psql", "-U", "postgres", "-d", "rescue",
                "-X", "-A", "-t", "-c", sql], timeout=30).stdout.strip()


def summary(container):
    table_names = query(container, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    assert table_names, "source has no application tables"
    stats = {}
    for table in table_names:
        ident = '"' + table.replace('"', '""') + '"'
        sql = ("SELECT count(*), md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' "
               "ORDER BY md5(to_jsonb(t)::text)),'')) FROM public." + ident + " t")
        stats[table] = query(container, sql)
    other = query(container, """SELECT
        (SELECT count(*) FROM pg_indexes WHERE schemaname='public'),
        (SELECT count(*) FROM pg_sequences WHERE schemaname='public'),
        (SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace),
        (SELECT extversion FROM pg_extension WHERE extname='postgis')""")
    owners = query(container, "SELECT tablename || '::' || tableowner FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    privileges = query(container, "SELECT table_name || ':' || grantee || ':' || privilege_type FROM information_schema.role_table_grants WHERE table_schema='public' ORDER BY table_name, grantee, privilege_type").splitlines()
    sequences = query(container, "SELECT sequencename || '|' || coalesce(last_value::text, 'NULL') || '|' || start_value || '|' || increment_by FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename").splitlines()
    indexes = query(container, "SELECT indexname || '|' || indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname").splitlines()
    return stats, other, owners, privileges, sequences, indexes


def main():
    before_names = cmd(["docker", "ps", "--format", "{{.Names}}"]).stdout
    assert SOURCE in before_names.splitlines(), "source not running"
    assert TARGET not in before_names.splitlines(), "parity target already exists"
    # Snapshot before copy. It might change during the read; final parity only refers to dump snapshot.
    source_tables, source_objects, source_owners, source_privileges, source_sequences, source_indexes = summary(SOURCE)
    secret = secrets.token_hex(24)
    role_secret = secrets.token_hex(24)
    try:
        cmd(["docker", "run", "-d", "--rm", "--name", TARGET, "--platform", "linux/arm64",
             "--network", "none", "--cpus", "2", "--memory", "512m",
             "--tmpfs", "/var/lib/postgresql/data:rw,size=192m",
             "-e", "POSTGRES_PASSWORD=" + secret, "-e", "DB_PASSWORD=" + role_secret,
             "-e", "POSTGRES_DB=rescue", IMAGE], timeout=35)
        for _ in range(60):
            if cmd(["docker", "exec", TARGET, "psql", "-U", "postgres", "-d", "rescue",
                    "-A", "-t", "-c", "SELECT PostGIS_Version()"], check=False, timeout=8).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("target database not ready")

        start = time.monotonic()
        source = subprocess.Popen(
            ["docker", "exec", SOURCE, "pg_dump", "-U", "postgres", "-d", "rescue",
             "--format=custom"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        target = subprocess.Popen(
            ["docker", "exec", "-i", TARGET, "pg_restore", "-U", "postgres", "-d", "rescue",
             "--clean", "--if-exists", "--exit-on-error", "--single-transaction"],
            stdin=source.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        source.stdout.close()
        target.communicate(timeout=90)
        source.stderr.read()
        src_status = source.wait(timeout=20)
        if src_status or target.returncode:
            raise RuntimeError(
                "streamed dump/restore failed; src=" + str(src_status)
                + " restore=" + str(target.returncode)
                + " (output suppressed to avoid exposing data)")
        elapsed = time.monotonic() - start
        target_tables, target_objects, target_owners, target_privileges, target_sequences, target_indexes = summary(TARGET)
        assert source_tables == target_tables, "table row counts/fingerprints mismatch"
        assert source_objects == target_objects, "indexes/sequences/constraints or PostGIS differ"
        assert source_owners == target_owners, "table ownership changed"
        assert source_privileges == target_privileges, "table ACL/privilege mismatch"
        assert source_sequences == target_sequences, "sequence state mismatch"
        assert source_indexes == target_indexes, "index definitions mismatch"
        as_rescue = cmd(["docker", "exec", "-e", "PGPASSWORD=" + role_secret, TARGET,
                         "psql", "-h", "127.0.0.1", "-U", "rescue", "-d", "rescue",
                         "-Atqc", "SELECT count(*) FROM django_migrations"], timeout=15)
        source_migrations = query(SOURCE, "SELECT count(*) FROM django_migrations")
        assert as_rescue.stdout.strip() == source_migrations, "application role migration-read failed"
        print("FULL_RESTORE_PARITY_OK", flush=True)
        print("APP_TABLES", len(source_tables), flush=True)
        print("OWNER_PRIVILEGE_PARITY_OK", flush=True)
        print("APP_ROLE_LOGIN_READ_OK", flush=True)
        print("INDEX_DEFINITIONS_SEQUENCE_VALUES_PARITY_OK", flush=True)
        print("APP_ROWS", sum(int(x.split("|")[0]) for x in source_tables.values()), flush=True)
        print("INDEXES_SEQUENCES_CONSTRAINTS_POSTGIS", source_objects, flush=True)
        print("RESTORE_SECONDS", round(elapsed, 2), flush=True)
    finally:
        removed = cmd(["docker", "rm", "-f", "-v", TARGET], check=False, timeout=25)
        print("TEMP_CONTAINER_REMOVED", removed.returncode == 0, flush=True)


if __name__ == "__main__":
    main()
