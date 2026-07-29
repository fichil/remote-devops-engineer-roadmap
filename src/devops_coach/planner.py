from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, load_yaml, write_json, write_text


@dataclass(frozen=True)
class DayBudget:
    label_zh: str
    total: int
    sections: tuple[tuple[str, int], ...]


DAY_BUDGETS = {
    "weekday": DayBudget(
        "工作日",
        75,
        (("english", 20), ("concept", 20), ("practice", 25), ("review", 10)),
    ),
    "saturday": DayBudget(
        "周六",
        180,
        (("english", 30), ("project", 135), ("review", 15)),
    ),
    "sunday": DayBudget(
        "周日",
        120,
        (("english", 30), ("retrieval", 45), ("weekly_review", 30), ("planning", 15)),
    ),
}


def day_kind(target: date) -> str:
    if target.weekday() == 5:
        return "saturday"
    if target.weekday() == 6:
        return "sunday"
    return "weekday"


def learning_week(start: date, target: date) -> int:
    delta = (target - start).days
    if delta < 0:
        raise ValueError("Target date is before the learner start date")
    return min(delta // 7 + 1, 78)


def _phase_for_week(roadmap: dict[str, Any], week: int) -> dict[str, Any]:
    for phase in roadmap["phases"]:
        if phase["week_start"] <= week <= phase["week_end"]:
            return phase
    raise ValueError(f"No phase covers week {week}")


def _focus_for_week(phase: dict[str, Any], week: int) -> dict[str, Any]:
    return next(item for item in phase["weekly_focus"] if item["week"] == week)


def _starter_day(roadmap: dict[str, Any], week: int, day_offset: int) -> dict[str, Any] | None:
    for starter in roadmap.get("starter_weeks", []):
        if starter["week"] == week:
            return starter["days"][day_offset]
    return None


def _task_copy(
    section: str,
    minutes: int,
    starter: dict[str, Any] | None,
    focus: dict[str, Any],
) -> str:
    if starter and section in starter:
        return starter[section]
    templates = {
        "english": f"用英语学习并口头复述：{focus['title_en']}。保留 3 个关键词和 3 句话。",
        "concept": f"阅读权威资料，画出概念图：{focus['title_zh']}。",
        "practice": f"完成一个可重复的小实验：{focus['title_zh']}，保存命令和结果。",
        "project": (
            f"把本周主题加入阶段作品：{focus['title_zh']}，补充测试和 README；"
            "其中至少 15 分钟用于英文文档。"
        ),
        "retrieval": f"不看笔记解释并复现本周主题：{focus['title_zh']}。",
        "weekly_review": "运行周复盘，核对完成率、掌握度、阻塞项和真实投入。",
        "planning": "根据复盘结果确认下一周负载，只安排可完成的任务。",
        "review": "记录今天学会了什么、证据在哪里、仍然卡在哪里。",
    }
    return templates[section]


def create_today_plan(root: Path, target: date) -> tuple[Path, bool]:
    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    state_path = root / "state" / "progress.json"
    progress = load_json(state_path)

    target_key = target.isoformat()
    existing = progress["daily_plans"].get(target_key)
    if existing:
        existing_path = root / existing["path"]
        if existing_path.exists():
            return existing_path, False

    start = date.fromisoformat(learner["learner"]["start_date"])
    week = learning_week(start, target)
    phase = _phase_for_week(roadmap, week)
    focus = _focus_for_week(phase, week)
    offset = (target - start).days % 7
    starter = _starter_day(roadmap, week, offset)
    kind = day_kind(target)
    budget = DAY_BUDGETS[kind]
    load_factor = float(progress.get("adaptation", {}).get("load_factor", 1.0))
    load_factor = max(0.8, min(1.1, load_factor))

    tasks: list[dict[str, Any]] = []
    for section, base_minutes in budget.sections:
        minutes = max(5, round(base_minutes * load_factor / 5) * 5)
        task_id = f"{target_key}-{section}"
        task = {
            "id": task_id,
            "date": target_key,
            "section": section,
            "title": _task_copy(section, minutes, starter, focus),
            "planned_minutes": minutes,
            "actual_minutes": 0,
            "status": "planned",
            "score": None,
            "evidence": None,
            "carryovers": 0,
            "next_review": None,
        }
        tasks.append(task)
        progress["tasks"][task_id] = task

    total = sum(task["planned_minutes"] for task in tasks)
    relative_path = Path("plans") / f"{target:%Y}" / f"{target:%m}" / f"{target_key}.md"
    plan_path = root / relative_path
    lines = [
        "---",
        f"date: {target_key}",
        f"week: {week}",
        f"phase: {phase['id']}",
        f"planned_minutes: {total}",
        "status: planned",
        "---",
        "",
        f"# {target_key} · Week {week} · {focus['title_zh']}",
        "",
        f"> {budget.label_zh}计划，调整系数 {load_factor:.1f}。教练一次只带你完成一项。",
        "",
        "## 今日任务",
        "",
    ]
    for index, task in enumerate(tasks, start=1):
        lines.extend(
            [
                f"### {index}. `{task['id']}` · {task['planned_minutes']} 分钟",
                "",
                task["title"],
                "",
                "- 状态：planned",
                "- 证据：待提交",
                "- 自评分：待测验",
                "",
            ]
        )
    lines.extend(
        [
            "## 完成标准",
            "",
            "- 提供命令输出、代码、截图文字说明或口头复述之一。",
            "- 教练通过追问或小测给出 0–5 掌握度。",
            "- 没有证据的任务不能标记为 done。",
            "- 只有说出“完成并发布今日记录”，才允许提交并推送公开进度。",
        ]
    )
    write_text(plan_path, "\n".join(lines))
    progress["daily_plans"][target_key] = {
        "path": relative_path.as_posix(),
        "week": week,
        "phase": phase["id"],
        "planned_minutes": total,
        "task_ids": [task["id"] for task in tasks],
        "status": "planned",
    }
    progress["current_week"] = week
    progress["current_phase"] = phase["id"]
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(state_path, progress)
    return plan_path, True


def record_task(
    root: Path,
    task_id: str,
    status: str,
    score: int,
    minutes: int,
    evidence: str,
    recorded_on: date | None = None,
) -> dict[str, Any]:
    state_path = root / "state" / "progress.json"
    progress = load_json(state_path)
    if task_id not in progress["tasks"]:
        raise KeyError(f"Unknown task: {task_id}")
    if status == "done" and not evidence.strip():
        raise ValueError("Done tasks require evidence")
    task = progress["tasks"][task_id]
    task.update(
        {
            "status": status,
            "score": score,
            "actual_minutes": minutes,
            "evidence": evidence.strip() or None,
        }
    )
    base = recorded_on or date.today()
    if score <= 2:
        task["next_review"] = (base + timedelta(days=2)).isoformat()
    elif score == 3:
        task["next_review"] = (base + timedelta(days=7)).isoformat()
    else:
        task["next_review"] = None
    if status == "blocked" and task_id not in progress["blockers"]:
        progress["blockers"].append(task_id)
    elif status != "blocked" and task_id in progress["blockers"]:
        progress["blockers"].remove(task_id)
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(state_path, progress)
    return task
