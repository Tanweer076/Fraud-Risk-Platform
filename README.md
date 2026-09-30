# Fraud Risk Platform

End-to-end transaction fraud detection and risk scoring: ML models that turn a transaction into a 0–100 risk score with explanations, served by FastAPI, stored in PostgreSQL and shown in a React dashboard.

The data comes from three financial systems that record the same transactions: General Ledger (GL, XML), Management Accounting (MA, REST API) and Financial Accounting (FA, CSV). A transaction is **suspicious** when those systems disagree about it or it breaks a business rule. That derived label is what the models learn to predict. See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Status

| Step | State |
|---|---|
| 1. Ingestion, linking, break labelling | done |
| 2. EDA report | done |
| 3. Features, models, risk score, explanations | done |
| 4. PostgreSQL + FastAPI | next |
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

`fraudml.scoring.Scorer` returns for each transaction:
- the probability and scores
- the band
- rule hits, each with a sentence
- up to five model factors, with plain-language reasons

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

## Tests

```bash
make test   # pytest, positive and negative cases
make lint   # ruff
```

## Repository layout

```
docs/architecture.md   system design
ml/fraudml/            ML package (ingest, canonical, labels, eda, features, models,
                       scoring, pipeline CLI)
ml/artifacts/          saved models (git-ignored)
ml/tests/              unit and CLI tests with synthetic fixtures
data/                  raw / interim / processed data (git-ignored)
```
