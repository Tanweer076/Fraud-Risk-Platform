DATASET ?= data/raw/OneRecon_DataSet
OUT ?= data/processed

.PHONY: install test test-ml test-backend test-web lint label eda train migrate seed api \
	web-install web api-types docker-up docker-demo docker-seed docker-logs docker-down e2e

install:
	pip install -e "ml[dev]" -e "backend[dev]"

test: test-ml test-backend test-web

test-ml:
	cd ml && pytest -q

# Needs PostgreSQL; see TEST_DATABASE_URL in backend/tests/conftest.py.
test-backend:
	cd backend && pytest -q

test-web:
	cd frontend && npm test

lint:
	cd ml && ruff check . && ruff format --check .
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run typecheck && npm run lint && npm run format:check

label:
	fraudml label \
		--month-dir "$(DATASET)/Historical Data/june" \
		--month-dir "$(DATASET)/Historical Data/july" \
		--month-dir "$(DATASET)/Current Data/august" \
		--rules "$(DATASET)/business_rules.txt" \
		--out $(OUT)

eda:
	fraudml eda --processed $(OUT) --out ml/reports/eda_report.html

train:
	fraudml train --processed $(OUT) --out ml/artifacts

migrate:
	alembic -c backend/alembic.ini upgrade head

seed:
	fraudapi ingest \
		--month-dir "$(DATASET)/Historical Data/june" \
		--month-dir "$(DATASET)/Historical Data/july" \
		--month-dir "$(DATASET)/Current Data/august"

api:
	uvicorn app.main:create_app --factory --reload --port 8000

web-install:
	cd frontend && npm ci

# The dashboard on http://localhost:5173; it forwards /api to the API on port 8000 (make api).
web:
	cd frontend && npm run dev

# After changing the API: refresh the schema and the frontend's types (CI fails if they drift).
api-types:
	cd backend && fraudapi openapi --output ../frontend/openapi.json
	cd frontend && npm run gen:api

# --- Docker: the whole app on http://localhost:8080 (see README, Run it with Docker) ---------

docker-up:
	docker compose up --detach --build --wait

# Synthetic data, a model trained on it and the admin from .env: enough to try every page.
docker-demo:
	docker compose run --rm demo

# The real dataset from DATASET_DIR instead.
docker-seed:
	docker compose run --rm seed

docker-logs:
	docker compose logs --follow --tail 100

# Keeps the data; docker compose down --volumes deletes it too.
docker-down:
	docker compose down

# Browser tests against the running stack, signed in as the admin from .env. The first time:
# cd frontend && npx playwright install chromium
e2e:
	cd frontend && npm run e2e
