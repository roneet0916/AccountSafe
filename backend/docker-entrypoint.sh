#!/usr/bin/env sh
# =============================================================================
# AccountSafe backend container entrypoint.
# =============================================================================
# Runs collectstatic + migrate, then execs gunicorn. Keeping this as a real
# script avoids YAML quoting bugs in compose `command:` blocks.
#
# Env knobs:
#   GUNICORN_WORKERS (default 3)
#   GUNICORN_THREADS (default 2)
#   GUNICORN_BIND    (default 0.0.0.0:8000)
#   SKIP_MIGRATE=1   -> don't run `migrate` (useful for one-off debug runs)
#   SKIP_COLLECTSTATIC=1
# =============================================================================

set -eu

: "${GUNICORN_WORKERS:=3}"
: "${GUNICORN_THREADS:=2}"
: "${GUNICORN_BIND:=0.0.0.0:8000}"

if [ "${SKIP_COLLECTSTATIC:-0}" != "1" ]; then
    echo "[entrypoint] collectstatic..."
    python manage.py collectstatic --noinput
fi

if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] migrate..."
    python manage.py migrate --noinput
fi

echo "[entrypoint] starting gunicorn on ${GUNICORN_BIND} with ${GUNICORN_WORKERS} workers..."
exec gunicorn \
    --bind "${GUNICORN_BIND}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    core.wsgi:application
