from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    for name in ("config", "curriculum", "schemas", "state"):
        shutil.copytree(root / name, tmp_path / name)

    state_path = tmp_path / "state" / "progress.json"
    progress = json.loads(state_path.read_text(encoding="utf-8"))
    progress.update(
        {
            "current_week": 1,
            "current_phase": "foundations",
            "daily_plans": {},
            "tasks": {},
            "blockers": [],
            "portfolio": [],
            "career": {
                "accepted_open_source_contributions": 0,
                "applications": 0,
                "english_demos": 0,
                "mock_interviews": 0,
            },
            "adaptation": {
                "generated_at": None,
                "load_factor": 1.0,
                "reason": "test baseline",
                "source_week": None,
            },
            "weekly_reviews": {},
            "updated_at": "2026-07-29T00:00:00+08:00",
        }
    )
    state_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return tmp_path
