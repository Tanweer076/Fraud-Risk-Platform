#!/bin/sh
# serve    start the API (the default)
# migrate  bring the database schema up to date and register saved models; run it before
#          serve on every release (docker compose does, as the migrate service)
# anything else runs as given, e.g. fraudapi create-user ...
set -eu

case "${1:-serve}" in
serve)
    # Each worker process writes its metrics here and /metrics adds them up; start empty.
    export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
    rm -rf "$PROMETHEUS_MULTIPROC_DIR"
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR" "$MODEL_DIR" "$UPLOAD_DIR"
    # The API is only reached through the web proxy on a private network, which sets
    # X-Forwarded-For to the real client, so any sender is trusted to forward it.
    exec uvicorn app.main:create_app --factory \
        --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" \
        --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" --no-server-header
    ;;
migrate)
    alembic -c /app/backend/alembic.ini upgrade head
    mkdir -p "$MODEL_DIR"
    fraudapi sync-models || echo "No model yet: load data and train one (see README, Deployment)."
    ;;
*)
    exec "$@"
    ;;
esac
