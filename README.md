# Fraud Risk Platform

End-to-end transaction fraud detection and risk scoring: ML models that turn a transaction into a 0–100 risk score with explanations, served by FastAPI, stored in PostgreSQL and shown in a React dashboard.

The data comes from three financial systems that record the same transactions (GL, MA, FA). A transaction is treated as suspicious when those systems disagree about it or it breaks a business rule. See `docs/architecture.md` for the full design.

Status: under construction.
