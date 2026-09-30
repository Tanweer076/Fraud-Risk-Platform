DATASET ?= data/raw/OneRecon_DataSet
OUT ?= data/processed

.PHONY: install test lint label eda train

install:
	pip install -e "ml[dev]"

test:
	cd ml && pytest -q

lint:
	cd ml && ruff check . && ruff format --check .

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
