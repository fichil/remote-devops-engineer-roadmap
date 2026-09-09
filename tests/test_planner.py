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
from devops_coach.publication_identity import (
    LEDGER_PATH,
    legacy_publication_key,
    publication_key,
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
    for checkpoint in state["tasks"][task_id]["checkpoints"]:
        checkpoint_id = checkpoint["id"]
        record_checkpoint(
            project,
            task_id,
            checkpoint_id,
            "done",
            None if checkpoint.get("assessment") == "formative" else score,
            f"verified {task_id} {checkpoint_id}",
            completed_on,
            hint_level_used=0,
            independent=True,
            evidence_details={
                "prediction": "The selected scope should exclude unrelated items.",
                "learner_action": "Ran the independently selected scope check.",
                "observed_result": "Only target items were returned.",
                "interpretation": "The selected scope matches the requested boundary.",
                "handoff": "The scope check passed. Unrelated items were excluded.",
            },
        )


def _mark_publication_complete(
    project: Path,
    target: date,
    task_id: str,
    kind: str,
    *,
    legacy: bool = False,
) -> None:
    path = project / LEDGER_PATH
    ledger = load_json(path) if path.exists() else {"schema_version": 2, "publications": {}}
    key = (
        legacy_publication_key(target, kind)
        if legacy
        else publication_key(target, kind, task_id if kind == "carryover" else None)
    )
    ledger["publications"][key] = {
        "date": target.isoformat(),
        "kind": kind,
        "status": "complete",
        "task_id": task_id,
    }
    write_json(path, ledger)


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
    assert "讲解与示范" in content
    assert "独立迁移与交付" in content


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


def test_calendar_theme_advances_but_phase_gate_uses_concrete_retest_blueprint(
    project_copy: Path,
) -> None:
    path, created = ensure_week_plan(project_copy, "2026-W44")
    state = load_json(project_copy / "state" / "progress.json")
    plan = state["weekly_plans"]["2026-W44"]

    assert created is True
    assert path.exists()
    assert plan["week"] == 14
    assert plan["calendar_phase"] == "systems_automation"
    assert plan["execution_phase"] == "foundations"
    assert plan["gate_mode"] == "remediation"
    tasks = [state["tasks"][task_id] for task_id in plan["new_task_ids"]]
    assert all(task["curriculum_week"] == 13 for task in tasks)
    assert all(task["weekly_project_id"] == "foundation-gate-incident" for task in tasks)
    assert all(task["title"].startswith("Gate ") for task in tasks)
    assert len({task["learning_goal"] for task in tasks}) == 5
    assert tasks[-1]["gate_id"] == "foundations"


def test_remediation_gate_passes_only_from_independent_summative_score(
    project_copy: Path,
) -> None:
    target = date(2026, 10, 30)
    ensure_week_plan(project_copy, "2026-W44")
    task_id = "2026-W44-05-mission"
    record_checkpoint(
        project_copy,
        task_id,
        "briefing",
        "done",
        None,
        "learner concept explanation and prediction",
        target,
    )
    record_checkpoint(
        project_copy,
        task_id,
        "lab",
        "done",
        None,
        "guided practice result and explanation",
        target,
        hint_level_used=2,
    )
    record_checkpoint(
        project_copy,
        task_id,
        "written_handoff",
        "done",
        4,
        "independent changed-condition evidence",
        target,
        hint_level_used=0,
        independent=True,
        evidence_details={
            "prediction": "The changed listener will fail the old health check.",
            "learner_action": "I selected and ran a new layered verification.",
            "observed_result": "The process listened on the changed port.",
            "interpretation": "The old endpoint was stale, not the process state.",
            "handoff": "The service is healthy on the new port. The old check is stale.",
        },
    )
    state = load_json(project_copy / "state" / "progress.json")

    assert state["tasks"][task_id]["score"] == 4
    assert state["phase_gates"]["foundations"] == {
        "status": "passed",
        "score": 4,
        "evidence": state["tasks"][task_id]["evidence"],
    }
    before = (project_copy / "state" / "progress.json").read_bytes()
    with pytest.raises(ValueError, match="Missing training blueprint.*week 15"):
        ensure_week_plan(project_copy, "2026-W45")
    assert (project_copy / "state" / "progress.json").read_bytes() == before


def test_missing_training_blueprint_blocks_without_generic_tasks_or_writes(
    project_copy: Path,
) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["phase_gates"]["foundations"] = {
        "status": "passed",
        "score": 4,
        "evidence": "verified foundation gate",
    }
    write_json(state_path, state)
    before = state_path.read_bytes()

    with pytest.raises(ValueError, match="Missing training blueprint.*week 14"):
        ensure_week_plan(project_copy, "2026-W44")

    assert state_path.read_bytes() == before
    assert not (project_copy / "plans" / "weeks" / "2026-W44.md").exists()


def test_cognitive_week_uses_blueprint_and_today_exposes_teaching_contract(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W35")
    overview = today_overview(project_copy, date(2026, 8, 24))
    state = load_json(project_copy / "state" / "progress.json")
    task = state["tasks"]["2026-W35-01-mission"]

    assert state["workflow_version"] == "cognitive_apprenticeship_v1"
    assert task["workflow_version"] == "cognitive_apprenticeship_v1"
    assert task["weekly_project_id"] == "local-git-change-control"
    assert [item["title"] for item in task["checkpoints"]] == [
        "讲解与示范",
        "引导练习",
        "独立迁移与交付",
    ]
    assert [item["assessment"] for item in task["checkpoints"]] == [
        "formative",
        "formative",
        "summative",
    ]
    active = overview["today"]["active_task"]
    checkpoint = overview["today"]["next_checkpoint"]
    assert active["scenario"]
    assert active["learning_goal"] == task["learning_goal"]
    assert active["weekly_project"]["id"] == task["weekly_project_id"]
    assert active["weekly_project"]["lab_week"] == "2026-W35"
    assert active["weekly_project"]["lab_root"] == "private/labs/2026-W35"
    assert active["weekly_project"]["worktree"].endswith("/work")
    assert "YYYY-Www" not in active["weekly_project"]["environment"]
    assert checkpoint["assessment"] == "formative"
    assert checkpoint["coach_action"]
    assert checkpoint["learner_action"]
    assert checkpoint["hint_policy"]
    assert checkpoint["success_criteria"]


def test_cognitive_scoring_requires_independent_structured_summative_evidence(
    project_copy: Path,
) -> None:
    target = date(2026, 8, 24)
    ensure_week_plan(project_copy, "2026-W35")
    task_id = "2026-W35-01-mission"

    with pytest.raises(ValueError, match="do not accept a score"):
        record_checkpoint(
            project_copy, task_id, "briefing", "done", 4, "copied answer", target
        )
    record_checkpoint(
        project_copy, task_id, "briefing", "done", None, "own prediction", target
    )
    record_checkpoint(
        project_copy, task_id, "lab", "done", None, "guided evidence", target,
        hint_level_used=2,
    )
    details = {
        "prediction": "The branch will be ahead by one commit.",
        "learner_action": "I selected and ran the comparison command.",
        "observed_result": "The output showed one local-only commit.",
        "interpretation": "The local commit has not reached the remote.",
        "handoff": "The branch is one commit ahead. Please review before push.",
    }
    with pytest.raises(ValueError, match="independent variation"):
        record_checkpoint(
            project_copy,
            task_id,
            "written_handoff",
            "done",
            4,
            "structured independent evidence",
            target,
            hint_level_used=1,
            independent=True,
            evidence_details=details,
        )

    task = record_checkpoint(
        project_copy,
        task_id,
        "written_handoff",
        "done",
        4,
        "structured independent evidence",
        target,
        hint_level_used=0,
        independent=True,
        evidence_details=details,
    )

    assert task["status"] == "done"
    assert task["score"] == 4
    assert task["checkpoints"][0]["score"] is None
    assert task["checkpoints"][1]["score"] is None


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
    _mark_publication_complete(project_copy, target, task_id, "primary")

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


def test_carryover_requires_publication_and_allows_three_with_explicit_requests(
    project_copy: Path,
) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-27", 1)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-28", 2)
    state["tasks"]["old-3"] = _old_task("old-3", "2026-07-28", 3)
    write_json(state_path, state)
    target = date(2026, 7, 29)
    today_overview(project_copy, target)
    state = load_json(state_path)
    state["tasks"]["2026-W31-01-mission"]["status"] = "cancelled"
    state["tasks"]["2026-W31-02-mission"]["status"] = "cancelled"
    write_json(state_path, state)

    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="primary task"):
        today_overview(project_copy, target, continue_carryover=True)
    assert state_path.read_bytes() == before

    primary_id = "2026-W31-03-mission"
    _complete_task(project_copy, primary_id, target)

    blocked = today_overview(project_copy, target)
    assert blocked["today"]["optional_carryover_available"] is False
    assert blocked["today"]["publication_pending_task_ids"] == [primary_id]
    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="recover publication"):
        today_overview(project_copy, target, continue_carryover=True)
    assert state_path.read_bytes() == before

    _mark_publication_complete(project_copy, target, primary_id, "primary")

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

    for index, task_id in enumerate(("old-1", "old-2", "old-3"), start=1):
        today_overview(project_copy, target, continue_carryover=True)
        _complete_task(project_copy, task_id, target)
        completed = load_json(state_path)
        stopped = today_overview(project_copy, target)

        assert stopped["today"]["active_task"] is None
        assert stopped["today"]["optional_carryover_limit"] is None
        assert stopped["today"]["optional_carryover_completed_count"] == index
        assert stopped["today"]["optional_carryover_completed_task_ids"] == [
            f"old-{item}" for item in range(1, index + 1)
        ]
        assert stopped["today"]["optional_carryover_complete"] is True
        assert stopped["today"]["publication_pending_task_ids"] == [task_id]

        if task_id != "old-3":
            before = state_path.read_bytes()
            with pytest.raises(ValueError, match="recover publication"):
                today_overview(project_copy, target, continue_carryover=True)
            assert state_path.read_bytes() == before

        _mark_publication_complete(
            project_copy,
            target,
            task_id,
            "carryover",
            legacy=task_id == "old-1",
        )

        if task_id != "old-3":
            available = today_overview(project_copy, target)
            assert available["today"]["active_task"] is None
            assert available["today"]["optional_carryover_available"] is True

    completed = load_json(state_path)
    assert [item["task_id"] for item in completed["completion_log"]] == [
        primary_id,
        "old-1",
        "old-2",
        "old-3",
    ]
    assert completion_streak(completed, target, target) == (1, 1)
    finished = today_overview(project_copy, target)
    assert finished["today"]["optional_carryover_available"] is False


def test_matching_finite_carryover_limit_is_still_enforced(project_copy: Path) -> None:
    config_path = project_copy / "config" / "learner.yml"
    content = config_path.read_text(encoding="utf-8")
    content = content.replace("optional_carryover_missions: null", "optional_carryover_missions: 1")
    content = content.replace(
        "optional_carryover_per_workday: null", "optional_carryover_per_workday: 1"
    )
    config_path.write_text(content, encoding="utf-8")

    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-27", 1)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-28", 2)
    write_json(state_path, state)
    target = date(2026, 7, 29)
    today_overview(project_copy, target)
    primary_id = "2026-W31-03-mission"
    _complete_task(project_copy, primary_id, target)
    _mark_publication_complete(project_copy, target, primary_id, "primary")
    today_overview(project_copy, target, continue_carryover=True)
    _complete_task(project_copy, "old-1", target)
    _mark_publication_complete(project_copy, target, "old-1", "carryover")

    overview = today_overview(project_copy, target)
    assert overview["today"]["optional_carryover_limit"] == 1
    assert overview["today"]["optional_carryover_available"] is False
    with pytest.raises(ValueError, match="configured optional carryover limit"):
        today_overview(project_copy, target, continue_carryover=True)


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
        "written_handoff",
        "in_progress",
        2,
        "verified knowledge gap",
        date(2026, 7, 29),
    )
    checkpoint = task["checkpoints"][2]
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
            4 if checkpoint_id == "written_handoff" else None,
            f"verified {checkpoint_id}",
            target,
            artifacts=[artifact] if checkpoint_id == "lab" else (),
            hint_level_used=0,
            independent=True,
            evidence_details={
                "prediction": "The verification artifact should contain the result.",
                "learner_action": "Selected and ran artifact verification.",
                "observed_result": "The artifact contained the expected result.",
                "interpretation": "The artifact supports this verification.",
                "handoff": "Verification passed. The artifact is attached.",
            },
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
