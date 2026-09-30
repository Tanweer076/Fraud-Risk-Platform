DATASET ?= data/raw/OneRecon_DataSet
OUT ?= data/processed

.PHONY: install test test-ml test-backend lint label eda train migrate seed api

install:
	pip install -e "ml[dev]" -e "backend[dev]"

test: test-ml test-backend

test-ml:
	cd ml && pytest -q

# Needs PostgreSQL; see TEST_DATABASE_URL in backend/tests/conftest.py.
test-backend:
	cd backend && pytest -q

lint:
	cd ml && ruff check . && ruff format --check .
	cd backend && ruff check . && ruff format --check .

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
