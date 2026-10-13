#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

echo "[entrypoint] Seeding demo inventory..."
python -c "
from app.core.database import SessionLocal
from app.db.seeds.property_seeds import seed_property_inventory
db = SessionLocal()
try:
    result = seed_property_inventory(db)
    print('Seed result:', result)
finally:
    db.close()
"

echo "[entrypoint] Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000