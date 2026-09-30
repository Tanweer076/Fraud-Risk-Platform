"""Command line tasks: create users, load months of data, register models.

fraudapi create-user --email admin@example.com --role admin
fraudapi ingest --month-dir "data/raw/OneRecon_DataSet/Historical Data/june" ...
fraudapi sync-models
"""

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

from fraudml.errors import IngestionError
from fraudml.ingest.rules import parse_rules
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import make_engine, make_sessionmaker
from app.ml.registry import ModelRegistry
from app.models import IngestionBatch
from app.schemas.auth import UserCreate
from app.services import ingestion, users

log = logging.getLogger("app.cli")


def _create_user(args, settings, make_session) -> int:
    password = args.password or os.environ.get("FRAUDAPI_PASSWORD")
    if not password:
        password = getpass.getpass("Password (12+ characters): ")
    try:
        data = UserCreate(
            email=args.email, full_name=args.full_name, password=password, role=args.role
        )
    except ValidationError as exc:
        for error in exc.errors():  # not str(exc): that would echo the password
            print(f"{'.'.join(map(str, error['loc']))}: {error['msg']}", file=sys.stderr)
        return 1
    with make_session() as db:
        try:
            user = users.create_user(db, settings, data, actor=None)
        except AppError as exc:
            print(exc.detail, file=sys.stderr)
            return 1
    print(f"Created {user.role} {user.email} (id {user.id})")
    return 0


def _ingest(args, settings, make_session) -> int:
    rules = parse_rules(args.rules or settings.rules_path)
    registry = ModelRegistry(settings.model_dir)
    with make_session() as db:
        registry.sync(db)
    failed = 0
    for month_dir in args.month_dir:
        try:
            period, paths = ingestion.find_month_files(Path(month_dir))
        except IngestionError as exc:
            print(exc, file=sys.stderr)
            failed += 1
            continue
        with make_session() as db:
            files = {source: path.name for source, path in paths.items()}
            batch_id = ingestion.create_batch(db, period, "cli", files, None).id
        ingestion.run_batch(make_session, registry, rules, settings, batch_id, paths)
        with make_session() as db:
            batch = db.get(IngestionBatch, batch_id)
            print(
                f"{period}: {batch.status}, {batch.transactions_loaded} transactions, "
                f"{batch.summary.get('suspicious', 0)} suspicious, "
                f"{batch.transactions_scored} scored in {batch.duration_ms} ms"
                + (f" ({batch.error})" if batch.error else "")
            )
            failed += batch.status != "succeeded"
    return 1 if failed else 0


def _sync_models(args, settings, make_session) -> int:
    registry = ModelRegistry(settings.model_dir)
    with make_session() as db:
        registry.sync(db)
    print(f"Active model: {registry.loaded_version or 'none'}")
    return 0 if registry.loaded_version else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fraudapi")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-user", help="Create a user (admin, approver or analyst)")
    p.add_argument("--email", required=True)
    p.add_argument("--role", required=True, choices=["analyst", "approver", "admin"])
    p.add_argument("--full-name", default="")
    p.add_argument("--password", help="Defaults to $FRAUDAPI_PASSWORD, else asks")
    p.set_defaults(handler=_create_user)

    p = sub.add_parser("ingest", help="Load month folders laid out like the OneRecon dataset")
    p.add_argument("--month-dir", action="append", required=True, help="Repeat, oldest first")
    p.add_argument("--rules", type=Path, help="Defaults to RULES_PATH")
    p.set_defaults(handler=_ingest)

    p = sub.add_parser("sync-models", help="Register artifacts in MODEL_DIR and load the active")
    p.set_defaults(handler=_sync_models)

    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    try:
        return args.handler(args, settings, make_sessionmaker(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
