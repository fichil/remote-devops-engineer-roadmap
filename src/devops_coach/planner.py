from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, load_yaml, write_json, write_text


@dataclass(frozen=True)
class DayBudget:
    label_zh: str
    total: int
    english_minutes: int


DAY_BUDGETS = {
    "weekday": DayBudget("工作日", 75, 20),
    "saturday": DayBudget("周六休息日", 0, 0),
    "sunday": DayBudget("周日休息日", 0, 0),
}


MISSION_ARCHETYPES = (
    {
        "codename": "Recon",
        "scenario": "你接手了一个陌生环境，需要先建立事实基线再提出操作建议。",
        "objective": "侦察 {topic_zh}，记录关键事实、未知项和下一步假设。",
        "lab": "围绕 {topic_zh} 执行只读检查，保存命令、输出和一条可验证结论。",
        "english_output": (
            "Write a short handoff with the situation, evidence, and next step "
            "for {topic_en}."
        ),
    },
    {
        "codename": "Build",
        "scenario": "团队需要一个可重复的小型实现，不能依赖旧目录或隐藏状态。",
        "objective": "构建一个关于 {topic_zh} 的最小可重复实验。",
        "lab": "从空 sandbox 完成 {topic_zh} 实验，并加入成功检查和清理方法。",
        "english_output": "Write setup, verification, and cleanup notes for {topic_en}.",
    },
    {
        "codename": "Incident",
        "scenario": "值班同事报告异常，但现有描述不足以直接判断根因。",
        "objective": "诊断一个与 {topic_zh} 有关的安全故障，并用证据排除错误假设。",
        "lab": "制造无害故障，依次记录现象、假设、检查、修复和恢复验证。",
        "english_output": (
            "Write an incident update with impact, cause, fix, and verification "
            "for {topic_en}."
        ),
    },
    {
        "codename": "Handoff",
        "scenario": "你的轮班即将结束，下一位工程师必须能继续操作而不重新猜测。",
        "objective": "把 {topic_zh} 整理为可执行交接，消除隐含步骤。",
        "lab": "整理命令、预期结果、实际结果、风险和回滚，并从头复核一次。",
        "english_output": (
            "Write a concise written handoff for {topic_en}, including one risk "
            "and one next action."
        ),
    },
    {
        "codename": "Boss Review",
        "scenario": "本周进入交付检查：既要独立完成综合任务，也要依据证据调整负载。",
        "objective": "完成 {topic_zh} 综合挑战，并进行本周复盘。",
        "lab": "在新环境完成综合变化题，核对证据、实际分钟、阻塞和可重复性。",
        "english_output": (
            "Write the weekly outcome, strongest evidence, unresolved risk, and "
            "next priority for {topic_en}."
        ),
    },
)


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


def _active_day_index(start: date, target: date) -> int:
    cycle = (target - start).days // 7
    cycle_start = start + timedelta(days=cycle * 7)
    active_days = [
        cycle_start + timedelta(days=offset)
        for offset in range(7)
        if (cycle_start + timedelta(days=offset)).weekday() < 5
    ]
    try:
        return active_days.index(target)
    except ValueError as exc:
        raise ValueError("Weekend dates do not have an active mission") from exc


def _mission_for_day(
    roadmap: dict[str, Any],
    focus: dict[str, Any],
    week: int,
    active_index: int,
) -> dict[str, str]:
    for starter in roadmap.get("starter_weeks", []):
        if starter["week"] == week:
            return dict(starter["missions"][active_index])

    archetype = MISSION_ARCHETYPES[active_index]
    return {
        key: value.format(topic_zh=focus["title_zh"], topic_en=focus["title_en"])
        for key, value in archetype.items()
    }


def _scaled_minutes(base_minutes: int, load_factor: float) -> int:
    if base_minutes == 0:
        return 0
    return max(15, round(base_minutes * load_factor / 5) * 5)


def checkpoint_minutes(total: int) -> tuple[int, int, int]:
    if total <= 60:
        return 10, 35, 15
    if total >= 80:
        return 15, total - 35, 20
    return 15, total - 35, 20


def weekday_streak(
    progress: dict[str, Any],
    start: date,
    target: date,
    minimum_minutes: int,
) -> tuple[int, int]:
    if target < start:
        return 0, 0

    minutes_by_day: defaultdict[date, int] = defaultdict(int)
    for task in progress.get("tasks", {}).values():
        task_date = date.fromisoformat(task["date"])
        if (
            start <= task_date <= target
            and task_date.weekday() < 5
            and task.get("status") in {"partial", "done"}
            and task.get("evidence")
        ):
            minutes_by_day[task_date] += max(0, int(task.get("actual_minutes", 0)))

    attended = {
        task_date
        for task_date, actual_minutes in minutes_by_day.items()
        if actual_minutes >= minimum_minutes
    }

    best = 0
    running = 0
    cursor = start
    while cursor <= target:
        if cursor.weekday() < 5:
            if cursor in attended:
                running += 1
                best = max(best, running)
            else:
                running = 0
        cursor += timedelta(days=1)

    current_end = target
    while current_end.weekday() >= 5:
        current_end -= timedelta(days=1)
    if current_end == target and current_end not in attended:
        current_end -= timedelta(days=1)
        while current_end.weekday() >= 5:
            current_end -= timedelta(days=1)

    current = 0
    cursor = current_end
    while cursor >= start:
        if cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
            continue
        if cursor not in attended:
            break
        current += 1
        cursor -= timedelta(days=1)
    return current, best


def create_today_plan(root: Path, target: date) -> tuple[Path | None, bool]:
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

    kind = day_kind(target)
    schedule = learner["learner"]["schedule"]
    base_minutes = int(schedule[f"{kind}_minutes"])
    if base_minutes == 0:
        return None, False

    start = date.fromisoformat(learner["learner"]["start_date"])
    week = learning_week(start, target)
    phase = _phase_for_week(roadmap, week)
    focus = _focus_for_week(phase, week)
    active_index = _active_day_index(start, target)
    mission = _mission_for_day(roadmap, focus, week, active_index)
    load_factor = float(progress.get("adaptation", {}).get("load_factor", 1.0))
    load_factor = max(0.8, min(1.1, load_factor))
    total = _scaled_minutes(base_minutes, load_factor)
    briefing_minutes, lab_minutes, english_minutes = checkpoint_minutes(total)
    minimum_minutes = int(schedule["minimum_session_minutes"])
    current_streak, best_streak = weekday_streak(progress, start, target, minimum_minutes)
    includes_weekly_review = active_index == 4

    task_id = f"{target_key}-mission"
    task = {
        "id": task_id,
        "date": target_key,
        "section": "mission",
        "title": f"{mission['codename']}：{mission['objective']}",
        "scenario": mission["scenario"],
        "planned_minutes": total,
        "actual_minutes": 0,
        "status": "planned",
        "score": None,
        "evidence": None,
        "carryovers": 0,
        "next_review": None,
        "checkpoints": [
            {
                "name": "briefing",
                "minutes": briefing_minutes,
                "instruction": "阅读事件背景，写出事实、风险和第一条假设。",
            },
            {
                "name": "lab",
                "minutes": lab_minutes,
                "instruction": mission["lab"],
            },
            {
                "name": "written_handoff",
                "minutes": english_minutes,
                "instruction": mission["english_output"],
            },
        ],
        "weekly_review": includes_weekly_review,
    }
    progress["tasks"][task_id] = task

    relative_path = Path("plans") / f"{target:%Y}" / f"{target:%m}" / f"{target_key}.md"
    plan_path = root / relative_path
    lines = [
        "---",
        f"date: {target_key}",
        f"week: {week}",
        f"phase: {phase['id']}",
        f"task_id: {task_id}",
        f"planned_minutes: {total}",
        "status: planned",
        "---",
        "",
        f"# {target_key} · Week {week} · {mission['codename']}",
        "",
        f"> {DAY_BUDGETS[kind].label_zh}单一情境任务；当前负载系数 {load_factor:.1f}。",
        "",
        "## 事件背景",
        "",
        mission["scenario"],
        "",
        f"**本周主题：** {focus['title_zh']} / {focus['title_en']}",
        "",
        f"**任务目标：** {mission['objective']}",
        "",
        "## 三个检查点",
        "",
        f"### 1. 现场简报 · {briefing_minutes} 分钟",
        "",
        "阅读事件，写下已知事实、主要风险和第一条可验证假设。",
        "",
        f"### 2. 实战处理 · {lab_minutes} 分钟",
        "",
        mission["lab"],
        "",
        f"### 3. 英文书面交接 · {english_minutes} 分钟",
        "",
        mission["english_output"],
        "",
        "日常英语只检查阅读和写作，不要求口语、发音或录音证据。",
        "",
    ]
    if includes_weekly_review:
        lines.extend(
            [
                "## 周复盘",
                "",
                "这是本学习周第五个工作日。完成变化题后，核对本周证据、实际分钟、",
                "最大阻塞和下一周负载；取消的历史任务不计入完成率。",
                "",
            ]
        )
    lines.extend(
        [
            "## 完成证据",
            "",
            "- 事件简报：学习者自己的事实、风险和假设。",
            "- 实战：命令或代码、关键输出、验证结果，以及一次独立变化题。",
            "- 英文交接：学习者自己的书面原文和实际投入时间。",
            "- 没有证据不能标记为 done；4/5 或 5/5 还需要独立解释或变化题。",
            "",
            "## 连胜与忙碌日模式",
            "",
            f"- 当前工作日连胜：{current_streak} 天；历史最佳：{best_streak} 天。",
            "- 周六、周日完全忽略，不增加也不中断连胜。",
            f"- 忙碌日可在有证据且实际投入至少 {minimum_minutes} 分钟后记录为 partial；",
            "  它计入参与连胜，但不提高评分，也不绕过阶段门禁。",
            "",
            "只有明确说出“完成并发布今日记录”，才允许提交并推送公开学习进度。",
        ]
    )
    write_text(plan_path, "\n".join(lines))
    progress["daily_plans"][target_key] = {
        "path": relative_path.as_posix(),
        "week": week,
        "phase": phase["id"],
        "planned_minutes": total,
        "actual_minutes": 0,
        "task_ids": [task_id],
        "status": "planned",
    }
    progress["current_week"] = week
    progress["current_phase"] = phase["id"]
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(state_path, progress)
    return plan_path, True


def _sync_daily_plan(progress: dict[str, Any], target_key: str) -> None:
    daily = progress.get("daily_plans", {}).get(target_key)
    if not daily:
        return
    tasks = [
        progress["tasks"][task_id]
        for task_id in daily.get("task_ids", [])
        if task_id in progress["tasks"]
        and progress["tasks"][task_id].get("status") != "cancelled"
    ]
    daily["actual_minutes"] = sum(max(0, int(task.get("actual_minutes", 0))) for task in tasks)
    if tasks and all(task.get("status") == "done" for task in tasks):
        daily["status"] = "done"
    elif any(
        task.get("status") in {"done", "partial", "blocked"}
        or task.get("actual_minutes", 0)
        or task.get("evidence")
        for task in tasks
    ):
        daily["status"] = "partial"
    elif tasks:
        daily["status"] = "planned"
    else:
        daily["status"] = "cancelled"


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
    if minutes < 0:
        raise ValueError("Actual minutes cannot be negative")
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
    _sync_daily_plan(progress, task["date"])
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(state_path, progress)
    return task
