"""Loading the business rules file (RULES_PATH)."""

import logging

from fraudml.errors import IngestionError
from fraudml.ingest.rules import Rule, parse_rules

from app.core.config import Settings

log = logging.getLogger("app")


def load_rules(settings: Settings) -> list[Rule] | None:
    """The parsed rules, or None (logged) when the file is missing or unreadable."""
    try:
        rules = parse_rules(settings.rules_path)
    except IngestionError as exc:
        log.error("Business rules not loaded: %s", exc)
        return None
    log.info("Loaded %d business rules from %s", len(rules), settings.rules_path)
    return rules
