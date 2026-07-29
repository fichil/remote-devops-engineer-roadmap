from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    for name in ("config", "curriculum", "schemas", "state"):
        shutil.copytree(root / name, tmp_path / name)
    return tmp_path
