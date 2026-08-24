from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from devops_coach.planner import ensure_master_plan


def _copy_static(root: Path, target: Path) -> None:
    for name in ("config", "curriculum", "schemas"):
        shutil.copytree(root / name, target / name)


def _empty_v2_state() -> dict[str, object]:
    phase_ids = (
        "foundations",
        "systems_automation",
        "containers_cicd",
        "aws_iac",
        "kubernetes_sre",
        "career_capstone",
    )
    return {
        "schema_version": 2,
        "current_week": 1,
        "current_phase": "foundations",
        "weekly_plans": {},
        "tasks": {},
        "blockers": [],
        "completion_log": [],
        "portfolio": [],
        "career": {
            "accepted_open_source_contributions": 0,
            "applications": 0,
            "english_demos": 0,
            "mock_interviews": 0,
        },
        "adaptation": {
            "mode": "standard",
            "reason": "test baseline",
            "source_week": None,
            "generated_at": None,
        },
        "weekly_reviews": {},
        "phase_gates": {
            phase_id: {
                "status": "active" if index == 0 else "locked",
                "score": None,
                "evidence": None,
            }
            for index, phase_id in enumerate(phase_ids)
        },
        "updated_at": "2026-07-29T00:00:00+08:00",
    }


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    _copy_static(root, tmp_path)
    state_path = tmp_path / "state" / "progress.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(_empty_v2_state(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ensure_master_plan(tmp_path)
    return tmp_path


def _legacy_task(task_id: str, day: str, status: str, evidence: str | None) -> dict[str, object]:
    return {
        "id": task_id,
        "date": day,
        "section": "legacy",
        "title": f"Legacy {task_id}",
        "planned_minutes": 75,
        "actual_minutes": 15 if evidence else 0,
        "status": status,
        "score": 4 if status in {"done", "partial"} else None,
        "evidence": evidence,
        "carryovers": 0,
        "next_review": None,
    }


@pytest.fixture
def migration_project(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    _copy_static(root, tmp_path)
    config = yaml.safe_load((tmp_path / "config" / "learner.yml").read_text(encoding="utf-8"))
    config["schema_version"] = 1
    config["learner"]["schedule"] = {
        "weekday_minutes": 75,
        "saturday_minutes": 0,
        "sunday_minutes": 0,
        "minimum_session_minutes": 15,
    }
    config["learner"]["engagement"] = {
        "style": "incident_mission",
        "show_weekday_streak": True,
    }
    (tmp_path / "config" / "learner.yml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    tasks = {
        "2026-08-03-work": _legacy_task(
            "2026-08-03-work", "2026-08-03", "done", "verified historical work"
        ),
        "2026-08-08-project": _legacy_task("2026-08-08-project", "2026-08-08", "planned", None),
        "2026-08-08-review": _legacy_task("2026-08-08-review", "2026-08-08", "planned", None),
        "2026-08-21-mission": _legacy_task(
            "2026-08-21-mission", "2026-08-21", "partial", "legacy package evidence"
        ),
    }
    state = {
        "schema_version": 1,
        "current_week": 4,
        "current_phase": "foundations",
        "daily_plans": {
            "2026-08-03": {
                "path": "plans/2026/08/2026-08-03.md",
                "week": 1,
                "phase": "foundations",
                "planned_minutes": 75,
                "actual_minutes": 15,
                "task_ids": ["2026-08-03-work"],
                "status": "planned",
            },
            "2026-08-08": {
                "path": "plans/2026/08/2026-08-08.md",
                "week": 2,
                "phase": "foundations",
                "planned_minutes": 180,
                "task_ids": ["2026-08-08-project", "2026-08-08-review"],
                "status": "done",
            },
            "2026-08-21": {
                "path": "plans/2026/08/2026-08-21.md",
                "week": 4,
                "phase": "foundations",
                "planned_minutes": 75,
                "actual_minutes": 75,
                "task_ids": ["2026-08-21-mission"],
                "status": "partial",
            },
        },
        "tasks": tasks,
        "blockers": [],
        "portfolio": [],
        "career": {
            "accepted_open_source_contributions": 0,
            "applications": 0,
            "english_demos": 0,
            "mock_interviews": 0,
        },
        "adaptation": {
            "load_factor": 1.0,
            "reason": "legacy",
            "source_week": None,
            "generated_at": None,
        },
        "weekly_reviews": {},
        "updated_at": "2026-08-21T10:13:01+08:00",
    }
    state_path = tmp_path / "state" / "progress.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old_plan = tmp_path / "plans" / "2026" / "08" / "2026-08-08.md"
    old_plan.parent.mkdir(parents=True)
    old_plan.write_text("# Immutable historical plan\n", encoding="utf-8")
    draft = tmp_path / "evidence" / "week-02" / "linux-file-search-runbook" / "README.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("# Draft Runbook\n", encoding="utf-8")
    return tmp_path
