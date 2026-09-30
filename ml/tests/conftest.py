from pathlib import Path

import pytest

from fraudml.testing import RULES


@pytest.fixture
def rules_path(tmp_path: Path) -> Path:
    path = tmp_path / "business_rules.txt"
    path.write_text(RULES)
    return path
