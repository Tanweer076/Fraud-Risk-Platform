#!/bin/sh
# Start the app on Render: nginx first (so the health check passes during the release steps),
# then migrations, the baked-in model, the demo months on first boot, and the API.
set -eu

# Render hands out postgresql:// URLs; SQLAlchemy needs the driver named.
DATABASE_URL=$(printf '%s' "$DATABASE_URL" | sed -E 's#^postgres(ql)?://#postgresql+psycopg://#')
export DATABASE_URL

sed "s/\${PORT}/${PORT:-10000}/" /app/nginx.conf > /tmp/nginx.conf
nginx -c /tmp/nginx.conf

alembic -c /app/backend/alembic.ini upgrade head

# A new build brings a new model and the old one's file is gone: stand the old one down, so the
# registry activates the new one. Then report whether any data has been loaded yet.
state=$(python - <<'EOF'
import os
from pathlib import Path
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as db:
    for row in db.execute(text("SELECT id, artifact_path FROM model_versions WHERE is_active")):
        if not Path(row.artifact_path).exists():
            db.execute(text("UPDATE model_versions SET is_active = false WHERE id = :id"), {"id": row.id})
    loaded = db.execute(text("SELECT count(*) FROM ingestion_batches")).scalar()
print("loaded" if loaded else "empty")
EOF
)
fraudapi sync-models

if [ "$state" = "empty" ]; then
    echo "First boot: loading and scoring the demo months"
    fraudapi ingest --rules "$RULES_PATH" \
        --month-dir /opt/demo/raw/202606 --month-dir /opt/demo/raw/202607 --month-dir /opt/demo/raw/202608
fi
if [ -n "${ADMIN_PASSWORD:-}" ]; then
    FRAUDAPI_PASSWORD="$ADMIN_PASSWORD" fraudapi create-user \
        --email "${ADMIN_EMAIL:-admin@example.com}" --role admin \
        || echo "The admin was not created (see above; it may already exist)."
fi

export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR" "$UPLOAD_DIR"
exec uvicorn app.main:create_app --factory \
    --host 127.0.0.1 --port 8000 --workers "${WEB_CONCURRENCY:-1}" \
    --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-server-header
