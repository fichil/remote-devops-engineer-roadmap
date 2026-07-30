from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from devops_coach.planner import create_today_plan, record_task
from devops_coach.storage import load_json


@pytest.mark.parametrize(
    ("target", "expected_minutes"),
    [
        (date(2026, 7, 29), 75),
        (date(2026, 8, 1), 180),
        (date(2026, 8, 2), 120),
    ],
)
def test_day_budgets(project_copy: Path, target: date, expected_minutes: int) -> None:
    path, created = create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")
    assert created is True
    assert path.exists()
    assert state["daily_plans"][target.isoformat()]["planned_minutes"] == expected_minutes


def test_plan_is_idempotent(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    initial_state = load_json(project_copy / "state" / "progress.json")
    expected_plan_count = len(initial_state["daily_plans"]) + (
        target.isoformat() not in initial_state["daily_plans"]
    )
    first_path, first_created = create_today_plan(project_copy, target)
    first_content = first_path.read_text(encoding="utf-8")
    second_path, second_created = create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")
    assert first_created is True
    assert second_created is False
    assert first_path == second_path
    assert second_path.read_text(encoding="utf-8") == first_content
    assert len(state["daily_plans"]) == expected_plan_count


def test_weekday_english_is_scheduled_after_work(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    path, _ = create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")
    english = state["tasks"]["2026-07-29-english"]

    assert english["spoken_not_before"] == "18:00"
    assert english["spoken_manual_start"] is True
    assert state["daily_plans"][target.isoformat()]["task_ids"][0].endswith("-concept")
    assert "- 口语部分：18:00 后手动开启" in path.read_text(encoding="utf-8")
    assert "可做英语阅读和写作" in path.read_text(encoding="utf-8")


def test_record_requires_evidence_and_schedules_review(project_copy: Path) -> None:
    create_today_plan(project_copy, date(2026, 7, 29))
    with pytest.raises(ValueError, match="require evidence"):
        record_task(
            project_copy,
            "2026-07-29-practice",
            "done",
            4,
            25,
            "",
            date(2026, 7, 29),
        )
    weak = record_task(
        project_copy,
        "2026-07-29-practice",
        "partial",
        2,
        25,
        "evidence/week-01/practice.md",
        date(2026, 7, 29),
    )
    assert weak["next_review"] == "2026-07-31"
    medium = record_task(
        project_copy,
        "2026-07-29-practice",
        "partial",
        3,
        25,
        "evidence/week-01/practice.md",
        date(2026, 7, 29),
    )
    assert medium["next_review"] == "2026-08-05"
