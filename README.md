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
| 6. Docker, CI/CD, deployment | done |

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
| Auth | `POST /auth/session`, `GET /auth/session`, `DELETE /auth/session` (the dashboard's cookie sign-in, check and sign-out), `POST /auth/login` (OAuth2 password form for API clients, email as username; returns a bearer token), `GET /auth/me` |
| Users (admin) | `GET /users`, `POST /users`, `PATCH /users/{id}` |
| Health | `GET /health` (liveness), `GET /ready` (database, model and rules loaded); `GET /metrics` (Prometheus, at the API's root, not under `/api/v1`) |
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
- **Sessions.** The dashboard signs in with `POST /auth/session`, which puts the token in an HttpOnly, SameSite=Strict cookie (Secure unless `COOKIE_SECURE=false`) that page scripts cannot read. Writes made with the cookie must send an `X-Requested-With` header, which a form on another site cannot add. API clients use `POST /auth/login` and send the token as a bearer header instead. A deactivated user is refused at their next request.
- **Rate limits.** Sign-in: 10 attempts a minute per client IP and 5 per email. Scoring: 120 transactions a minute per user, a batch counting each of its transactions. Uploads: 20 months an hour per user. Over a limit the API answers 429 with `Retry-After`. Each API process keeps its own counts, so with two workers a client can get up to twice a limit; `RATE_LIMIT_*` in `.env` changes them, and an empty value turns one off.
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
- **Sessions** use the API's HttpOnly cookie, so no token is kept where a script could read it. A session lasts across reloads and tabs until sign-out or the token's expiry (`JWT_EXPIRE_MINUTES`, 60 by default); when the API rejects it, the user is signed out with a message.
- **Types come from the API.** After changing the API, run `make api-types` to refresh `frontend/openapi.json` and the generated types; CI fails if they are stale.

## Run it with Docker

The whole app in containers: PostgreSQL, the API (two worker processes) and the dashboard behind nginx, on http://localhost:8080. Needs Docker with Compose 2.24 or later.

```bash
cp .env.example .env    # set JWT_SECRET, POSTGRES_PASSWORD and ADMIN_PASSWORD
make docker-up          # builds the images and waits until every container is healthy
make docker-demo        # synthetic data and a model; or make docker-seed for the real dataset
```

Then sign in as `ADMIN_EMAIL` with `ADMIN_PASSWORD`. `make docker-logs` follows the logs; `make docker-down` stops the stack and keeps the data (`docker compose down --volumes` deletes it).

- **Containers.** `db` is PostgreSQL 16. `migrate` applies the Alembic migrations and registers saved models, then exits; the API starts only after it succeeds, on every release. `api` is not published: only nginx in `web` reaches it, and nginx serves the dashboard and forwards `/api`. `seed` and `demo` are one-off jobs.
- **Data.** The `pgdata` volume holds the database, and `data` holds models, uploads and the business rules. The images contain code only: no data, models or secrets.
- **`make docker-demo`** generates three synthetic months (2,000 transactions each; `DEMO_ROWS` changes that), labels them, trains a model, loads and scores the months and creates the admin, in about 30 seconds. **`make docker-seed`** does the same with the real dataset, mounted read-only from `DATASET_DIR`. Running either again reloads the months in place and saves a new model version, which an admin activates on the Models page.

## Deployment

Production is one Linux server running the same compose file with `docker-compose.prod.yml` on top: Caddy serves HTTPS with a Let's Encrypt certificate, only ports 80 and 443 are open, cookies are Secure, and the images come from GitHub's container registry.

### What CI does

On every pull request, CI checks `ml/`, `backend/` and `frontend/`, then builds the whole stack in Docker, loads synthetic data and runs the browser tests. On `main`, once all of that passes, it publishes `ghcr.io/<owner>/fraud-risk-platform-api` and `-web`, tagged `sha-<commit>` and `latest`. When the server is set up, it then deploys them.

### Set up the server (once)

1. Get a Linux server with Docker Engine and the Compose plugin (2.24 or later), ports 80 and 443 open, and a DNS name pointing at it.
2. Add a user for deployments, and give CI an SSH key for it:
   ```bash
   sudo useradd --create-home --groups docker deploy
   sudo install -d -o deploy -g deploy /opt/fraud-risk-platform
   # put the public half of a new key pair in /home/deploy/.ssh/authorized_keys
   ```
3. Write `/opt/fraud-risk-platform/.env` (owned by `deploy`, mode 600) from `.env.example`: a new `JWT_SECRET`, `POSTGRES_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `DOMAIN`.
4. In the GitHub repository, under Settings, Environments, create `production` with:
   - variables `DEPLOY_HOST` (the server's name or IP) and `DEPLOY_KNOWN_HOSTS` (the output of `ssh-keyscan <host>`, checked against the server's own fingerprint), and optionally `DEPLOY_USER` (default `deploy`) and `DEPLOY_PATH` (default `/opt/fraud-risk-platform`);
   - the secret `DEPLOY_SSH_KEY`, the private half of the key pair.

   Adding required reviewers to the environment makes every deploy wait for an approval.
5. Push to `main` (or re-run the latest CI run). The deploy job copies the compose files and their configs to the server, has it pull the new images with a token that expires with the job, records them as `API_IMAGE` and `WEB_IMAGE` in `.env`, and restarts the stack; migrations run before the new API starts.
6. Load data once, on the server. Copy the dataset there, set `DATASET_DIR` in `.env`, then:
   ```bash
   cd /opt/fraud-risk-platform
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm seed
   ```
   The seed creates the admin; `ADMIN_PASSWORD` can then be removed from `.env`.

### Operating it

- **Rolling back.** Re-run the deploy job of an earlier CI run, or set `API_IMAGE` and `WEB_IMAGE` in the server's `.env` to an earlier `sha-` tag and run `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`. Migrations only move forward, so going back past a schema change needs `alembic downgrade` first. A model is rolled back separately, by activating an earlier version on the Models page.
- **Backups.** The database, and the `data` volume with models, uploads and rules:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U fraud -Fc fraud > fraud.dump
  docker run --rm -v fraud-risk-platform_data:/data -v "$PWD":/backup alpine tar czf /backup/data.tgz -C /data .
  ```
- **Monitoring.** The API serves Prometheus metrics at `/metrics`: requests by route and status with latency, scored transactions by band and source with the score distribution, month loads, review outcomes (approved findings by decision are the live precision signal), rate-limited requests and the active model. nginx does not forward it, so it is not public; `docker compose --profile monitoring up -d prometheus` starts a Prometheus that scrapes it, on `127.0.0.1:9090` (reach it through an SSH tunnel). The containers' health checks use `/api/v1/health`; `/api/v1/ready` also checks the database, the model and the rules.
- **Security headers.** nginx sends a strict Content-Security-Policy (scripts, styles and requests only from the site itself), `X-Frame-Options: DENY`, `nosniff` and `no-referrer`; Caddy adds HSTS. The browser tests fail when a page logs a CSP violation.
- **Disk.** A release usually adds only a few megabytes, because Python dependencies sit in their own image layer. `docker image prune -a` removes images no container uses.
- **Other hosts.** The images are configured only through environment variables, so a managed platform can run them too: the API image with `migrate` as its release command and `serve` as its start command, the web image with `API_UPSTREAM` set to the API's host and port, and a managed PostgreSQL.

## Tests

```bash
make test   # pytest for ml/ and backend/, Vitest for frontend/
make lint   # ruff; tsc, eslint and prettier for the frontend
make e2e    # Playwright browser tests against the Docker stack (after make docker-up docker-demo)
```

Backend tests run against a real PostgreSQL database, which they wipe: `TEST_DATABASE_URL` (default `postgresql+psycopg://fraud:fraud@localhost:5432/fraud_test`). They generate a small synthetic dataset and train a model on it, so no real data is needed.

Frontend tests render the real pages and routes against a fake API (`frontend/src/test/server.ts`), covering sign-in, scoring, URL filters, the maker-checker rules, uploads and admin.

Browser tests (`frontend/e2e/`) drive Chromium through the running stack with the demo data: cookie sign-in and sign-out, every page for each role, scoring, an analyst's finding approved and another rejected by an approver, filters with CSV export, adding and deactivating a user, the security headers and the CSRF check. Each test also fails if a page logs an error or a CSP violation. They sign in as the admin from `.env` and add `e2e-analyst@example.com` and `e2e-approver@example.com` with a new random password on every run, so point them only at a local or CI stack (`E2E_BASE_URL`, default http://localhost:8080). Install the browser once with `cd frontend && npx playwright install chromium`. Two runs within a minute can reach the sign-in rate limit; `RATE_LIMIT_LOGIN=` in `.env` turns it off locally.

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
frontend/e2e/          Playwright browser tests against the running stack
infra/                 Dockerfiles, and the nginx, Caddy and Prometheus configs
docker-compose.yml     the whole app on one machine; docker-compose.prod.yml adds HTTPS
.github/workflows/     CI: checks, browser tests, image publishing and deploy
data/                  raw / interim / processed data and uploads (git-ignored)
```
