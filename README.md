# Fraud Risk Platform

End-to-end transaction fraud detection and risk scoring: ML models that turn a transaction into a 0–100 risk score with explanations, served by FastAPI, stored in PostgreSQL and shown in a React dashboard.

The data comes from three financial systems that record the same transactions: General Ledger (GL, XML), Management Accounting (MA, REST API) and Financial Accounting (FA, CSV). A transaction is **suspicious** when those systems disagree about it or it breaks a business rule. That derived label is what the models learn to predict. See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Status

| Step | State |
|---|---|
| 1. Ingestion, linking, break labelling | done |
| 2. EDA | next |
| 3. Features, models, risk score, explanations | planned |
| 4. PostgreSQL + FastAPI | planned |
| 5. React dashboard | planned |
| 6. Docker, CI/CD, deployment | CI only |

## Setup

Requires Python 3.11+.

```bash
make install
```

Put the dataset (not committed) under `data/raw/`, so the folder looks like `data/raw/OneRecon_DataSet/{business_rules.txt, Historical Data/june, Historical Data/july, Current Data/august}`.

## Build labelled data

```bash
make label
```

For each month this reads GL, MA and FA, checks the business rules, links the three systems by `TransactionID`, resolves account keys through that month's join map, and writes `data/processed/labelled_<YYYYMM>.parquet` plus a JSON summary.

By default MA is read from the payload embedded in `ma_api_server_<YYYYMM>.py` (decoded, never executed). To read it over HTTP instead, start that month's server and run:

```bash
fraudml label --month-dir "data/raw/OneRecon_DataSet/Historical Data/july" \
  --rules data/raw/OneRecon_DataSet/business_rules.txt --ma-source api --ma-url http://localhost:5000
```

Current results:

| Month | Transactions | Suspicious | Rate |
|---|---|---|---|
| 2026-06 | 16,824 | 0 | 0.0% |
| 2026-07 | 21,987 | 841 | 3.8% |
| 2026-08 | 22,258 | 2,096 | 9.4% |

### Break types

| Type | Meaning |
|---|---|
| `missing_in_gl` / `missing_in_ma` / `missing_in_fa` | Transaction absent from that system |
| `amount_mismatch` | Amounts differ by more than one cent between two systems |
| `date_mismatch` | Transaction dates differ between systems |
| `currency_mismatch` | Currencies differ between systems |
| `unmapped_account` | GL account has no join-map entry effective on the transaction date |
| `key_mismatch` | MA or FA key differs from the one the join map gives for the GL account |
| `rule_violation` | A record breaks a rule in `business_rules.txt`, or its date is outside the month |

## Tests

```bash
make test   # pytest, positive and negative cases
make lint   # ruff
```

## Repository layout

```
docs/architecture.md   system design
ml/fraudml/            ML package (ingest, canonical, labels, pipeline CLI)
ml/tests/              unit and CLI tests with synthetic fixtures
data/                  raw / interim / processed data (git-ignored)
```
