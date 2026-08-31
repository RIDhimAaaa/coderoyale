#!/bin/sh
set -e

echo "[entrypoint] applying migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-0}" = "1" ]; then
  echo "[entrypoint] seeding demo data..."
  python -m scripts.seed || true
fi

echo "[entrypoint] starting api..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
