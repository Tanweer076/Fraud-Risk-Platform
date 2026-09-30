"""Canonical record schema shared by every source system."""

SYSTEMS = ("gl", "ma", "fa")

# Column that holds each system's own account key in the canonical frame.
ACCOUNT_KEY_FIELD = {"gl": "gl_account_id", "ma": "ma_customer_key", "fa": "fa_key"}

CANONICAL_COLUMNS = [
    "transaction_id",
    "source_system",
    "account_key",
    "transaction_date_raw",
    "transaction_date",
    "amount",
    "currency",
    "country",
    "description",
]

# Source column name -> canonical column name. The account key column differs per system.
SOURCE_TO_CANONICAL = {
    "TransactionID": "transaction_id",
    "TransactionDate": "transaction_date_raw",
    "Amount": "amount",
    "Currency": "currency",
    "Country": "country",
    "Description": "description",
}
