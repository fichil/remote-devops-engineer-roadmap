from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from devops_coach.migration import (
    COGNITIVE_WORKFLOW_VERSION,
    migrate_to_schema_2,
    migrate_to_training_workflow,
    retire_policy_backlog,
)
from devops_coach.planner import ensure_week_plan, refresh_week_plan, today_overview
from devops_coach.storage import load_json, load_yaml, write_json, write_text
from devops_coach.validation import validate_project


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _has_time_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.endswith("_minutes") or key in {"minutes", "load_factor"} or _has_time_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_has_time_key(child) for child in value)
    return False


def _prepare_cognitive_migration_source(root: Path) -> None:
    ensure_week_plan(root, "2026-W35")
    ensure_week_plan(root, "2026-W36")
    state_path = root / "state" / "progress.json"
    state = load_json(state_path)
    state.pop("workflow_version", None)
    legacy_titles = {
        "briefing": "事件简报",
        "lab": "实战处理",
        "written_handoff": "英文书面交接",
    }
    legacy_instructions = {
        "briefing": "写出已知事实、风险、缺失信息和假设。",
        "lab": "复制并运行给出的命令。",
        "written_handoff": "Complete the English handoff template.",
    }
    for task_id, task in state["tasks"].items():
        if not task_id.startswith(("2026-W35-", "2026-W36-")):
            continue
        for field in (
            "workflow_version",
            "weekly_project_id",
            "learning_goal",
            "success_criteria",
        ):
            task.pop(field, None)
        task["title"] = f"Legacy {task_id}"
        task["scenario"] = "Legacy four-question scenario"
        for checkpoint in task["checkpoints"]:
            checkpoint["title"] = legacy_titles[checkpoint["id"]]
            checkpoint["instruction"] = legacy_instructions[checkpoint["id"]]
            for field in (
                "assessment",
                "success_criteria",
                "coach_action",
                "learner_action",
                "hint_policy",
                "hint_level_used",
                "independent",
                "evidence_details",
            ):
                checkpoint.pop(field, None)

    completed = state["tasks"]["2026-W35-01-mission"]
    completed["status"] = "done"
    completed["score"] = 3
    completed["evidence"] = "verified completed mission"
    completed["completed_on"] = "2026-08-24"
    for checkpoint in completed["checkpoints"]:
        checkpoint.update(
            {
                "status": "done",
                "score": 3,
                "evidence": f"verified {checkpoint['id']}",
            }
        )
    state["completion_log"] = [
        {
            "date": "2026-08-24",
            "task_id": completed["id"],
            "kind": "primary",
            "evidence": "verified completed mission",
            "artifacts": [],
        }
    ]

    historical_briefings = {
        "2026-W35-02-mission",
        "2026-W35-04-mission",
        "2026-W36-01-mission",
    }
    concept_resets = {"2026-W35-03-mission", "2026-W35-05-mission"}
    for task_id in historical_briefings | concept_resets:
        task = state["tasks"][task_id]
        task["status"] = "in_progress"
        briefing = task["checkpoints"][0]
        if task_id in historical_briefings:
            briefing.update(
                {
                    "status": "done",
                    "score": 4,
                    "evidence": f"verified historical briefing for {task_id}",
                }
            )
        else:
            briefing.update(
                {"status": "in_progress", "score": None, "evidence": None}
            )
    write_json(state_path, state)
    for week_value in ("2026-W35", "2026-W36"):
        write_text(root / "plans" / "weeks" / f"{week_value}.md", "legacy weekly plan")


def test_migration_dry_run_writes_nothing(migration_project: Path) -> None:
    before = _snapshot(migration_project)

    summary = migrate_to_schema_2(migration_project, dry_run=True)

    assert summary["dry_run"] is True
    assert summary["to_schema"] == 2
    assert summary["active_queue"][:3] == [
        "2026-08-08-project",
        "2026-08-08-review",
        "2026-08-21-mission",
    ]
    assert _snapshot(migration_project) == before
    assert not (migration_project / "state" / "archive").exists()


def test_formal_migration_archives_exact_bytes_and_preserves_old_plans(
    migration_project: Path,
) -> None:
    state_path = migration_project / "state" / "progress.json"
    old_plan = migration_project / "plans" / "2026" / "08" / "2026-08-08.md"
    original_state = state_path.read_bytes()
    original_plan = old_plan.read_bytes()

    summary = migrate_to_schema_2(migration_project)
    state = load_json(state_path)
    learner = load_yaml(migration_project / "config" / "learner.yml")

    assert summary["changed"] is True
    assert (
        migration_project / "state" / "archive" / "progress-v1.json"
    ).read_bytes() == original_state
    assert old_plan.read_bytes() == original_plan
    assert state["schema_version"] == 2
    assert learner["schema_version"] == 2
    assert "daily_plans" not in state
    assert not _has_time_key(state)
    assert not _has_time_key(learner)
    assert state["completion_log"] == [
        {
            "date": "2026-08-03",
            "task_id": "2026-08-03-work",
            "evidence": "Legacy day derived from completed evidence tasks: 2026-08-03-work",
        }
    ]


def test_migration_uses_locked_queue_and_is_idempotent(migration_project: Path) -> None:
    migrate_to_schema_2(migration_project)
    state_path = migration_project / "state" / "progress.json"
    state = load_json(state_path)
    active = [
        task["id"]
        for task in sorted(state["tasks"].values(), key=lambda item: item["queue_order"])
        if task["status"] in {"queued", "in_progress", "blocked"}
    ]

    assert active == [
        "2026-08-08-project",
        "2026-08-08-review",
        "2026-08-21-mission",
    ]
    assert state["tasks"]["2026-08-08-project"]["status"] == "in_progress"
    assert state["tasks"]["2026-08-08-review"]["status"] == "queued"
    mission = state["tasks"]["2026-08-21-mission"]
    assert mission["status"] == "in_progress"
    assert [item["status"] for item in mission["checkpoints"]] == [
        "done",
        "in_progress",
        "queued",
    ]
    assert mission["checkpoints"][0]["score"] == 4

    before = _snapshot(migration_project)
    summary = migrate_to_schema_2(migration_project)
    assert summary["changed"] is False
    assert _snapshot(migration_project) == before


def test_policy_backlog_retirement_is_auditable_and_idempotent(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W34")
    ensure_week_plan(project_copy, "2026-W35")
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    for queue_order, task_id in enumerate(
        ("2026-08-08-project", "2026-08-08-review", "2026-08-21-mission"),
        start=1,
    ):
        state["tasks"][task_id] = {
            "id": task_id,
            "created_on": task_id[:10],
            "scheduled_for": task_id[:10],
            "curriculum_week": 2,
            "phase": "foundations",
            "section": "legacy",
            "title": f"Legacy {task_id}",
            "status": "in_progress" if task_id != "2026-08-08-review" else "queued",
            "score": 4 if task_id == "2026-08-21-mission" else None,
            "evidence": "verified briefing" if task_id == "2026-08-21-mission" else None,
            "completed_on": None,
            "next_review": None,
            "queue_order": queue_order,
            "source": "legacy-v1",
            "checkpoints": [
                {
                    "id": "work",
                    "title": "Legacy work",
                    "instruction": "Complete legacy work.",
                    "status": "in_progress",
                    "score": 4 if task_id == "2026-08-21-mission" else None,
                    "evidence": (
                        "verified briefing" if task_id == "2026-08-21-mission" else None
                    ),
                    "next_review": None,
                }
            ],
        }
    write_json(state_path, state)
    original = state_path.read_bytes()

    summary = retire_policy_backlog(project_copy)
    retired = load_json(state_path)
    archive = (
        project_copy
        / "state"
        / "archive"
        / "progress-pre-queue-policy-2026-08-24.json"
    )

    assert summary["changed"] is True
    assert archive.read_bytes() == original
    assert all(
        retired["tasks"][task_id]["status"] == "cancelled"
        for task_id in summary["retired_ids"]
    )
    assert retired["tasks"]["2026-08-21-mission"]["score"] == 4
    assert retired["tasks"]["2026-08-21-mission"]["evidence"] == "verified briefing"
    assert retired["weekly_plans"]["2026-W35"]["execution_slots"] == retired[
        "weekly_plans"
    ]["2026-W35"]["new_task_ids"]

    before_repeat = _snapshot(project_copy)
    repeated = retire_policy_backlog(project_copy)
    assert repeated["changed"] is False
    assert _snapshot(project_copy) == before_repeat


def test_training_migration_dry_run_writes_nothing(project_copy: Path) -> None:
    _prepare_cognitive_migration_source(project_copy)
    before = _snapshot(project_copy)

    summary = migrate_to_training_workflow(project_copy, dry_run=True)

    assert summary["changed"] is False
    assert summary["would_change"] is True
    assert summary["dry_run"] is True
    assert len(summary["task_ids"]) == 9
    assert _snapshot(project_copy) == before
    assert not (
        project_copy
        / "state"
        / "archive"
        / "progress-pre-cognitive-apprenticeship-v1.json"
    ).exists()


def test_training_migration_preserves_history_and_converts_active_matrix(
    project_copy: Path,
) -> None:
    _prepare_cognitive_migration_source(project_copy)
    state_path = project_copy / "state" / "progress.json"
    before = load_json(state_path)
    original_bytes = state_path.read_bytes()
    completed_before = deepcopy(before["tasks"]["2026-W35-01-mission"])
    completion_log_before = deepcopy(before["completion_log"])

    summary = migrate_to_training_workflow(project_copy)
    migrated = load_json(state_path)

    assert summary["changed"] is True
    assert summary["legacy_checkpoints_preserved"] == 3
    assert summary["checkpoints_converted"] == 24
    assert (
        project_copy
        / "state"
        / "archive"
        / "progress-pre-cognitive-apprenticeship-v1.json"
    ).read_bytes() == original_bytes
    assert migrated["tasks"]["2026-W35-01-mission"] == completed_before
    assert migrated["completion_log"] == completion_log_before
    assert migrated["workflow_version"] == COGNITIVE_WORKFLOW_VERSION
    assert summary["weekly_plans_synced"] == ["2026-W35", "2026-W36"]
    for week_value in summary["weekly_plans_synced"]:
        weekly_plan = (
            project_copy / "plans" / "weeks" / f"{week_value}.md"
        ).read_text(encoding="utf-8")
        assert "legacy weekly plan" not in weekly_plan
        assert "概念与预测" in weekly_plan

    historical_briefings = {
        "2026-W35-02-mission",
        "2026-W35-04-mission",
        "2026-W36-01-mission",
    }
    for task_id in historical_briefings:
        old = before["tasks"][task_id]["checkpoints"][0]
        new = migrated["tasks"][task_id]["checkpoints"][0]
        assert migrated["tasks"][task_id]["score"] is None
        assert new["status"] == old["status"] == "done"
        assert new["score"] == old["score"] == 4
        assert new["evidence"] == old["evidence"]
        assert new["title"] == old["title"]
        assert new["instruction"] == old["instruction"]
        assert new["assessment"] == "legacy"

    for task_id in ("2026-W35-03-mission", "2026-W35-05-mission"):
        briefing = migrated["tasks"][task_id]["checkpoints"][0]
        assert briefing["title"] == "概念与预测"
        assert briefing["assessment"] == "formative"
        assert briefing["score"] is None
        assert briefing["evidence"] is None

    for task_id in summary["task_ids"]:
        task = migrated["tasks"][task_id]
        assert task["workflow_version"] == COGNITIVE_WORKFLOW_VERSION
        assert task["weekly_project_id"]
        assert task["learning_goal"]
        assert task["success_criteria"]
        checkpoints = {item["id"]: item for item in task["checkpoints"]}
        if checkpoints["lab"]["status"] != "done":
            assert checkpoints["lab"]["title"] == "引导练习"
            assert checkpoints["lab"]["assessment"] == "formative"
        if checkpoints["written_handoff"]["status"] != "done":
            assert checkpoints["written_handoff"]["title"] == "独立迁移与交付"
            assert checkpoints["written_handoff"]["assessment"] == "summative"

    w36_queued = [f"2026-W36-0{slot}-mission" for slot in range(2, 6)]
    assert all(
        migrated["tasks"][task_id]["title"] != before["tasks"][task_id]["title"]
        for task_id in w36_queued
    )
    w36_first_lab = migrated["tasks"]["2026-W36-01-mission"]["checkpoints"][1][
        "instruction"
    ]
    assert "概念桥接" in w36_first_lab
    assert "本地仓库" in w36_first_lab
    assert w36_first_lab.count("？") == 1
    assert "画出对象关系" in w36_first_lab
    assert "复制命令" in w36_first_lab
    assert validate_project(project_copy) == []


def test_w36_01_reopens_with_concept_bridge_and_one_judgment(
    project_copy: Path,
) -> None:
    _prepare_cognitive_migration_source(project_copy)
    migrate_to_training_workflow(project_copy)

    overview = today_overview(project_copy, date(2026, 8, 31))

    checkpoint = overview["today"]["next_checkpoint"]
    assert overview["today"]["active_task"]["id"] == "2026-W36-01-mission"
    assert checkpoint["id"] == "lab"
    assert checkpoint["assessment"] == "formative"
    assert "先讲清周项目所需的对象关系" in checkpoint["coach_action"]
    assert "先用自己的话回答一个判断题" in checkpoint["learner_action"]
    assert checkpoint["instruction"].count("？") == 1
    assert "gh " not in checkpoint["instruction"]


def test_training_migration_is_idempotent_with_zero_writes(project_copy: Path) -> None:
    _prepare_cognitive_migration_source(project_copy)
    migrate_to_training_workflow(project_copy)
    before_repeat = _snapshot(project_copy)

    summary = migrate_to_training_workflow(project_copy)

    assert summary["changed"] is False
    assert summary["would_change"] is False
    assert _snapshot(project_copy) == before_repeat


def test_training_migration_repairs_plan_after_interrupted_sync(
    project_copy: Path,
) -> None:
    _prepare_cognitive_migration_source(project_copy)
    migrate_to_training_workflow(project_copy)
    state_path = project_copy / "state" / "progress.json"
    archive_path = (
        project_copy
        / "state"
        / "archive"
        / "progress-pre-cognitive-apprenticeship-v1.json"
    )
    state_before = state_path.read_bytes()
    archive_before = archive_path.read_bytes()
    write_text(project_copy / "plans" / "weeks" / "2026-W36.md", "stale weekly plan")

    repaired = migrate_to_training_workflow(project_copy)

    assert repaired["changed"] is True
    assert repaired["task_ids"] == []
    assert repaired["weekly_plans_synced"] == ["2026-W36"]
    assert state_path.read_bytes() == state_before
    assert archive_path.read_bytes() == archive_before
    assert "stale weekly plan" not in (
        project_copy / "plans" / "weeks" / "2026-W36.md"
    ).read_text(encoding="utf-8")

    before_repeat = _snapshot(project_copy)
    repeated = migrate_to_training_workflow(project_copy)
    assert repeated["changed"] is False
    assert _snapshot(project_copy) == before_repeat


def test_training_migration_does_not_reclassify_later_formative_evidence(
    project_copy: Path,
) -> None:
    _prepare_cognitive_migration_source(project_copy)
    migrate_to_training_workflow(project_copy)
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    checkpoint = state["tasks"]["2026-W35-03-mission"]["checkpoints"][0]
    checkpoint.update(
        {
            "status": "done",
            "score": None,
            "evidence": "learner prediction and explanation",
            "hint_level_used": 1,
            "evidence_details": None,
        }
    )
    write_json(state_path, state)
    refresh_week_plan(project_copy, "2026-W35")
    before_repeat = _snapshot(project_copy)

    summary = migrate_to_training_workflow(project_copy)

    assert summary["changed"] is False
    assert _snapshot(project_copy) == before_repeat
    preserved = load_json(state_path)["tasks"]["2026-W35-03-mission"]["checkpoints"][0]
    assert preserved["assessment"] == "formative"
    assert preserved["hint_level_used"] == 1
