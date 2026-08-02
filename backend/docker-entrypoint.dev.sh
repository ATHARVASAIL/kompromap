#!/bin/sh
# Dev entrypoint. Mirrors docker-entrypoint.prod.sh's migration step —
# without this, a freshly-created Postgres volume has zero tables and
# every API call 500s with "relation does not exist" while /api/health
# (which doesn't touch the DB) misleadingly still returns 200.
set -e

echo "Waiting for Postgres at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}..."
# compose's `depends_on: service_healthy` already gates on pg_isready, but
# that only proves the server accepts connections — retry here anyway so a
# slow first-boot initdb can't race the migration step.
until python -c "
import os, sys, psycopg
try:
    psycopg.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        user=os.getenv('POSTGRES_USER', 'kompromap'),
        password=os.getenv('POSTGRES_PASSWORD', 'kompromap'),
        dbname=os.getenv('POSTGRES_DB', 'kompromap'),
        connect_timeout=3,
    ).close()
except Exception as e:
    print(f'  not ready yet: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done
echo "Postgres is up."

echo "Running database migrations..."
alembic upgrade head

echo "Starting dev server (hot-reload enabled)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
