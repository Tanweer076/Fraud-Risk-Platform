# Fraud Risk Platform

End-to-end transaction fraud detection and risk scoring: ML models that turn a transaction into a 0–100 risk score with explanations, served by FastAPI, stored in PostgreSQL and shown in a React dashboard.

The data comes from three financial systems that record the same transactions: General Ledger (GL, XML), Management Accounting (MA, REST API) and Financial Accounting (FA, CSV). A transaction is **suspicious** when those systems disagree about it or it breaks a business rule. That derived label is what the models learn to predict. See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Status

| Step | State |
|---|---|
| 1. Ingestion, linking, break labelling | done |
| 2. EDA report | done |
| 3. Features, models, risk score, explanations | done |
| 4. PostgreSQL + FastAPI | done |
| 5. React dashboard | done |
| 6. Docker, CI/CD, deployment | next (CI already checks ml, backend and frontend) |

## Setup

Requires Python 3.11+, PostgreSQL 16 for the API, and Node 22+ for the dashboard.

```bash
make install       # installs ml/ (fraudml) and backend/ (fraudapi)
make web-install   # installs the dashboard's packages (frontend/)
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

## EDA report

```bash
make eda   # after make label
```

Writes `ml/reports/eda_report.html`, a self-contained page with volumes, which systems hold each transaction, break types and how they overlap, suspicious rate by segment with 95% intervals, the size of amount and date mismatches, account history and month-to-month drift.

What it shows on the current data:

- Amount mismatch is the most common break (1,366), then rule violations (450) and date mismatches (386).
- 437 of the 450 rule violations are also amount mismatches: one system holds a negative or over-limit amount.
- The suspicious rate barely changes across currency, country, description, weekday, amount band or part of month (5.8% to 7.6%).
- Accounts that broke last month are not more likely to break this month (8.2% vs 8.9% in August).
- Amount distributions do not drift between months (PSI at most 0.003).

So the models should be built on cross-system deviation features and rule checks rather than a transaction's own attributes.

## Features, models and risk score

```bash
make train   # after make label
```

This builds 34 features in four groups:

| Group | Examples |
|---|---|
| Cross-system | present in GL/MA/FA, relative amount difference per pair, sign conflict, largest date gap, number of currencies, unmapped account, key mismatch |
| Rules | number of rule violations, negative amount, amount over 100,000, date outside the month |
| Behavioural | account's earlier transaction count, amount z-score and ratio to its previous maximum, days since last transaction, first use of a currency, breaks in earlier months |
| Attributes | amount, round amount, day of month, weekday, month end, currency, country, description |

Behavioural features only look at the account's transactions on earlier days, and at labels from earlier months.

It then trains and compares logistic regression, random forest and LightGBM, plus two reference models: LightGBM on behavioural and attribute features only, and an Isolation Forest that never sees labels. The latest month (August) is held out as an out-of-time test. Earlier months are split 80/20 into train and validation. Validation picks the champion (restricted to models that can explain single predictions), fits an isotonic calibrator and sets the threshold.

Each run is saved to `ml/artifacts/model_vN/` as:
- `model.joblib`: preprocessing, model, calibrator, feature list, threshold and metadata
- `metadata.json`
- `model_report.md`

`ml/artifacts/LATEST` names the newest run.

### Risk score

- **Model score** = round(100 × calibrated probability).
- **Rule floors.** Deterministic break checks set a minimum score:
  - rule violation: 90
  - missing from a system, unmapped account or key mismatch: 80
  - amount, date or currency mismatch: 70
- **Risk score** = the higher of the model score and the floor.
- **Bands:** low 0–39, medium 40–69, high 70–89, critical 90–100.
- **Priority** ranks work within a band by money at stake. Exposure is the amount difference for an amount mismatch, or the whole amount for any other break, converted to USD with a static rate table. Priority = risk score × a weight that grows from 0.5 at 0 USD to 1.0 at 1,000,000 USD, so a 50,000 break comes before a 0.50 one.

`fraudml.scoring.Scorer` returns for each transaction:
- the probability and scores
- the band, exposure in USD and priority
- rule hits, each with a sentence
- up to five model factors, with plain-language reasons (in batch runs, only for rows scoring 40 or more, since explanations are the slow part)

Model factors come from LightGBM's exact TreeSHAP contributions, or coefficient × value for logistic regression.

### Results (test month 2026-08)

| Model | Test PR-AUC | Test ROC-AUC |
|---|---|---|
| Logistic regression | 0.941 | 0.965 |
| Random forest | 0.940 | 0.966 |
| LightGBM (champion) | 0.940 | 0.965 |
| LightGBM, behavioural + attributes only | 0.104 | 0.512 |
| Isolation Forest, no labels | 0.924 | 0.958 |

What the numbers mean:
- **Labelled models reproduce the rules.** The label is defined by cross-system checks, so the supervised models learn those checks almost exactly. On break types seen in training they reach 100% recall at 100% precision.
- **They miss the new break type.** "Unmapped account" first appears in August, and the model alone catches only 9% of those 194 transactions. With rule floors, recall is 100% for every break type.
- **No signal in behaviour or attributes.** Without the cross-system features the model is no better than chance (ROC-AUC 0.51), which confirms the EDA.
- **Isolation Forest works without labels.** It never sees labels, yet it finds most breaks. It is the component to lean on for break patterns nobody has labelled yet.

## API (FastAPI + PostgreSQL)

### Run it locally

```bash
cp .env.example .env              # set JWT_SECRET; the defaults suit a local Postgres
createdb fraud                    # or any database named in DATABASE_URL
make migrate                      # Alembic: creates the tables
fraudapi create-user --email admin@example.com --role admin   # asks for a password
make seed                         # loads, scores and stores June, July and August
make api                          # http://localhost:8000/docs
```

`make seed` scores with the newest model in `ml/artifacts`, so train one first (`make label train`); without a model, months load unscored. A month of 22,000 transactions is read, linked, labelled, scored and stored in about 20 seconds.

### Endpoints (`/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login` (OAuth2 password form, email as username), `GET /auth/me` |
| Users (admin) | `GET /users`, `POST /users`, `PATCH /users/{id}` |
| Health | `GET /health` (liveness), `GET /ready` (database, model and rules loaded) |
| Scoring | `POST /predictions`, `POST /predictions/batch`, `GET /predictions/{id}` |
| Transactions | `GET /transactions` (filters: period, band, score range, break type, suspicious, currency, country, account, dates, search, reviewed; sort; paging), `GET /transactions/{transaction_id}` |
| Ingestion | `POST /ingestion/upload` (GL, FA, join map and MA files, or MA from its REST API), `GET /ingestion/batches`, `GET /ingestion/batches/{id}` |
| Analytics | `GET /analytics/summary`, `/risk-distribution`, `/trends`, `/breakdown?by=currency\|country\|description\|period\|band\|break_type`, `/top-accounts` |
| Models | `GET /models`, `GET /models/active`, `GET /models/{id}/evaluation`, `POST /models/{id}/activate`, `POST /models/sync` |
| Reviews | `GET /reviews/queue`, `GET /reviews`, `POST /reviews`, `POST /reviews/{id}/approve`, `POST /reviews/{id}/reject`, `POST /reviews/bulk-approve` |
| Reports | `GET /reports/export` (CSV, same filters as `/transactions`) |
| Audit | `GET /audit` |

Roles: **analyst** scores, uploads and records review decisions; **approver** approves or rejects them; **admin** can do both and manages users and models. Every change is written to the audit log with the request id.

### How it behaves

- **Scoring a transaction.** Send one system's record, and the other systems' records of the same transaction when you have them. A record for a TransactionID that is already stored is added to it and the whole transaction is re-linked and re-scored. Sending a system's record twice returns 409. Without a TransactionID, one is generated.
- **Business rules are findings, not input errors.** Only structure is validated (a real date, a finite amount). An unsupported currency or a malformed account id is scored and reported as a rule violation, so it shows up in the queue instead of being refused.
- **Join map.** A single transaction is resolved with its month's join map, or the latest earlier month's if its own is not loaded yet.
- **Account history.** Behavioural features use the account's other stored transactions; a monthly load uses earlier months.
- **Uploads** return at once with a queued batch that runs in the background. The batch records how MA arrived (file, API or CLI), rows per source, the outcome and the duration. A failed batch keeps nothing but its own row. Reloading a month updates transactions in place, keeps their score history and review outcomes, and replaces the month's join map. Pulling MA by URL only works for hosts listed in `MA_API_ALLOWED_HOSTS`.
- **Review queue.** Transactions scoring 70 or more that have no pending or approved review, highest priority first; priority tops out at 100, so ties go to the higher risk score and then the larger USD exposure. The transaction list and CSV export use the same order by default. An analyst records "confirmed" or "false positive"; a different user with the approver role approves (the outcome is written on the transaction) or rejects it (it goes back to the queue).
- **Models.** Artifacts in `MODEL_DIR` are registered at startup (or with `POST /models/sync`). Activating a version swaps it in without a restart, and every API worker follows the switch.
- **Speed.** One transaction is scored in about 0.3 s, most of it pandas overhead on one-row frames. That is slower than the 100 ms the design aimed for and is a candidate for a fast path later.

## Dashboard (React)

### Run it locally

With the API running (`make api`), start the dashboard in a second terminal:

```bash
make web   # http://localhost:5173
```

Sign in with a user made by `fraudapi create-user`. The dev server forwards `/api` and `/docs` to port 8000, so there is no CORS setup; set `API_PROXY_TARGET` to use another API.

### Pages

| Page | What it is for |
|---|---|
| Dashboard | The month at a glance: KPIs, risk bands, daily break rate, the 10 most urgent unreviewed transactions |
| Score transaction | Submit a record (and the other systems' records if known) and get the 0–100 score, band, failed checks and reasons |
| Transactions | Every transaction with its latest score; filters, sorting and CSV export |
| Transaction detail | The three systems' records side by side with the disagreements marked, why it was flagged, score history and reviews |
| Review queue | Record findings, approve or reject them (bulk approve for approvers) |
| Analytics | Score distribution, break rate over time, break types, segments, accounts with the most breaks |
| Models | How each saved model performs and which one is active |
| Data ingestion | Load a month and follow its batch |
| Admin | Users (admin) and the audit log (approver and admin) |

What people see follows their role: analysts score, load data and record findings; approvers decide on findings and read the audit log; admins do everything. The API enforces the same rules.

### How it behaves

- **Filters live in the URL**, so a filtered view can be bookmarked or sent to someone. The CSV export uses the same filters.
- **Charts have a table view** with the same numbers. Risk bands always show an icon and a label with their colour, and the theme follows the system unless the user picks light or dark.
- **Sessions** last until the token expires or the tab is closed; a rejected token signs the user out with a message.
- **Types come from the API.** After changing the API, run `make api-types` to refresh `frontend/openapi.json` and the generated types; CI fails if they are stale.

## Tests

```bash
make test   # pytest for ml/ and backend/, Vitest for frontend/
make lint   # ruff; tsc, eslint and prettier for the frontend
```

Backend tests run against a real PostgreSQL database, which they wipe: `TEST_DATABASE_URL` (default `postgresql+psycopg://fraud:fraud@localhost:5432/fraud_test`). They generate a small synthetic dataset and train a model on it, so no real data is needed.

Frontend tests render the real pages and routes against a fake API (`frontend/src/test/server.ts`), covering sign-in, scoring, URL filters, the maker-checker rules, uploads and admin.

## Repository layout

```
docs/architecture.md   system design
ml/fraudml/            ML package (ingest, canonical, labels, eda, features, models,
                       scoring, pipeline CLI)
ml/artifacts/          saved models (git-ignored)
ml/tests/              unit and CLI tests with synthetic fixtures
backend/app/           FastAPI app: api/v1 routers, services, repositories, ORM models,
                       schemas, model registry, fraudapi CLI
backend/alembic/       database migrations
backend/tests/         API tests against PostgreSQL
frontend/src/          React dashboard: api client and hooks, auth, components, lib, pages
frontend/openapi.json  API schema the frontend's types are generated from
data/                  raw / interim / processed data and uploads (git-ignored)
```
