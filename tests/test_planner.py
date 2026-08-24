from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from devops_coach.planner import (
    completion_streak,
    ensure_week_plan,
    record_checkpoint,
    today_overview,
)
from devops_coach.storage import load_json, write_json


def _old_task(task_id: str, created_on: str, queue_order: int) -> dict[str, Any]:
    return {
        "id": task_id,
        "created_on": created_on,
        "scheduled_for": created_on,
        "curriculum_week": 1,
        "phase": "foundations",
        "section": "legacy",
        "title": f"Old task {task_id}",
        "status": "queued",
        "score": None,
        "evidence": None,
        "completed_on": None,
        "next_review": None,
        "queue_order": queue_order,
        "source": "test",
        "checkpoints": [
            {
                "id": "work",
                "title": "历史任务",
                "instruction": "Complete the old task.",
                "status": "queued",
                "score": None,
                "evidence": None,
                "next_review": None,
            }
        ],
    }


def _complete_task(project: Path, task_id: str, completed_on: date, score: int = 4) -> None:
    state = load_json(project / "state" / "progress.json")
    checkpoint_ids = [item["id"] for item in state["tasks"][task_id]["checkpoints"]]
    for checkpoint_id in checkpoint_ids:
        record_checkpoint(
            project,
            task_id,
            checkpoint_id,
            "done",
            score,
            f"verified {task_id} {checkpoint_id}",
            completed_on,
        )


def _forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.endswith("_minutes") or key in {"minutes", "load_factor"} or _forbidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_forbidden_key(child) for child in value)
    return False


def test_week_plan_creates_one_calendar_workweek(project_copy: Path) -> None:
    path, created = ensure_week_plan(project_copy, "2026-W34")
    state = load_json(project_copy / "state" / "progress.json")
    plan = state["weekly_plans"]["2026-W34"]

    assert created is True
    assert path == project_copy / "plans" / "weeks" / "2026-W34.md"
    assert plan["monday"] == "2026-08-17"
    assert plan["friday"] == "2026-08-21"
    assert plan["week"] == 4
    assert len(plan["new_task_ids"]) == 5
    assert len(plan["execution_slots"]) == 5
    assert plan["execution_slots"] == plan["new_task_ids"]
    assert all(len(state["tasks"][task_id]["checkpoints"]) == 3 for task_id in plan["new_task_ids"])
    content = path.read_text(encoding="utf-8")
    assert "进程、服务与软件包" in content
    assert "事件简报" in content
    assert "英文书面交接" in content


def test_week_plan_is_created_once_and_then_resumed(project_copy: Path) -> None:
    first_path, first_created = ensure_week_plan(project_copy, "2026-W34")
    first_state = (project_copy / "state" / "progress.json").read_bytes()
    first_content = first_path.read_bytes()

    second_path, second_created = ensure_week_plan(project_copy, "2026-W34")

    assert first_created is True
    assert second_created is False
    assert second_path == first_path
    assert (project_copy / "state" / "progress.json").read_bytes() == first_state
    assert second_path.read_bytes() == first_content


def test_today_lists_all_backlog_but_starts_scheduled_task_without_daily_file(
    project_copy: Path,
) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-30", 1)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-31", 2)
    write_json(state_path, state)

    overview = today_overview(project_copy, date(2026, 8, 5))
    state = load_json(state_path)

    assert overview["today"]["active_task"]["id"] == "2026-W32-03-mission"
    assert overview["today"]["active_task_kind"] == "primary"
    assert overview["today"]["next_checkpoint"]["id"] == "briefing"
    assert overview["week"]["backlog"] == [
        "old-1",
        "old-2",
        "2026-W32-01-mission",
        "2026-W32-02-mission",
    ]
    assert overview["project"]["backlog_count"] == 4
    assert state["tasks"]["old-1"]["status"] == "queued"
    assert state["tasks"]["old-2"]["status"] == "queued"
    assert state["weekly_plans"]["2026-W32"]["execution_slots"] == state[
        "weekly_plans"
    ]["2026-W32"]["new_task_ids"]
    assert not (project_copy / "plans" / "2026" / "08" / "2026-08-05.md").exists()


def test_weekend_today_is_read_only_rest(project_copy: Path) -> None:
    state_path = project_copy / "state" / "progress.json"
    before = state_path.read_bytes()

    overview = today_overview(project_copy, date(2026, 8, 1))

    assert overview["today"]["rest"] is True
    assert overview["today"]["quota"] == 0
    assert state_path.read_bytes() == before
    assert not (project_copy / "plans" / "weeks" / "2026-W31.md").exists()


def test_calendar_theme_advances_but_phase_gate_blocks_next_phase(
    project_copy: Path,
) -> None:
    _, created = ensure_week_plan(project_copy, "2026-W44")
    state = load_json(project_copy / "state" / "progress.json")
    plan = state["weekly_plans"]["2026-W44"]

    assert created is True
    assert plan["week"] == 14
    assert plan["calendar_phase"] == "systems_automation"
    assert plan["execution_phase"] == "foundations"
    assert plan["gate_mode"] == "remediation"
    assert all(
        state["tasks"][task_id]["title"].startswith(("Gate Reteach", "Gate Retest"))
        for task_id in plan["new_task_ids"]
    )

    gate_task = plan["new_task_ids"][-1]
    _complete_task(project_copy, gate_task, date(2026, 10, 30))
    state = load_json(project_copy / "state" / "progress.json")
    assert state["phase_gates"]["foundations"]["status"] == "passed"

    ensure_week_plan(project_copy, "2026-W45")
    state = load_json(project_copy / "state" / "progress.json")
    next_plan = state["weekly_plans"]["2026-W45"]
    assert next_plan["calendar_phase"] == "systems_automation"
    assert next_plan["execution_phase"] == "systems_automation"
    assert next_plan["gate_mode"] == "normal"


def test_primary_stops_by_default_and_explicit_continue_starts_oldest_carryover(
    project_copy: Path,
) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-27", 1)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-28", 2)
    write_json(state_path, state)
    target = date(2026, 7, 29)
    first = today_overview(project_copy, target)
    task_id = first["today"]["active_task"]["id"]
    _complete_task(project_copy, task_id, target)

    resumed = today_overview(project_copy, target)
    state = load_json(state_path)

    assert resumed["today"]["quota_complete"] is True
    assert resumed["today"]["active_task"] is None
    assert resumed["today"]["completed_task"] == task_id
    assert resumed["today"]["optional_carryover_available"] is True
    assert state["tasks"]["old-1"]["status"] == "queued"

    continued = today_overview(project_copy, target, continue_carryover=True)
    state = load_json(state_path)

    assert continued["today"]["active_task"]["id"] == "old-1"
    assert continued["today"]["active_task_kind"] == "carryover"
    assert state["tasks"]["old-1"]["status"] == "in_progress"


def test_carryover_requires_primary_and_daily_limit_is_two(project_copy: Path) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-27", 1)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-28", 2)
    write_json(state_path, state)
    target = date(2026, 7, 29)
    today_overview(project_copy, target)

    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="primary task"):
        today_overview(project_copy, target, continue_carryover=True)
    assert state_path.read_bytes() == before

    primary_id = "2026-W31-03-mission"
    _complete_task(project_copy, primary_id, target)

    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="--continue-carryover"):
        record_checkpoint(
            project_copy,
            "old-1",
            "work",
            "done",
            4,
            "must require explicit continuation",
            target,
        )
    assert state_path.read_bytes() == before

    today_overview(project_copy, target, continue_carryover=True)
    _complete_task(project_copy, "old-1", target)
    completed = load_json(state_path)
    assert [item["task_id"] for item in completed["completion_log"]] == [
        primary_id,
        "old-1",
    ]
    assert completion_streak(completed, target, target) == (1, 1)

    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="--continue-carryover"):
        record_checkpoint(
            project_copy,
            "old-2",
            "work",
            "done",
            4,
            "verified third task rejection",
            target,
        )
    assert state_path.read_bytes() == before


def test_record_requires_evidence_and_schedules_reteaching(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W31")
    task_id = "2026-W31-03-mission"
    with pytest.raises(ValueError, match="require evidence"):
        record_checkpoint(
            project_copy,
            task_id,
            "briefing",
            "in_progress",
            2,
            "",
            date(2026, 7, 29),
        )

    task = record_checkpoint(
        project_copy,
        task_id,
        "briefing",
        "in_progress",
        2,
        "verified knowledge gap",
        date(2026, 7, 29),
    )
    checkpoint = task["checkpoints"][0]
    assert checkpoint["next_review"] == "2026-07-31"
    assert task["status"] == "in_progress"
    assert not load_json(project_copy / "state" / "progress.json")["completion_log"]


def test_recorded_artifacts_are_repository_contained_and_follow_completion(
    project_copy: Path,
) -> None:
    target = date(2026, 7, 29)
    ensure_week_plan(project_copy, "2026-W31")
    task_id = "2026-W31-03-mission"
    artifact = project_copy / "evidence" / "git" / "verification.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("verified output\n", encoding="utf-8")
    checkpoint_ids = ["briefing", "lab", "written_handoff"]
    for checkpoint_id in checkpoint_ids:
        record_checkpoint(
            project_copy,
            task_id,
            checkpoint_id,
            "done",
            4,
            f"verified {checkpoint_id}",
            target,
            artifacts=[artifact] if checkpoint_id == "lab" else (),
        )

    state = load_json(project_copy / "state" / "progress.json")
    task = state["tasks"][task_id]
    completion = state["completion_log"][0]

    assert task["artifacts"] == ["evidence/git/verification.txt"]
    assert completion["kind"] == "primary"
    assert completion["artifacts"] == ["evidence/git/verification.txt"]

    before = (project_copy / "state" / "progress.json").read_bytes()
    with pytest.raises(ValueError, match="inside the repository"):
        record_checkpoint(
            project_copy,
            "2026-W31-04-mission",
            "briefing",
            "done",
            4,
            "outside artifact rejection",
            date(2026, 7, 30),
            artifacts=[project_copy.parent / "outside.txt"],
        )
    assert (project_copy / "state" / "progress.json").read_bytes() == before


def test_completion_streak_requires_full_evidence_task_and_skips_weekend(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W31")
    ensure_week_plan(project_copy, "2026-W32")
    _complete_task(project_copy, "2026-W31-05-mission", date(2026, 7, 31))
    _complete_task(project_copy, "2026-W32-01-mission", date(2026, 8, 3))
    state = load_json(project_copy / "state" / "progress.json")

    assert completion_streak(state, date(2026, 7, 29), date(2026, 8, 3)) == (2, 2)

    _complete_task(project_copy, "2026-W32-03-mission", date(2026, 8, 5))
    state = load_json(project_copy / "state" / "progress.json")
    assert completion_streak(state, date(2026, 7, 29), date(2026, 8, 5)) == (1, 2)


def test_active_state_and_new_plans_have_no_time_fields(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W34")
    state = load_json(project_copy / "state" / "progress.json")
    learner = (project_copy / "config" / "learner.yml").read_text(encoding="utf-8")
    master = (project_copy / "plans" / "master-plan.md").read_text(encoding="utf-8")
    week = (project_copy / "plans" / "weeks" / "2026-W34.md").read_text(encoding="utf-8")

    assert not _forbidden_key(state)
    state_text = json.dumps(state, ensure_ascii=False).lower()
    assert "分钟" not in state_text
    assert " minutes" not in state_text
    assert "_minutes" not in learner
    assert "load_factor" not in learner
    assert "预计时间" not in master + week
    assert "总时长" not in master + week
