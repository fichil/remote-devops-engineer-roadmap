from __future__ import annotations

from datetime import date
from pathlib import Path

from devops_coach.planner import create_today_plan, record_task
from devops_coach.review import review_week
from devops_coach.storage import load_json


def _complete(project: Path, target: date, count: int, blocked: bool = False) -> list[str]:
    create_today_plan(project, target)
    state = load_json(project / "state" / "progress.json")
    task_ids = state["daily_plans"][target.isoformat()]["task_ids"]
    for task_id in task_ids[:count]:
        record_task(project, task_id, "done", 4, 20, f"evidence/{task_id}.md", target)
    if blocked and count < len(task_ids):
        record_task(project, task_ids[count], "blocked", 2, 10, "blocked by lab", target)
    return task_ids


def test_four_week_adaptation_scenarios(project_copy: Path) -> None:
    low_ids = _complete(project_copy, date(2026, 7, 29), 0)
    _, low = review_week(project_copy, "2026-W31")
    assert low["load_factor"] == 0.8

    _complete(project_copy, date(2026, 8, 5), 3)
    _, normal = review_week(project_copy, "2026-W32")
    assert normal["load_factor"] == 1.0

    high_ids = _complete(project_copy, date(2026, 8, 12), 4)
    _, high = review_week(project_copy, "2026-W33")
    assert high["load_factor"] == 1.1
    assert high["done_count"] == len(high_ids)

    _complete(project_copy, date(2026, 8, 19), 3, blocked=True)
    _, blocked = review_week(project_copy, "2026-W34")
    assert blocked["load_factor"] == 1.0
    assert blocked["blockers"]

    review_week(project_copy, "2026-W31")
    state = load_json(project_copy / "state" / "progress.json")
    assert state["tasks"][low_ids[0]]["adaptation_action"] == "split_and_reteach"
