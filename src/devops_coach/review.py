from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from devops_coach.planner import (
    COGNITIVE_WORKFLOW,
    ensure_week_plan,
    parse_iso_week,
    refresh_week_plan,
)
from devops_coach.storage import load_json, write_json


def _task_score(task: dict[str, Any]) -> int | None:
    if task.get("workflow_version") != COGNITIVE_WORKFLOW:
        return task.get("score")
    scores = [
        checkpoint["score"]
        for checkpoint in task.get("checkpoints", [])
        if checkpoint.get("assessment") == "summative"
        and checkpoint.get("score") is not None
    ]
    return round(sum(scores) / len(scores)) if scores else None


def _priority(tasks: list[dict[str, Any]]) -> str:
    weak = next(
        (
            task
            for task in tasks
            if task["status"] == "blocked"
            or (_task_score(task) is not None and _task_score(task) <= 2)
            or task["status"] != "done"
        ),
        None,
    )
    return weak["title"] if weak else "保持本周主题并增加独立变化"


def _english_priority(tasks: list[dict[str, Any]]) -> str:
    for task in tasks:
        for checkpoint in task.get("checkpoints", []):
            if checkpoint["id"] == "written_handoff" and checkpoint["status"] != "done":
                return checkpoint["instruction"]
    return "独立写出更精确的证据、风险和下一步交接"


def review_week(root: Path, week_value: str) -> tuple[Path, dict[str, Any]]:
    parse_iso_week(week_value)
    ensure_week_plan(root, week_value)
    progress_path = root / "state" / "progress.json"
    progress = load_json(progress_path)
    plan = progress["weekly_plans"][week_value]
    tasks = [
        progress["tasks"][task_id]
        for task_id in plan["execution_slots"]
        if task_id in progress["tasks"] and progress["tasks"][task_id]["status"] != "cancelled"
    ]
    done = [task for task in tasks if task["status"] == "done"]
    scores = [score for task in tasks if (score := _task_score(task)) is not None]
    completion = len(done) / len(tasks) if tasks else 0.0
    mean_score = sum(scores) / len(scores) if scores else 0.0
    blockers = [task["id"] for task in tasks if task["status"] == "blocked"]
    low_scores = [
        task["id"]
        for task in tasks
        if (score := _task_score(task)) is not None and score <= 2
    ]

    if completion < 0.70 or low_scores:
        mode = "reteach"
        reason = "完成率偏低或存在 0–2 分项；下一周优先重教、拆小和变化题。"
    elif completion >= 0.80 and mean_score >= 4 and not blockers:
        mode = "stretch"
        reason = "完成率高、平均掌握度达标且无阻塞；下一周增加独立变化要求。"
    else:
        mode = "standard"
        reason = "证据处于可持续区间；保持核心难度并继续检索薄弱点。"

    actions: list[dict[str, str]] = []
    for task in tasks:
        if task["status"] == "done":
            continue
        action = "拆小重教并加入变化题" if mode == "reteach" else "继续队首任务"
        task["coaching_action"] = action
        actions.append({"task": task["id"], "action": action})

    summary = {
        "week": week_value,
        "task_count": len(tasks),
        "done_count": len(done),
        "completion_rate": round(completion, 4),
        "mean_score": round(mean_score, 2),
        "blockers": blockers,
        "low_score_tasks": low_scores,
        "adaptation_mode": mode,
        "reason": reason,
        "content_actions": actions,
        "technical_priority": _priority(tasks),
        "english_priority": _english_priority(tasks),
        "daily_mission_quota": 1,
    }
    progress["adaptation"] = {
        "mode": mode,
        "reason": reason,
        "source_week": week_value,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    progress["weekly_reviews"][week_value] = summary
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(progress_path, progress)
    path = refresh_week_plan(root, week_value)
    if path is None:
        raise RuntimeError(f"Weekly plan disappeared while reviewing {week_value}")
    return path, summary
