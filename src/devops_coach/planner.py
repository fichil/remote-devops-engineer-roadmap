from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, load_yaml, write_json, write_text

ACTIVE_STATUSES = {"queued", "in_progress", "blocked"}
STATUS_ZH = {
    "queued": "待开始",
    "in_progress": "进行中",
    "done": "已完成",
    "blocked": "阻塞",
    "cancelled": "已取消",
}

MISSION_ARCHETYPES = (
    {
        "codename": "Recon",
        "scenario": "你接手了一个陌生环境，需要先建立事实基线再提出操作建议。",
        "objective": "侦察 {topic_zh}，记录关键事实、未知项和下一步假设。",
        "lab": "围绕 {topic_zh} 执行只读检查，保存命令、输出和一条可验证结论。",
        "english_output": (
            "Write a short handoff with the situation, evidence, and next step for {topic_en}."
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
            "Write an incident update with impact, cause, fix, and verification for {topic_en}."
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
        "scenario": "本周进入交付检查：既要独立完成综合任务，也要依据证据调整下周内容。",
        "objective": "完成 {topic_zh} 综合挑战，并进行本周复盘。",
        "lab": "在新环境完成综合变化题，核对证据、阻塞和可重复性。",
        "english_output": (
            "Write the weekly outcome, strongest evidence, unresolved risk, and "
            "next priority for {topic_en}."
        ),
    },
)


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def require_schema_v2(progress: dict[str, Any]) -> None:
    if progress.get("schema_version") != 2:
        raise ValueError(
            "Progress schema v2 is required; run `devops-coach migrate --to-schema 2` first."
        )


def day_kind(target: date) -> str:
    if target.weekday() == 5:
        return "saturday"
    if target.weekday() == 6:
        return "sunday"
    return "weekday"


def calendar_learning_week(start: date, target: date) -> int:
    start_monday = start - timedelta(days=start.weekday())
    target_monday = target - timedelta(days=target.weekday())
    if target_monday < start_monday:
        raise ValueError("Target date is before the learner start week")
    return min((target_monday - start_monday).days // 7 + 1, 78)


def learning_week(start: date, target: date) -> int:
    """Backward-compatible name for the calendar-week curriculum index."""
    return calendar_learning_week(start, target)


def parse_iso_week(value: str) -> tuple[int, int]:
    try:
        year_text, week_text = value.split("-W", maxsplit=1)
        year, week = int(year_text), int(week_text)
        date.fromisocalendar(year, week, 1)
        return year, week
    except (ValueError, TypeError) as exc:
        raise ValueError("Week must use YYYY-Www, for example 2026-W34") from exc


def week_bounds(value: str) -> tuple[date, date]:
    year, week = parse_iso_week(value)
    monday = date.fromisocalendar(year, week, 1)
    return monday, monday + timedelta(days=4)


def phase_for_week(roadmap: dict[str, Any], week: int) -> dict[str, Any]:
    for phase in roadmap["phases"]:
        if phase["week_start"] <= week <= phase["week_end"]:
            return phase
    raise ValueError(f"No phase covers week {week}")


def focus_for_week(phase: dict[str, Any], week: int) -> dict[str, Any]:
    return next(item for item in phase["weekly_focus"] if item["week"] == week)


def mission_for_slot(
    roadmap: dict[str, Any], focus: dict[str, Any], week: int, slot: int
) -> dict[str, str]:
    for starter in roadmap.get("starter_weeks", []):
        if starter["week"] == week:
            return dict(starter["missions"][slot])
    archetype = MISSION_ARCHETYPES[slot]
    return {
        key: value.format(topic_zh=focus["title_zh"], topic_en=focus["title_en"])
        for key, value in archetype.items()
    }


def _gate_execution(
    roadmap: dict[str, Any], progress: dict[str, Any], calendar_phase: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    unmet = [
        prerequisite
        for prerequisite in calendar_phase.get("prerequisites", [])
        if progress.get("phase_gates", {}).get(prerequisite, {}).get("status") != "passed"
    ]
    if not unmet:
        return calendar_phase, "normal"
    execution = next(phase for phase in roadmap["phases"] if phase["id"] == unmet[0])
    return execution, "remediation"


def _review_date(score: int, base: date) -> str | None:
    if score <= 2:
        return (base + timedelta(days=2)).isoformat()
    if score == 3:
        return (base + timedelta(days=7)).isoformat()
    return None


def _checkpoint(checkpoint_id: str, title: str, instruction: str) -> dict[str, Any]:
    return {
        "id": checkpoint_id,
        "title": title,
        "instruction": instruction,
        "status": "queued",
        "score": None,
        "evidence": None,
        "artifacts": [],
        "next_review": None,
    }


def _adapt_instruction(instruction: str, mode: str) -> str:
    if mode == "reteach":
        return instruction + " 先重教最弱点，拆成可验证的小步，再完成变化题。"
    if mode == "stretch":
        return instruction + " 完成基础要求后，再独立处理一个未给步骤的变化条件。"
    return instruction


def _new_mission_task(
    task_id: str,
    scheduled_for: date,
    week: int,
    phase: dict[str, Any],
    mission: dict[str, str],
    queue_order: int,
    adaptation_mode: str,
    gate_mode: str,
    weekly_review: bool,
) -> dict[str, Any]:
    if gate_mode == "remediation":
        gate_text = str(phase["gate"])
        mission = {
            "codename": "Gate Reteach" if not weekly_review else "Gate Retest",
            "scenario": "日历主题已经前进，但上一阶段门禁尚未通过，不能启动下一阶段实作。",
            "objective": f"围绕“{gate_text}”补齐证据并重新接受门禁检查。",
            "lab": f"复现上一阶段门禁：{gate_text}；保存成功证据、失败诊断和独立变化结果。",
            "english_output": (
                "Write the gate status, strongest evidence, remaining gap, and next action."
            ),
        }
    checkpoints = [
        _checkpoint(
            "briefing",
            "事件简报",
            _adapt_instruction(
                "写出已知事实、主要风险、缺失信息和第一条可验证假设。",
                adaptation_mode,
            ),
        ),
        _checkpoint(
            "lab",
            "实战处理",
            _adapt_instruction(mission["lab"], adaptation_mode),
        ),
        _checkpoint(
            "written_handoff",
            "英文书面交接",
            _adapt_instruction(mission["english_output"], adaptation_mode),
        ),
    ]
    task = {
        "id": task_id,
        "created_on": scheduled_for.isoformat(),
        "scheduled_for": scheduled_for.isoformat(),
        "curriculum_week": week,
        "phase": str(phase["id"]),
        "section": "mission",
        "title": f"{mission['codename']}：{mission['objective']}",
        "scenario": mission["scenario"],
        "status": "queued",
        "score": None,
        "evidence": None,
        "completed_on": None,
        "next_review": None,
        "queue_order": queue_order,
        "source": "weekly-plan",
        "weekly_review": weekly_review,
        "carryover_activated_on": None,
        "checkpoints": checkpoints,
    }
    if weekly_review and (gate_mode == "remediation" or week == phase["week_end"]):
        task["gate_id"] = str(phase["id"])
    return task


def active_tasks(progress: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            task
            for task in progress.get("tasks", {}).values()
            if task.get("status") in ACTIVE_STATUSES
        ),
        key=lambda task: (
            int(task.get("queue_order", 10**9)),
            str(task.get("created_on", "9999-12-31")),
            str(task.get("id", "")),
        ),
    )


def _scheduled_primary_task(
    progress: dict[str, Any], plan: dict[str, Any], target: date
) -> dict[str, Any] | None:
    candidates = [
        progress["tasks"][task_id]
        for task_id in plan.get("new_task_ids", [])
        if task_id in progress.get("tasks", {})
        and progress["tasks"][task_id].get("scheduled_for") == target.isoformat()
    ]
    if len(candidates) > 1:
        raise ValueError(f"Multiple primary tasks are scheduled for {target.isoformat()}")
    return candidates[0] if candidates else None


def carryover_tasks(progress: dict[str, Any], target: date) -> list[dict[str, Any]]:
    carryovers: list[dict[str, Any]] = []
    for task in active_tasks(progress):
        scheduled_text = task.get("scheduled_for") or task.get("created_on")
        try:
            scheduled = date.fromisoformat(str(scheduled_text))
        except (TypeError, ValueError):
            continue
        if scheduled < target:
            carryovers.append(task)
    return carryovers


def _completion_items(progress: dict[str, Any], target: date) -> list[dict[str, Any]]:
    return [
        item
        for item in progress.get("completion_log", [])
        if item.get("date") == target.isoformat()
    ]


def _start_task(task: dict[str, Any]) -> dict[str, Any] | None:
    if task["status"] == "queued":
        task["status"] = "in_progress"
        first = _first_unfinished(task)
        if first and first["status"] == "queued":
            first["status"] = "in_progress"
    return _first_unfinished(task)


def task_has_complete_evidence(task: dict[str, Any]) -> bool:
    checkpoints = task.get("checkpoints", [])
    return bool(
        task.get("status") == "done"
        and task.get("evidence")
        and checkpoints
        and all(
            checkpoint.get("status") == "done" and checkpoint.get("evidence")
            for checkpoint in checkpoints
        )
    )


def completion_streak(progress: dict[str, Any], start: date, target: date) -> tuple[int, int]:
    attended: set[date] = set()
    for item in progress.get("completion_log", []):
        try:
            completed_date = date.fromisoformat(item["date"])
        except (KeyError, ValueError, TypeError):
            continue
        task = progress.get("tasks", {}).get(item.get("task_id"))
        if (
            start <= completed_date <= target
            and completed_date.weekday() < 5
            and item.get("evidence")
            and task
            and task_has_complete_evidence(task)
        ):
            attended.add(completed_date)

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
    if current_end not in attended:
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


def weekday_streak(
    progress: dict[str, Any], start: date, target: date, *_ignored: Any
) -> tuple[int, int]:
    """Compatibility alias; schema v2 uses completion, never attendance time."""
    return completion_streak(progress, start, target)


def readiness_date(start: date) -> date:
    first_monday = start - timedelta(days=start.weekday())
    return first_monday + timedelta(weeks=77, days=4)


def render_master_plan(learner: dict[str, Any], roadmap: dict[str, Any]) -> str:
    profile = learner["learner"]
    start = date.fromisoformat(profile["start_date"])
    lines = [
        "# DevOps 转行总规划",
        "",
        "## 目标定义",
        "",
        "- 目标岗位：海外远程 DevOps 工程师（正式雇员或长期合同工）。",
        (
            f"- 路线起点：{start.isoformat()}；第 78 周预计能力门槛日："
            f"{readiness_date(start).isoformat()}。"
        ),
        "- 达标含义：具备稳定投递和参加面试的证据门槛，不承诺具体录用日期。",
        "- 总进度同时看规划周次、证据任务、阶段门禁和职业成果，不合成为单一百分比。",
        "",
        "## 执行规则",
        "",
        "- 周一至周五每天定量完成一个完整运维任务；周六、周日完全休息。",
        "- 每个标准任务固定包含事件简报、实战处理、英文书面交接三个检查点。",
        "- 每个工作日先完成当天计划任务；旧任务不得抢占当天主任务。",
        "- 当天主任务完成后默认停止；用户明确要求继续时，最多再处理一个最早遗留任务。",
        "- 完整任务取得全部证据后自动通过 Ready PR、CI 和 squash merge 发布；可选遗留单独发布。",
        "- 日历主题每周前进；跨阶段时，未通过的先修门禁会改派重教或复测任务。",
        "- 日常英语只评价阅读和写作；通用口语与发音由 Duolingo 负责。",
        "- 路线明确安排的技术演示和模拟面试仍是职业门槛证据。",
        "",
        "## 六阶段与门禁",
        "",
        "| 阶段 | 周次 | 核心成果 | 阶段门禁 |",
        "|---|---:|---|---|",
    ]
    for phase in roadmap["phases"]:
        outcomes = "；".join(str(item) for item in phase["outcomes"])
        lines.append(
            f"| {phase['title_zh']} | {phase['week_start']}–{phase['week_end']} | "
            f"{outcomes} | {phase['gate']} |"
        )
    lines.extend(
        [
            "",
            "## 78 周主题",
            "",
            "| 周次 | 阶段 | 主题 |",
            "|---:|---|---|",
        ]
    )
    for phase in roadmap["phases"]:
        for focus in phase["weekly_focus"]:
            lines.append(
                f"| {focus['week']} | {phase['title_zh']} | "
                f"{focus['title_zh']} / {focus['title_en']} |"
            )
    lines.extend(
        [
            "",
            "## 门禁规则",
            "",
            "- 六个阶段门禁都必须有可复核证据且达到 4/5；不得为维持名义日期降低门槛。",
            "- 0–2 分安排优先重教和变化题；3 分安排后续检索；4–5 分仍需成功证据与独立解释或变化。",
            "- 门禁未通过时保留日历周次，但下一阶段任务保持锁定。",
            "",
            "## 英语进阶",
            "",
            "- 第 1–13 周：读懂基础命令和工单，用简单英文写事实、结果与下一步。",
            "- 第 14–26 周：编写脚本 README、故障报告和异步状态更新。",
            "- 第 27–39 周：编写 Issue、PR、发布说明，并保留路线规定的技术演示。",
            "- 第 40–65 周：编写架构、成本、变更、告警、事故时间线和复盘文档。",
            "- 第 66–78 周：完成全英文 README、简历、求职信、书面面试回答、技术演示和模拟面试。",
            "",
            "## 作品集与求职里程碑",
            "",
            "- 作品集目标：6 个，每个阶段至少形成一个可运行、可验证、可解释的成果。",
            "- 开源贡献目标：3 次被接受的有效贡献，公开部分不得包含私人求职信息。",
            "- 模拟面试目标：3 轮，技术演示和路线规定的面试环节保留。",
            "- 求职里程碑：综合项目、英文文档、简历与职业主页、定制投递、最终能力门禁。",
            "",
            "## 遗留优先与内容适应",
            "",
            "- 每周仍生成五个新任务，并把它们固定为当周五个必做执行名额。",
            "- 遗留任务按最早创建顺序排列，只能在当天主任务完成且用户明确要求后处理一项。",
            "- 完成率低或出现 0–2 分项：下一周重教、拆小并加入变化题。",
            "- 完成率高、平均分至少 4 且无阻塞：任务数量不变，增加独立变化要求。",
            "- 周复盘只调整内容，不调整每日任务数量，也不使用历史时间数据。",
        ]
    )
    return "\n".join(lines) + "\n"


def ensure_master_plan(root: Path) -> tuple[Path, bool]:
    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    path = root / "plans" / "master-plan.md"
    expected = render_master_plan(learner, roadmap)
    if path.exists() and path.read_text(encoding="utf-8") == expected:
        return path, False
    write_text(path, expected)
    return path, True


def _week_status(progress: dict[str, Any], task_ids: list[str]) -> dict[str, int]:
    tasks = [progress["tasks"][task_id] for task_id in task_ids if task_id in progress["tasks"]]
    done = sum(task["status"] == "done" for task in tasks)
    in_progress = sum(task["status"] == "in_progress" for task in tasks)
    blocked = sum(task["status"] == "blocked" for task in tasks)
    queued = sum(task["status"] == "queued" for task in tasks)
    return {
        "done": done,
        "in_progress": in_progress,
        "blocked": blocked,
        "queued": queued,
        "remaining": in_progress + blocked + queued,
    }


def render_week_plan(progress: dict[str, Any], week_value: str) -> str:
    plan = progress["weekly_plans"][week_value]
    new_ids = list(plan["new_task_ids"])
    new_set = set(new_ids)
    backlog = [task for task in active_tasks(progress) if task["id"] not in new_set]
    slots = list(plan["execution_slots"])
    status = _week_status(progress, slots)
    lines = [
        f"# {week_value} 周规划",
        "",
        f"> 工作日范围：{plan['monday']} 至 {plan['friday']}；规划第 {plan['week']}/78 周。",
        "",
        "## 本周主题、阶段和门禁",
        "",
        f"- 日历主题：{plan['theme_zh']} / {plan['theme_en']}",
        f"- 日历阶段：{plan['calendar_phase']}",
        f"- 实际执行阶段：{plan['execution_phase']}",
        f"- 门禁模式：{'上一阶段重教或复测' if plan['gate_mode'] == 'remediation' else '正常'}",
        "",
        "## 旧任务队列",
        "",
    ]
    if backlog:
        lines.append(f"- 最早遗留项：`{backlog[0]['id']}` — {backlog[0]['title']}")
        lines.extend(
            f"- `{task['id']}` [{STATUS_ZH[task['status']]}] {task['title']}" for task in backlog
        )
    else:
        lines.append("- 无遗留任务。")
    lines.extend(["", "## 本周五个新任务", ""])
    for index, task_id in enumerate(new_ids, start=1):
        task = progress["tasks"][task_id]
        lines.extend(
            [
                f"### {index}. `{task_id}` [{STATUS_ZH[task['status']]}]",
                "",
                task["title"],
                "",
            ]
        )
        lines.extend(
            f"- {checkpoint['title']} [{STATUS_ZH[checkpoint['status']]}]："
            f"{checkpoint['instruction']}"
            for checkpoint in task["checkpoints"]
        )
        lines.append("")
    lines.extend(
        [
            "## 周一至周五执行名额",
            "",
            "当天计划任务优先；遗留只作为主任务完成后的可选第二项。",
            "",
            "| 工作日 | 队列任务 | 状态 |",
            "|---|---|---|",
        ]
    )
    monday = date.fromisoformat(plan["monday"])
    for index, task_id in enumerate(slots):
        task = progress["tasks"][task_id]
        lines.append(
            f"| {(monday + timedelta(days=index)).isoformat()} | `{task_id}` "
            f"{task['title']} | {STATUS_ZH[task['status']]} |"
        )
    lines.extend(
        [
            "",
            "## 本周完成情况",
            "",
            f"- 已完成：{status['done']}",
            f"- 进行中：{status['in_progress']}",
            f"- 阻塞：{status['blocked']}",
            f"- 待开始：{status['queued']}",
            f"- 剩余：{status['remaining']}",
            "",
            "## 英文输出",
            "",
            "- 每个标准任务都必须完成学习者本人撰写的英文书面交接。",
            "- 本仓库只评价日常英文阅读和写作；通用口语、发音和录音由 Duolingo 负责。",
            "- 路线规定的技术演示和模拟面试仍保留。",
            "",
            "## 周复盘与下周内容调整",
            "",
        ]
    )
    review = progress.get("weekly_reviews", {}).get(week_value)
    if review:
        lines.extend(
            [
                (
                    f"- 执行名额完成：{review['done_count']}/{review['task_count']}"
                    f"（{review['completion_rate']:.0%}）"
                ),
                f"- 平均掌握度：{review['mean_score']:.2f}/5",
                f"- 阻塞项：{', '.join(review['blockers']) if review['blockers'] else '无'}",
                f"- 下周内容模式：{review['adaptation_mode']} — {review['reason']}",
                f"- 技术优先项：{review['technical_priority']}",
                f"- 英文优先项：{review['english_priority']}",
            ]
        )
    else:
        lines.extend(
            [
                "- 周复盘尚未写回。",
                (
                    f"- 当前内容适应模式：{progress['adaptation']['mode']} — "
                    f"{progress['adaptation']['reason']}"
                ),
                "- 复盘只调整任务内容，不改变每天一个任务的定量。",
            ]
        )
    return "\n".join(lines) + "\n"


def ensure_week_plan(root: Path, week_value: str) -> tuple[Path, bool]:
    progress_path = root / "state" / "progress.json"
    progress = load_json(progress_path)
    require_schema_v2(progress)
    existing = progress.get("weekly_plans", {}).get(week_value)
    if existing:
        path = root / existing["path"]
        if not path.exists():
            write_text(path, render_week_plan(progress, week_value))
        return path, False

    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    monday, friday = week_bounds(week_value)
    start = date.fromisoformat(learner["learner"]["start_date"])
    week = calendar_learning_week(start, friday)
    calendar_phase = phase_for_week(roadmap, week)
    focus = focus_for_week(calendar_phase, week)
    execution_phase, gate_mode = _gate_execution(roadmap, progress, calendar_phase)
    adaptation_mode = progress["adaptation"]["mode"]
    next_order = (
        max(
            (int(task.get("queue_order", 0)) for task in progress["tasks"].values()),
            default=0,
        )
        + 1
    )
    new_ids: list[str] = []
    for slot in range(5):
        task_id = f"{week_value}-{slot + 1:02d}-mission"
        if task_id in progress["tasks"]:
            raise ValueError(f"Task already exists without weekly plan metadata: {task_id}")
        mission = mission_for_slot(roadmap, focus, week, slot)
        task = _new_mission_task(
            task_id,
            monday + timedelta(days=slot),
            week,
            execution_phase,
            mission,
            next_order + slot,
            adaptation_mode,
            gate_mode,
            slot == 4,
        )
        progress["tasks"][task_id] = task
        new_ids.append(task_id)

    execution_slots = list(new_ids)
    relative = Path("plans") / "weeks" / f"{week_value}.md"
    progress.setdefault("weekly_plans", {})[week_value] = {
        "path": relative.as_posix(),
        "week": week,
        "calendar_phase": str(calendar_phase["id"]),
        "execution_phase": str(execution_phase["id"]),
        "theme_zh": str(focus["title_zh"]),
        "theme_en": str(focus["title_en"]),
        "monday": monday.isoformat(),
        "friday": friday.isoformat(),
        "new_task_ids": new_ids,
        "execution_slots": execution_slots,
        "gate_mode": gate_mode,
    }
    progress["updated_at"] = now_text()
    write_json(progress_path, progress)
    path = root / relative
    write_text(path, render_week_plan(progress, week_value))
    return path, True


def refresh_week_plan(root: Path, week_value: str) -> Path | None:
    progress = load_json(root / "state" / "progress.json")
    plan = progress.get("weekly_plans", {}).get(week_value)
    if not plan:
        return None
    path = root / plan["path"]
    write_text(path, render_week_plan(progress, week_value))
    return path


def _aggregate_task(task: dict[str, Any]) -> None:
    checkpoints = task["checkpoints"]
    if checkpoints and all(item["status"] == "done" for item in checkpoints):
        status = "done"
    elif any(item["status"] == "blocked" for item in checkpoints):
        status = "blocked"
    elif any(item["status"] in {"done", "in_progress"} for item in checkpoints):
        status = "in_progress"
    else:
        status = "queued"
    scores = [item["score"] for item in checkpoints if item["score"] is not None]
    evidence = [item["evidence"] for item in checkpoints if item.get("evidence")]
    artifacts = sorted(
        {
            artifact
            for item in checkpoints
            for artifact in item.get("artifacts", [])
        }
    )
    reviews = [item["next_review"] for item in checkpoints if item.get("next_review")]
    task["status"] = status
    task["score"] = round(sum(scores) / len(scores)) if scores else None
    task["evidence"] = " | ".join(evidence) if evidence else None
    task["artifacts"] = artifacts
    task["next_review"] = min(reviews) if reviews else None


def normalize_artifact_paths(root: Path, artifacts: Sequence[str | Path]) -> list[str]:
    """Return existing, repository-contained evidence paths in stable POSIX form."""
    resolved_root = root.resolve()
    normalized: set[str] = set()
    for value in artifacts:
        raw = Path(value)
        candidate = (resolved_root / raw).resolve() if not raw.is_absolute() else raw.resolve()
        try:
            relative = candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"Artifact must stay inside the repository: {value}") from exc
        if not candidate.is_file():
            raise ValueError(f"Artifact must be an existing file: {value}")
        if relative.parts and relative.parts[0] in {".git", "private"}:
            raise ValueError(f"Artifact cannot be published from {relative.parts[0]}: {value}")
        normalized.add(relative.as_posix())
    return sorted(normalized)


def _recording_kind(
    progress: dict[str, Any], task_id: str, target: date
) -> tuple[str, dict[str, Any]]:
    week_value = target.strftime("%G-W%V")
    plan = progress.get("weekly_plans", {}).get(week_value)
    if not plan:
        raise ValueError(f"No weekly plan exists for {week_value}")
    primary = _scheduled_primary_task(progress, plan, target)
    if not primary:
        raise ValueError(f"No primary task is scheduled for {target.isoformat()}")
    if task_id == primary["id"]:
        return "primary", primary

    completed_ids = {item["task_id"] for item in _completion_items(progress, target)}
    if primary["id"] not in completed_ids or not task_has_complete_evidence(primary):
        raise ValueError("Today's primary task must be completed before a carryover")
    carryovers = carryover_tasks(progress, target)
    if not carryovers or carryovers[0]["id"] != task_id:
        raise ValueError("Only the oldest carryover can be recorded after today's primary task")
    if carryovers[0].get("carryover_activated_on") != target.isoformat():
        raise ValueError("Run today --continue-carryover before recording a carryover")
    optional_completed = completed_ids - {primary["id"]}
    if optional_completed:
        raise ValueError("The optional carryover slot is already complete today")
    return "carryover", primary


def record_checkpoint(
    root: Path,
    task_id: str,
    checkpoint_id: str,
    status: str,
    score: int,
    evidence: str,
    recorded_on: date | None = None,
    artifacts: Sequence[str | Path] = (),
) -> dict[str, Any]:
    if status not in {"in_progress", "done", "blocked"}:
        raise ValueError("Record status must be in_progress, done, or blocked")
    if not 0 <= score <= 5:
        raise ValueError("Score must be between 0 and 5")
    if not evidence.strip():
        raise ValueError("Recorded checkpoints require evidence")
    normalized_artifacts = normalize_artifact_paths(root, artifacts)
    progress_path = root / "state" / "progress.json"
    progress = load_json(progress_path)
    require_schema_v2(progress)
    if task_id not in progress["tasks"]:
        raise KeyError(f"Unknown task: {task_id}")
    task = progress["tasks"][task_id]
    if task["status"] in {"done", "cancelled"}:
        raise ValueError(f"Task {task_id} is already {task['status']}")
    base = recorded_on or date.today()
    if base.weekday() >= 5:
        raise ValueError("A routine task cannot be recorded on a weekend rest day")
    recording_kind, primary = _recording_kind(progress, task_id, base)
    try:
        checkpoint = next(item for item in task["checkpoints"] if item["id"] == checkpoint_id)
    except StopIteration as exc:
        raise KeyError(f"Unknown checkpoint {checkpoint_id} for task {task_id}") from exc
    if checkpoint["status"] == "done":
        raise ValueError(f"Checkpoint {checkpoint_id} is already done")
    checkpoint.update(
        {
            "status": status,
            "score": score,
            "evidence": evidence.strip(),
            "artifacts": normalized_artifacts or list(checkpoint.get("artifacts", [])),
            "next_review": _review_date(score, base),
        }
    )
    previous_status = task["status"]
    _aggregate_task(task)
    if task["status"] == "done":
        completed_items = _completion_items(progress, base)
        completed_ids = {item["task_id"] for item in completed_items}
        if recording_kind == "carryover" and primary["id"] not in completed_ids:
            raise ValueError("Today's primary task must be completed before a carryover")
        if len(completed_ids) >= 2 and task_id not in completed_ids:
            raise ValueError("At most one primary task and one carryover can complete today")
        task["completed_on"] = base.isoformat()
        if task_id not in completed_ids:
            progress["completion_log"].append(
                {
                    "date": base.isoformat(),
                    "task_id": task_id,
                    "kind": recording_kind,
                    "evidence": str(task["evidence"]),
                    "artifacts": list(task.get("artifacts", [])),
                }
            )
        gate_id = task.get("gate_id")
        checkpoint_scores = [item.get("score") for item in task["checkpoints"]]
        if gate_id and all(score is not None and score >= 4 for score in checkpoint_scores):
            progress["phase_gates"][gate_id] = {
                "status": "passed",
                "score": min(checkpoint_scores),
                "evidence": task["evidence"],
            }
    elif previous_status != "done":
        task["completed_on"] = None
    blockers = set(progress.get("blockers", []))
    if task["status"] == "blocked":
        blockers.add(task_id)
    else:
        blockers.discard(task_id)
    progress["blockers"] = sorted(blockers)
    progress["updated_at"] = now_text()
    write_json(progress_path, progress)
    refresh_week_plan(root, base.strftime("%G-W%V"))
    return task


def record_task(
    root: Path,
    task_id: str,
    status: str,
    score: int,
    evidence: str,
    checkpoint_id: str = "work",
    recorded_on: date | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for callers that already operate on one checkpoint."""
    return record_checkpoint(root, task_id, checkpoint_id, status, score, evidence, recorded_on)


def _first_unfinished(task: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            checkpoint
            for checkpoint in task.get("checkpoints", [])
            if checkpoint["status"] not in {"done", "cancelled"}
        ),
        None,
    )


def _evidence_standard(checkpoint: dict[str, Any] | None) -> str | None:
    if not checkpoint:
        return None
    if checkpoint["id"] == "briefing":
        return "学习者本人写出的事实、风险、缺失信息和可验证假设。"
    if checkpoint["id"] == "lab":
        return "命令或代码、关键输出、验证结果，以及一次独立解释或变化。"
    if checkpoint["id"] == "written_handoff":
        return "学习者本人撰写的英文交接原文，包含证据、风险和下一步。"
    return "与任务要求对应的文件、命令输出或结构化演示，以及复核结果。"


def project_summary(
    learner: dict[str, Any], progress: dict[str, Any], target: date
) -> dict[str, Any]:
    profile = learner["learner"]
    start = date.fromisoformat(profile["start_date"])
    week = calendar_learning_week(start, target)
    done = sum(task_has_complete_evidence(task) for task in progress["tasks"].values())
    backlog = carryover_tasks(progress, target)
    gates_passed = sum(
        gate.get("status") == "passed" for gate in progress.get("phase_gates", {}).values()
    )
    career = progress.get("career", {})
    current_streak, best_streak = completion_streak(progress, start, target)
    return {
        "goal": "海外远程 DevOps 工程师的投递与面试能力",
        "readiness_date": readiness_date(start).isoformat(),
        "calendar_week": week,
        "weeks_total": 78,
        "phase": progress["current_phase"],
        "gates_passed": gates_passed,
        "gates_total": 6,
        "evidence_tasks_done": done,
        "portfolio_done": len(progress.get("portfolio", [])),
        "portfolio_target": 6,
        "open_source_done": int(career.get("accepted_open_source_contributions", 0)),
        "open_source_target": 3,
        "mock_interviews_done": int(career.get("mock_interviews", 0)),
        "mock_interviews_target": 3,
        "backlog_count": len(backlog),
        "course_lag": sum(int(task["curriculum_week"]) < week for task in backlog),
        "streak": {"current": current_streak, "best": best_streak},
    }


def _week_summary(
    progress: dict[str, Any], week_value: str, fallback: dict[str, Any], target: date
) -> dict[str, Any]:
    plan = progress.get("weekly_plans", {}).get(week_value)
    if not plan:
        return fallback
    new_tasks = [
        {
            "id": task_id,
            "title": progress["tasks"][task_id]["title"],
            "status": progress["tasks"][task_id]["status"],
        }
        for task_id in plan["new_task_ids"]
    ]
    backlog = [task["id"] for task in carryover_tasks(progress, target)]
    status = _week_status(progress, plan["execution_slots"])
    return {
        "id": week_value,
        "date_range": {"monday": plan["monday"], "friday": plan["friday"]},
        "theme": {"zh": plan["theme_zh"], "en": plan["theme_en"]},
        "calendar_phase": plan["calendar_phase"],
        "execution_phase": plan["execution_phase"],
        "gate_mode": plan["gate_mode"],
        "new_missions": new_tasks,
        "backlog": backlog,
        "execution_slots": list(plan["execution_slots"]),
        **status,
        "adaptation": dict(progress["adaptation"]),
    }


def today_overview(
    root: Path, target: date, continue_carryover: bool = False
) -> dict[str, Any]:
    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    progress_path = root / "state" / "progress.json"
    progress = load_json(progress_path)
    require_schema_v2(progress)
    start = date.fromisoformat(learner["learner"]["start_date"])
    week_number = calendar_learning_week(start, target)
    phase = phase_for_week(roadmap, week_number)
    focus = focus_for_week(phase, week_number)
    week_value = target.strftime("%G-W%V")
    monday, friday = week_bounds(week_value)
    fallback_week = {
        "id": week_value,
        "date_range": {"monday": monday.isoformat(), "friday": friday.isoformat()},
        "theme": {"zh": focus["title_zh"], "en": focus["title_en"]},
        "calendar_phase": phase["id"],
        "execution_phase": progress["current_phase"],
        "gate_mode": "normal",
        "new_missions": [],
        "backlog": [task["id"] for task in carryover_tasks(progress, target)],
        "execution_slots": [],
        "done": 0,
        "in_progress": 0,
        "blocked": 0,
        "queued": 0,
        "remaining": 0,
        "adaptation": dict(progress["adaptation"]),
    }
    if target.weekday() >= 5:
        return {
            "schema_version": 2,
            "project": project_summary(learner, progress, target),
            "week": _week_summary(progress, week_value, fallback_week, target),
            "today": {
                "date": target.isoformat(),
                "rest": True,
                "quota": 0,
                "quota_complete": True,
                "completed_task": None,
                "completed_tasks": [],
                "active_task": None,
                "active_task_kind": None,
                "next_checkpoint": None,
                "optional_carryover_limit": 0,
                "optional_carryover_available": False,
                "optional_carryover_complete": False,
                "completion_standard": "周末完全休息，不生成、补排或启动例行任务。",
                "evidence_required": None,
            },
        }

    ensure_master_plan(root)
    ensure_week_plan(root, week_value)
    progress = load_json(progress_path)
    progress["current_week"] = week_number
    plan = progress["weekly_plans"][week_value]
    progress["current_phase"] = plan["execution_phase"]
    primary_task = _scheduled_primary_task(progress, plan, target)
    if not primary_task:
        raise ValueError(f"No primary task is scheduled for {target.isoformat()}")
    completed_items = _completion_items(progress, target)
    completed_ids = [item["task_id"] for item in completed_items]
    primary_completed = (
        primary_task["id"] in completed_ids and task_has_complete_evidence(primary_task)
    )
    optional_completed_ids = [
        task_id for task_id in completed_ids if task_id != primary_task["id"]
    ]
    if len(optional_completed_ids) > 1:
        raise ValueError("More than one optional carryover is recorded for this workday")
    carryovers = carryover_tasks(progress, target)
    optional_limit = int(
        learner["learner"]["schedule"].get("optional_carryover_missions", 1)
    )
    if continue_carryover and not primary_completed:
        raise ValueError("Complete today's primary task before continuing a carryover")
    active_task: dict[str, Any] | None = None
    active_task_kind: str | None = None
    checkpoint: dict[str, Any] | None = None
    if not primary_completed:
        if primary_task["status"] not in ACTIVE_STATUSES:
            raise ValueError(f"Primary task {primary_task['id']} is not active")
        active_task = primary_task
        active_task_kind = "primary"
        checkpoint = _start_task(active_task)
    elif continue_carryover and not optional_completed_ids and carryovers:
        active_task = carryovers[0]
        active_task["carryover_activated_on"] = target.isoformat()
        active_task_kind = "carryover"
        checkpoint = _start_task(active_task)
    optional_available = bool(
        primary_completed and not optional_completed_ids and carryovers and optional_limit
    )
    progress["updated_at"] = now_text()
    write_json(progress_path, progress)
    refresh_week_plan(root, week_value)
    if active_task_kind == "primary":
        completion_standard = (
            "今日计划任务的全部检查点均为 done，且每个检查点都有可复核证据。"
        )
    elif active_task_kind == "carryover":
        completion_standard = (
            "当前可选遗留任务的全部检查点均为 done，且每个检查点都有可复核证据；"
            "完成后今天结束。"
        )
    elif optional_completed_ids:
        completion_standard = "今日主任务和一个可选遗留均已有完整证据；今天结束。"
    elif optional_available:
        completion_standard = (
            "今日主任务已有完整证据；默认停止。只有用户明确说“继续处理遗留”时，"
            "才启动最早遗留的一项。"
        )
    else:
        completion_standard = "今日主任务已有完整证据，且当前没有可选遗留；今天结束。"
    return {
        "schema_version": 2,
        "project": project_summary(learner, progress, target),
        "week": _week_summary(progress, week_value, fallback_week, target),
        "today": {
            "date": target.isoformat(),
            "rest": False,
            "quota": 1,
            "quota_complete": primary_completed,
            "completed_task": primary_task["id"] if primary_completed else None,
            "completed_tasks": completed_ids,
            "active_task": (
                {
                    "id": active_task["id"],
                    "title": active_task["title"],
                    "status": active_task["status"],
                }
                if active_task
                else None
            ),
            "active_task_kind": active_task_kind,
            "next_checkpoint": (
                {
                    "id": checkpoint["id"],
                    "title": checkpoint["title"],
                    "instruction": checkpoint["instruction"],
                    "status": checkpoint["status"],
                }
                if checkpoint
                else None
            ),
            "optional_carryover_limit": optional_limit,
            "optional_carryover_available": optional_available,
            "optional_carryover_complete": bool(optional_completed_ids),
            "completion_standard": completion_standard,
            "evidence_required": _evidence_standard(checkpoint),
        },
    }


def render_today_text(overview: dict[str, Any]) -> str:
    project = overview["project"]
    week = overview["week"]
    today = overview["today"]
    new_missions = (
        ", ".join(item["id"] for item in week["new_missions"])
        if week["new_missions"]
        else "周末不新建"
    )
    backlog = ", ".join(week["backlog"]) if week["backlog"] else "无"
    lines = [
        "总项目",
        f"- 目标：{project['goal']}；预计能力门槛日：{project['readiness_date']}",
        (
            f"- 规划：第 {project['calendar_week']}/{project['weeks_total']} 周；"
            f"当前阶段：{project['phase']}"
        ),
        (
            f"- 阶段门禁：{project['gates_passed']}/{project['gates_total']}；"
            f"证据完成任务：{project['evidence_tasks_done']}"
        ),
        (
            f"- 作品集：{project['portfolio_done']}/{project['portfolio_target']}；"
            f"开源贡献：{project['open_source_done']}/{project['open_source_target']}；"
            f"模拟面试：{project['mock_interviews_done']}/"
            f"{project['mock_interviews_target']}"
        ),
        (
            f"- 遗留：{project['backlog_count']}；课程滞后：{project['course_lag']}；"
            f"工作日连胜：当前 {project['streak']['current']} / "
            f"最佳 {project['streak']['best']}"
        ),
        "",
        "本周",
        f"- {week['id']}：{week['theme']['zh']} / {week['theme']['en']}",
        f"- 五项新任务：{new_missions}",
        f"- 遗留队列：{backlog}",
        (
            f"- 完成 {week['done']}；进行中 {week['in_progress']}；"
            f"阻塞 {week['blocked']}；剩余 {week['remaining']}"
        ),
        f"- 内容适应：{week['adaptation']['mode']} — {week['adaptation']['reason']}",
        "",
        "今天",
    ]
    if today["rest"]:
        lines.append(f"- {today['date']} 是周末休息日；不生成、补排或启动任务。")
        return "\n".join(lines)
    task = today["active_task"]
    checkpoint = today["next_checkpoint"]
    if today["quota_complete"] and not task:
        completed = ", ".join(today["completed_tasks"])
        lines.extend(
            [
                "- 每日定量：一个完整任务；今天已完成。",
                f"- 完成任务：{completed}",
                f"- 完成标准：{today['completion_standard']}",
            ]
        )
        return "\n".join(lines)
    if today["active_task_kind"] == "carryover":
        lines.extend(
            [
                "- 每日定量：一个完整任务；今日主任务已完成。",
                f"- 已完成任务：{today.get('completed_task')}",
                "- 用户已明确继续；现在最多处理一个可选遗留任务。",
                f"- 最早遗留任务：{task['id']} — {task['title']}",
                f"- 第一未完成检查点：{checkpoint['id']} / {checkpoint['title']}",
                f"- 任务要求：{checkpoint['instruction']}",
                f"- 完成标准：{today['completion_standard']}",
                f"- 所需证据：{today['evidence_required']}",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "- 每日定量：一个完整任务。",
            f"- 今日计划任务：{task['id']} — {task['title']}",
            f"- 第一未完成检查点：{checkpoint['id']} / {checkpoint['title']}",
            f"- 任务要求：{checkpoint['instruction']}",
            f"- 完成标准：{today['completion_standard']}",
            f"- 所需证据：{today['evidence_required']}",
        ]
    )
    return "\n".join(lines)


def create_today_plan(root: Path, target: date) -> tuple[Path | None, bool]:
    """Compatibility wrapper: schema v2 returns the living weekly plan, never a daily file."""
    if target.weekday() >= 5:
        today_overview(root, target)
        return None, False
    week_value = target.strftime("%G-W%V")
    before = (root / "plans" / "weeks" / f"{week_value}.md").exists()
    today_overview(root, target)
    path = root / "plans" / "weeks" / f"{week_value}.md"
    return path, not before
