from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from devops_coach.planner import create_today_plan, record_task
from devops_coach.review import review_week
from devops_coach.storage import load_json, write_json


def _prepare_workweek(
    project: Path,
    monday: date,
    done_count: int,
    blocked: bool = False,
) -> list[str]:
    task_ids: list[str] = []
    for offset in range(5):
        target = monday + timedelta(days=offset)
        create_today_plan(project, target)
        task_id = f"{target.isoformat()}-mission"
        task_ids.append(task_id)
        if offset < done_count:
            record_task(project, task_id, "done", 4, 75, f"evidence/{task_id}.md", target)
        elif blocked and offset == done_count:
            record_task(project, task_id, "blocked", 2, 10, "blocked by lab", target)
    return task_ids


def test_weekly_adaptation_uses_five_missions(project_copy: Path) -> None:
    low_ids = _prepare_workweek(project_copy, date(2026, 8, 3), 0)
    _, low = review_week(project_copy, "2026-W32")
    assert low["load_factor"] == 0.8
    assert low["task_count"] == 5

    _prepare_workweek(project_copy, date(2026, 8, 10), 4)
    _, normal = review_week(project_copy, "2026-W33")
    assert normal["load_factor"] == 1.0

    high_ids = _prepare_workweek(project_copy, date(2026, 8, 17), 5)
    _, high = review_week(project_copy, "2026-W34")
    assert high["load_factor"] == 1.1
    assert high["done_count"] == len(high_ids)

    _prepare_workweek(project_copy, date(2026, 8, 24), 4, blocked=True)
    _, blocked = review_week(project_copy, "2026-W35")
    assert blocked["load_factor"] == 1.0
    assert blocked["blockers"]

    review_week(project_copy, "2026-W32")
    state = load_json(project_copy / "state" / "progress.json")
    assert state["tasks"][low_ids[0]]["adaptation_action"] == "split_and_reteach"


def test_cancelled_tasks_do_not_affect_review_or_carryover(project_copy: Path) -> None:
    monday = date(2026, 8, 3)
    task_ids = _prepare_workweek(project_copy, monday, 4)
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    cancelled_id = "2026-08-03-legacy-english"
    state["tasks"][cancelled_id] = {
        "id": cancelled_id,
        "date": "2026-08-03",
        "section": "english",
        "title": "Legacy task",
        "planned_minutes": 20,
        "actual_minutes": 0,
        "status": "cancelled",
        "score": None,
        "evidence": None,
        "carryovers": 0,
        "next_review": None,
    }
    state["daily_plans"]["2026-08-03"]["task_ids"].append(cancelled_id)
    write_json(state_path, state)

    _, summary = review_week(project_copy, "2026-W32")
    state = load_json(state_path)

    assert summary["task_count"] == len(task_ids)
    assert summary["completion_rate"] == 0.8
    assert cancelled_id not in {
        item["task"] for item in summary["carryover_actions"]
    }
    assert "adaptation_action" not in state["tasks"][cancelled_id]
