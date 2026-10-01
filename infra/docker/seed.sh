#!/usr/bin/env bash
# Load three months, train the first model and create the first admin.
#   seed real   the OneRecon dataset, mounted read-only at /dataset
#   seed demo   three synthetic months, for trying the app without the real data
# Running it again reloads the months in place and trains a new model version, which an admin
# can activate on the Models page. The admin is created when ADMIN_PASSWORD is set.
set -euo pipefail

case "${1:-}" in
real)
    months=("/dataset/Historical Data/june" "/dataset/Historical Data/july" "/dataset/Current Data/august")
    rules=/dataset/business_rules.txt
    ;;
demo)
    rm -rf /data/demo
    fraudml demo-data --out /data/demo --rows "${DEMO_ROWS:-2000}" >/dev/null
    months=(/data/demo/raw/202606 /data/demo/raw/202607 /data/demo/raw/202608)
    rules=/data/demo/business_rules.txt
    ;;
*)
    echo "usage: seed real|demo" >&2
    exit 2
    ;;
esac

month_args=()
for dir in "${months[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Missing month folder: $dir" >&2
        exit 1
    fi
    month_args+=(--month-dir "$dir")
done
cp "$rules" "$RULES_PATH"

echo "Labelling the months"
fraudml label "${month_args[@]}" --rules "$RULES_PATH" --out /data/processed >/dev/null
echo "Training a model"
fraudml train --processed /data/processed --out "$MODEL_DIR"
echo "Loading and scoring the months"
fraudapi ingest "${month_args[@]}" --rules "$RULES_PATH"

if [ -n "${ADMIN_PASSWORD:-}" ]; then
    FRAUDAPI_PASSWORD="$ADMIN_PASSWORD" fraudapi create-user \
        --email "${ADMIN_EMAIL:-admin@example.com}" --role admin \
        || echo "The admin was not created (see above)."
fi
