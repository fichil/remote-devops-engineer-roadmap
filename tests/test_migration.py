from __future__ import annotations

from pathlib import Path
from typing import Any

from devops_coach.migration import migrate_to_schema_2, retire_policy_backlog
from devops_coach.planner import ensure_week_plan
from devops_coach.storage import load_json, load_yaml, write_json


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
