#!/bin/sh
# Entry point of the production image. `serve` migrates, then starts gunicorn; any other
# command is a manage.py command (sync_logbook --every 21600, sync_sheets --every 300, …).
set -eu
manage() { uv run --no-sync python backend/manage.py "$@"; }

if [ "${1:-serve}" = "serve" ]; then
  manage migrate --noinput
  exec uv run --no-sync gunicorn --chdir backend rescue.wsgi:application \
    --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-2}" --threads 1 --timeout 30 \
    --access-logfile -
fi
# Readers start with the web process: wait until its migrations are applied, or their first
# pass fails on a missing table (and the logbook reader would then sleep six hours).
until manage migrate --check >/dev/null 2>&1; do sleep 3; done
exec uv run --no-sync python -u backend/manage.py "$@"
