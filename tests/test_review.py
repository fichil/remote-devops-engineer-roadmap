from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from devops_coach.planner import ensure_week_plan, record_checkpoint
from devops_coach.review import review_week
from devops_coach.storage import load_json


def _complete(project: Path, task_id: str, day: date, score: int = 4) -> None:
    state = load_json(project / "state" / "progress.json")
    for checkpoint in state["tasks"][task_id]["checkpoints"]:
        record_checkpoint(
            project,
            task_id,
            checkpoint["id"],
            "done",
            None if checkpoint.get("assessment") == "formative" else score,
            f"verified {checkpoint['id']}",
            day,
            hint_level_used=0,
            independent=True,
            evidence_details={
                "prediction": "The changed condition should pass verification.",
                "learner_action": "Selected and ran verification independently.",
                "observed_result": "The changed condition passed.",
                "interpretation": "The result supports the selected approach.",
                "handoff": "Verification passed. The evidence is ready for review.",
            },
        )


def _complete_cognitive(project: Path, task_id: str, day: date, score: int = 4) -> None:
    record_checkpoint(project, task_id, "briefing", "done", None, "own prediction", day)
    record_checkpoint(project, task_id, "lab", "done", None, "guided practice", day)
    record_checkpoint(
        project,
        task_id,
        "written_handoff",
        "done",
        score,
        "independent variation",
        day,
        hint_level_used=0,
        independent=True,
        evidence_details={
            "prediction": "Expected branch difference.",
            "learner_action": "Selected and ran a read-only comparison.",
            "observed_result": "Observed the expected branch difference.",
            "interpretation": "The result confirms the prediction.",
            "handoff": "The comparison passed. The change is ready for review.",
        },
    )


def test_low_completion_changes_content_to_reteach_not_quantity(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W31")
    task_id = "2026-W31-03-mission"
    record_checkpoint(
        project_copy,
        task_id,
        "briefing",
        "blocked",
        None,
        "environment blocker evidence",
        date(2026, 7, 29),
    )

    path, summary = review_week(project_copy, "2026-W31")
    state = load_json(project_copy / "state" / "progress.json")

    assert path == project_copy / "plans" / "weeks" / "2026-W31.md"
    assert summary["adaptation_mode"] == "reteach"
    assert summary["daily_mission_quota"] == 1
    assert summary["task_count"] == 5
    assert task_id in summary["blockers"]
    assert state["adaptation"]["mode"] == "reteach"
    assert not (project_copy / "reviews" / "2026-W31.md").exists()
    assert "下周内容模式：reteach" in path.read_text(encoding="utf-8")

    ensure_week_plan(project_copy, "2026-W32")
    state = load_json(project_copy / "state" / "progress.json")
    next_ids = state["weekly_plans"]["2026-W32"]["new_task_ids"]
    assert len(next_ids) == 5
    assert all(
        "拆成可验证的小步" in state["tasks"][task_id]["checkpoints"][0]["instruction"]
        for task_id in next_ids
    )


def test_high_completion_adds_independent_variation_with_same_quantity(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W31")
    monday = date(2026, 7, 27)
    for index in range(4):
        _complete(
            project_copy,
            f"2026-W31-{index + 1:02d}-mission",
            monday + timedelta(days=index),
        )

    _, summary = review_week(project_copy, "2026-W31")
    assert summary["completion_rate"] == 0.8
    assert summary["mean_score"] == 4
    assert summary["adaptation_mode"] == "stretch"
    assert summary["daily_mission_quota"] == 1

    ensure_week_plan(project_copy, "2026-W32")
    state = load_json(project_copy / "state" / "progress.json")
    next_ids = state["weekly_plans"]["2026-W32"]["new_task_ids"]
    assert len(next_ids) == 5
    assert all(
        "独立处理一个未给步骤的变化条件" in state["tasks"][task_id]["checkpoints"][1]["instruction"]
        for task_id in next_ids
    )
    assert "load_factor" not in state["adaptation"]


def test_cognitive_review_uses_only_summative_scores(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W35")
    monday = date(2026, 8, 24)
    for index in range(4):
        _complete_cognitive(
            project_copy,
            f"2026-W35-{index + 1:02d}-mission",
            monday + timedelta(days=index),
        )

    _, summary = review_week(project_copy, "2026-W35")
    state = load_json(project_copy / "state" / "progress.json")

    assert summary["completion_rate"] == 0.8
    assert summary["mean_score"] == 4
    assert summary["low_score_tasks"] == []
    assert summary["adaptation_mode"] == "stretch"
    for task_id in state["weekly_plans"]["2026-W35"]["new_task_ids"][:4]:
        task = state["tasks"][task_id]
        assert task["score"] == 4
        assert [item["score"] for item in task["checkpoints"]] == [None, None, 4]
