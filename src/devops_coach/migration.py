from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, load_yaml, write_json, write_text

ACTIVE_STATUSES = {"queued", "in_progress", "blocked"}
SPECIAL_QUEUE = (
    "2026-08-08-project",
    "2026-08-08-review",
    "2026-08-21-mission",
)
POLICY_RESET_DATE = "2026-08-24"
POLICY_BACKLOG_TASK_IDS = (
    "2026-08-08-project",
    "2026-08-08-review",
    "2026-08-21-mission",
    "2026-W34-01-mission",
    "2026-W34-02-mission",
    "2026-W34-03-mission",
    "2026-W34-04-mission",
    "2026-W34-05-mission",
)
COGNITIVE_WORKFLOW_VERSION = "cognitive_apprenticeship_v1"
COGNITIVE_ARCHIVE_NAME = "progress-pre-cognitive-apprenticeship-v1.json"


def _calendar_week(start: date, target: date) -> int:
    start_monday = start - timedelta(days=start.weekday())
    target_monday = target - timedelta(days=target.weekday())
    return max(1, min(78, (target_monday - start_monday).days // 7 + 1))


def _phase_id(roadmap: dict[str, Any], week: int) -> str:
    for phase in roadmap["phases"]:
        if phase["week_start"] <= week <= phase["week_end"]:
            return str(phase["id"])
    raise ValueError(f"No phase covers week {week}")


def _checkpoint(
    checkpoint_id: str,
    title: str,
    instruction: str,
    status: str,
    score: int | None,
    evidence: str | None,
    next_review: str | None,
) -> dict[str, Any]:
    return {
        "id": checkpoint_id,
        "title": title,
        "instruction": instruction,
        "status": status,
        "score": score,
        "evidence": evidence,
        "next_review": next_review,
    }


def _legacy_status(value: str) -> str:
    return {
        "planned": "queued",
        "partial": "in_progress",
        "done": "done",
        "blocked": "blocked",
        "cancelled": "cancelled",
    }.get(value, "queued")


def _without_duration_requirement(value: str) -> str:
    value = value.replace("一分钟长度的", "简短的")
    value = re.sub(r"至少投入 \d+ 分钟", "并提交可验证证据", value)
    value = re.sub(r"至少 \d+ 分钟用英语完成", "用英语完成", value)
    value = re.sub(r"至少 \d+ 分钟", "并提交可验证证据", value)
    value = re.sub(r"\d+\s*分钟", "已记录投入", value)
    value = re.sub(r"\b\d+\s+minutes?\b", "recorded effort", value, flags=re.I)
    return value


def _legacy_task(
    task: dict[str, Any],
    roadmap: dict[str, Any],
    start: date,
    daily_plans: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(task["id"])
    created_on = str(task.get("date") or start.isoformat())
    daily = daily_plans.get(created_on, {})
    week = int(daily.get("week") or _calendar_week(start, date.fromisoformat(created_on)))
    phase = str(daily.get("phase") or _phase_id(roadmap, week))
    status = _legacy_status(str(task.get("status", "planned")))
    score = task.get("score")
    raw_evidence = task.get("evidence")
    evidence = (
        _without_duration_requirement(str(raw_evidence)) if raw_evidence is not None else None
    )
    next_review = task.get("next_review")
    checkpoint_status = status
    title = _without_duration_requirement(str(task.get("title") or task_id))
    checkpoint = _checkpoint(
        "work",
        "历史任务",
        title,
        checkpoint_status,
        score,
        evidence,
        next_review,
    )
    return {
        "id": task_id,
        "created_on": created_on,
        "scheduled_for": created_on,
        "curriculum_week": week,
        "phase": phase,
        "section": str(task.get("section") or "legacy"),
        "title": title,
        "status": status,
        "score": score,
        "evidence": evidence,
        "completed_on": created_on if status == "done" else None,
        "next_review": next_review,
        "queue_order": 1000,
        "source": "legacy-v1",
        "checkpoints": [checkpoint],
    }


def _apply_locked_queue(tasks: dict[str, dict[str, Any]], root: Path) -> None:
    project_id, review_id, mission_id = SPECIAL_QUEUE
    if project_id not in tasks or review_id not in tasks or mission_id not in tasks:
        missing = [task_id for task_id in SPECIAL_QUEUE if task_id not in tasks]
        raise ValueError(f"Migration source is missing locked tasks: {', '.join(missing)}")

    draft = root / "evidence" / "week-02" / "linux-file-search-runbook" / "README.md"
    draft_evidence = "evidence/week-02/linux-file-search-runbook/README.md"
    project = tasks[project_id]
    project.update(
        {
            "title": "扩充 Linux Runbook：加入文件定位、内容搜索和安全文件操作；完成英文 README。",
            "status": "in_progress",
            "score": None,
            "evidence": draft_evidence if draft.exists() else None,
            "completed_on": None,
            "next_review": None,
            "queue_order": 1,
        }
    )
    project["checkpoints"] = [
        _checkpoint(
            "work",
            "Runbook 实作",
            "补全可重复的文件定位、内容搜索和安全文件操作 Runbook，并提交复核证据。",
            "in_progress",
            None,
            draft_evidence if draft.exists() else None,
            None,
        )
    ]

    review = tasks[review_id]
    review.update(
        {
            "status": "queued",
            "score": None,
            "evidence": None,
            "completed_on": None,
            "next_review": None,
            "queue_order": 2,
        }
    )
    review["checkpoints"] = [
        _checkpoint(
            "work",
            "安全复核",
            "确认所有示例均限定在 sandbox，并用只读预览证明不会触碰宽路径。",
            "queued",
            None,
            None,
            None,
        )
    ]

    mission = tasks[mission_id]
    briefing_evidence = (
        "Learner identified the missing target version, approved server access path, "
        "and rollback plan for a remote Nginx change; independently explained the risk."
    )
    lab_evidence = (
        "Read-only Ubuntu and APT evidence: Ubuntu 22.04, nginx "
        "1.18.0-6ubuntu14.18, and Installed equals Candidate from configured repositories."
    )
    mission.update(
        {
            "status": "in_progress",
            "score": 4,
            "completed_on": None,
            "next_review": None,
            "queue_order": 3,
        }
    )
    mission["checkpoints"] = [
        _checkpoint(
            "briefing",
            "事件简报",
            "说明已知事实、主要风险、缺失信息和第一条可验证假设。",
            "done",
            4,
            briefing_evidence,
            None,
        ),
        _checkpoint(
            "lab",
            "实战处理",
            "补齐依赖、包文件、影响与回滚证据；不得执行未经授权的安装或升级。",
            "in_progress",
            None,
            lab_evidence,
            None,
        ),
        _checkpoint(
            "written_handoff",
            "英文书面交接",
            "Write a package change brief with source, version, dependencies, risk, and rollback.",
            "queued",
            None,
            None,
            None,
        ),
    ]

    next_order = 4
    for task_id, task in sorted(tasks.items(), key=lambda item: (item[1]["created_on"], item[0])):
        if task_id in SPECIAL_QUEUE:
            continue
        if task["status"] in ACTIVE_STATUSES:
            task["queue_order"] = next_order
            next_order += 1
    completed_order = 1000
    for task_id, task in sorted(tasks.items()):
        if task_id in SPECIAL_QUEUE or task["status"] in ACTIVE_STATUSES:
            continue
        task["queue_order"] = completed_order
        completed_order += 1


def _historical_completion_log(
    legacy: dict[str, Any], tasks: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for day, daily in sorted(legacy.get("daily_plans", {}).items()):
        task_date = date.fromisoformat(day)
        if task_date.weekday() >= 5:
            continue
        included = [
            tasks[task_id]
            for task_id in daily.get("task_ids", [])
            if task_id in tasks and tasks[task_id]["status"] != "cancelled"
        ]
        if not included:
            continue
        if all(task["status"] == "done" and task.get("evidence") for task in included):
            result.append(
                {
                    "date": day,
                    "task_id": included[-1]["id"],
                    "evidence": "Legacy day derived from completed evidence tasks: "
                    + ", ".join(task["id"] for task in included),
                }
            )
    return result


def _phase_gates(roadmap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, phase in enumerate(roadmap["phases"]):
        result[str(phase["id"])] = {
            "status": "active" if index == 0 else "locked",
            "score": None,
            "evidence": None,
        }
    return result


def transform_progress_v1(
    legacy: dict[str, Any],
    learner: dict[str, Any],
    roadmap: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    if legacy.get("schema_version") != 1:
        raise ValueError("Only progress schema v1 can be migrated to schema v2")
    start = date.fromisoformat(learner["learner"]["start_date"])
    tasks = {
        task_id: _legacy_task(deepcopy(task), roadmap, start, legacy.get("daily_plans", {}))
        for task_id, task in legacy.get("tasks", {}).items()
    }
    _apply_locked_queue(tasks, root)
    current_week = int(legacy.get("current_week", 1))
    current_phase = _phase_id(roadmap, current_week)
    return {
        "schema_version": 2,
        "current_week": current_week,
        "current_phase": current_phase,
        "weekly_plans": {},
        "tasks": tasks,
        "blockers": sorted(
            task_id for task_id, task in tasks.items() if task["status"] == "blocked"
        ),
        "completion_log": _historical_completion_log(legacy, tasks),
        "portfolio": deepcopy(legacy.get("portfolio", [])),
        "career": deepcopy(
            legacy.get(
                "career",
                {
                    "accepted_open_source_contributions": 0,
                    "applications": 0,
                    "english_demos": 0,
                    "mock_interviews": 0,
                },
            )
        ),
        "adaptation": {
            "mode": "standard",
            "reason": "迁移后按任务完成数、掌握度和阻塞调整内容。",
            "source_week": None,
            "generated_at": None,
        },
        "weekly_reviews": {},
        "phase_gates": _phase_gates(roadmap),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def transform_learner_v1(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("schema_version") == 2:
        return deepcopy(config)
    if config.get("schema_version") != 1:
        raise ValueError("Only learner schema v1 can be migrated to schema v2")
    result = deepcopy(config)
    result["schema_version"] = 2
    result["learner"]["schedule"] = {
        "weekday_missions": 1,
        "optional_carryover_missions": 1,
        "saturday_missions": 0,
        "sunday_missions": 0,
    }
    result["learner"]["engagement"] = {
        "style": "incident_mission",
        "streak_basis": "completed_evidence_task",
        "backlog_order": "today_first_then_oldest",
    }
    result["learner"]["publication"] = {
        "mode": "auto_after_task_completion",
        "integration": "ready_pr_squash",
        "base_branch": "main",
        "branch_prefix": "learn",
        "primary_per_workday": 1,
        "optional_carryover_per_workday": 1,
        "recover_before_today": True,
    }
    return result


def migrate_to_schema_2(root: Path, dry_run: bool = False) -> dict[str, Any]:
    state_path = root / "state" / "progress.json"
    config_path = root / "config" / "learner.yml"
    archive_path = root / "state" / "archive" / "progress-v1.json"
    raw_state = state_path.read_bytes()
    legacy = load_json(state_path)
    if legacy.get("schema_version") == 2:
        return {
            "changed": False,
            "dry_run": dry_run,
            "schema_version": 2,
            "archive": archive_path.relative_to(root).as_posix() if archive_path.exists() else None,
            "message": "Progress is already schema v2; no files changed.",
        }

    learner = load_yaml(config_path)
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    migrated = transform_progress_v1(legacy, learner, roadmap, root)
    migrated_learner = transform_learner_v1(learner)
    summary = {
        "changed": not dry_run,
        "dry_run": dry_run,
        "from_schema": 1,
        "to_schema": 2,
        "archive": archive_path.relative_to(root).as_posix(),
        "task_count": len(migrated["tasks"]),
        "active_queue": [
            task["id"]
            for task in sorted(migrated["tasks"].values(), key=lambda item: item["queue_order"])
            if task["status"] in ACTIVE_STATUSES
        ],
        "historical_completion_days": len(migrated["completion_log"]),
    }
    if dry_run:
        return summary

    if archive_path.exists():
        if archive_path.read_bytes() != raw_state:
            raise ValueError("Existing progress-v1 archive differs from the migration source")
    else:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(raw_state)
    write_json(state_path, migrated)
    if learner != migrated_learner:
        import yaml

        config_path.write_text(
            yaml.safe_dump(
                migrated_learner,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
            newline="\n",
        )
    return summary


def _cognitive_blueprint_content(
    roadmap: dict[str, Any], week: int, slot: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return one concrete weekly project and mission; generic fallbacks are forbidden."""
    from devops_coach.planner import cognitive_task_content

    content = cognitive_task_content(roadmap, week, slot)
    return content["project"], content["mission"]


def _task_mission_slot(task: dict[str, Any]) -> int:
    task_id = str(task.get("id", ""))
    match = re.search(r"-W\d{2}-(0[1-5])-mission$", task_id)
    if match:
        return int(match.group(1)) - 1
    scheduled_for = task.get("scheduled_for")
    if scheduled_for:
        weekday = date.fromisoformat(str(scheduled_for)).weekday()
        if 0 <= weekday <= 4:
            return weekday
    raise ValueError(f"Cannot determine the weekday mission slot for task {task_id}")


def _checkpoint_success_criteria(checkpoint_id: str, assessment: str) -> str:
    if assessment == "legacy":
        return "历史证据已保留，不重新提问或重新评分。"
    if checkpoint_id == "briefing":
        return "用自己的话解释心智模型，并在执行前给出一个可检验预测。"
    if checkpoint_id == "lab":
        return "先选择下一步并预测结果，再执行、观察并解释；该阶段不计分。"
    return (
        "在变化条件下独立完成任务，提交预测、学习者动作、实际结果、解释，"
        "并写出 2–4 句英文 PR 评论或交接。"
    )


def _new_checkpoint_metadata(checkpoint: dict[str, Any], assessment: str) -> None:
    checkpoint["assessment"] = assessment
    checkpoint["hint_level_used"] = None
    checkpoint["independent"] = False
    checkpoint["evidence_details"] = None
    checkpoint["success_criteria"] = _checkpoint_success_criteria(
        str(checkpoint.get("id", "")), assessment
    )
    if assessment == "legacy":
        checkpoint["coach_action"] = "保留历史证据，不要求学习者重复作答。"
        checkpoint["learner_action"] = "无需重复已经完成并验证的历史检查点。"
        checkpoint["hint_policy"] = "历史记录不推断提示级别或独立完成状态。"
    elif checkpoint.get("id") == "briefing":
        checkpoint["coach_action"] = "先用中文解释概念和命令组成，然后只提出一个目标相关问题。"
        checkpoint["learner_action"] = "解释当前概念并写出一个可检验预测，不复制现成答案。"
        checkpoint["hint_policy"] = (
            "按需依次使用概念提示、带空格命令骨架、完整拆解；完整提示后必须换题。"
        )
    elif checkpoint.get("id") == "lab":
        checkpoint["coach_action"] = (
            "等待学习者先决策和预测，再按提示层级逐级帮助并脱敏检查输出。"
        )
        checkpoint["learner_action"] = (
            "选择或补全命令，先预测后执行，并用自己的话解释实际结果。"
        )
        checkpoint["hint_policy"] = (
            "按需依次使用概念提示、带空格命令骨架、完整拆解；完整提示后必须换题。"
        )
    else:
        checkpoint["coach_action"] = (
            "提供变化条件但不给完整命令；只验证证据并按 0–5 分总结评价。"
        )
        checkpoint["learner_action"] = (
            "独立选择或编写命令，预测、执行、解释，并完成英文书面交付。"
        )
        checkpoint["hint_policy"] = (
            "不提供完整命令；若需要完整提示，本次转回引导练习并更换变化题。"
        )


def _transform_active_task_to_cognitive_workflow(
    task: dict[str, Any], roadmap: dict[str, Any]
) -> dict[str, int]:
    week = int(task["curriculum_week"])
    slot = _task_mission_slot(task)
    project, mission = _cognitive_blueprint_content(roadmap, week, slot)
    acceptance = project.get("acceptance_criteria")
    if not isinstance(acceptance, list) or not acceptance or not all(
        isinstance(item, str) and item.strip() for item in acceptance
    ):
        raise ValueError(
            f"Training blueprint for curriculum week {week} needs acceptance criteria"
        )

    task["workflow_version"] = COGNITIVE_WORKFLOW_VERSION
    task["weekly_project_id"] = str(project["id"])
    task["learning_goal"] = str(mission["learning_goal"])
    task["success_criteria"] = list(acceptance)
    task["scenario"] = str(mission["scenario"])
    task["title"] = f"{mission['codename']}：{mission['learning_goal']}"
    preserved_briefing = any(
        checkpoint.get("id") == "briefing"
        and checkpoint.get("status") == "done"
        and checkpoint.get("evidence")
        for checkpoint in task.get("checkpoints", [])
    )

    preserved = 0
    converted = 0
    for checkpoint in task.get("checkpoints", []):
        if checkpoint.get("status") == "done" and checkpoint.get("evidence"):
            # Historical verified work remains exactly as recorded; metadata only prevents
            # the new coach from asking the learner to repeat it.
            _new_checkpoint_metadata(checkpoint, "legacy")
            preserved += 1
            continue

        checkpoint_id = checkpoint.get("id")
        if checkpoint_id == "briefing":
            checkpoint["title"] = "概念与预测"
            checkpoint["instruction"] = str(mission["concept_prompt"])
            assessment = "formative"
        elif checkpoint_id == "lab":
            checkpoint["title"] = "引导练习"
            checkpoint["instruction"] = str(mission["guided_practice"])
            assessment = "formative"
        elif checkpoint_id == "written_handoff":
            checkpoint["title"] = "独立迁移与交付"
            checkpoint["instruction"] = str(mission["independent_delivery"])
            assessment = "summative"
        else:
            raise ValueError(
                f"Unsupported checkpoint {checkpoint_id!r} in cognitive task {task['id']}"
            )
        # An incomplete legacy checkpoint has no mastery value in the new workflow.
        checkpoint["score"] = None
        checkpoint["next_review"] = None
        _new_checkpoint_metadata(checkpoint, assessment)
        if checkpoint_id == "lab" and preserved_briefing:
            concepts = "、".join(str(item) for item in project.get("core_concepts", []))
            checkpoint["instruction"] = (
                f"概念桥接：教练先用中文讲清 {concepts} 的关系；随后只问这一题："
                f"{mission['concept_prompt']} 学习者回答并给出预测后，再进入引导练习："
                f"{mission['guided_practice']}"
            )
            checkpoint["coach_action"] = (
                "先讲清周项目所需的对象关系，再只提出 instruction 中的一个判断题；"
                "收到学习者预测后才进入引导练习。"
            )
            checkpoint["learner_action"] = (
                "先用自己的话回答一个判断题并给出可检验预测，再选择引导练习的下一步。"
            )
        converted += 1
    summative = [
        checkpoint
        for checkpoint in task.get("checkpoints", [])
        if checkpoint.get("assessment") == "summative"
    ]
    summative_scores = [
        int(checkpoint["score"])
        for checkpoint in summative
        if checkpoint.get("score") is not None
    ]
    task["score"] = min(summative_scores) if summative_scores else None
    summative_reviews = [
        str(checkpoint["next_review"])
        for checkpoint in summative
        if checkpoint.get("next_review")
    ]
    task["next_review"] = min(summative_reviews) if summative_reviews else None
    return {"preserved": preserved, "converted": converted}


def transform_training_workflow(
    progress: dict[str, Any], roadmap: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if progress.get("schema_version") != 2:
        raise ValueError("Progress schema v2 is required before migrating the training workflow")
    migrated = deepcopy(progress)
    migrated_ids: list[str] = []
    preserved = 0
    converted = 0
    for task_id, task in migrated.get("tasks", {}).items():
        if task.get("status") not in ACTIVE_STATUSES:
            continue
        if task.get("source") != "weekly-plan":
            continue
        if task.get("workflow_version") == COGNITIVE_WORKFLOW_VERSION:
            continue
        stats = _transform_active_task_to_cognitive_workflow(task, roadmap)
        migrated_ids.append(task_id)
        preserved += stats["preserved"]
        converted += stats["converted"]
    if migrated_ids:
        migrated["workflow_version"] = COGNITIVE_WORKFLOW_VERSION
    return migrated, {
        "task_ids": migrated_ids,
        "legacy_checkpoints_preserved": preserved,
        "checkpoints_converted": converted,
    }


def migrate_to_training_workflow(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Migrate active schema-v2 missions without recording or publishing evidence."""
    state_path = root / "state" / "progress.json"
    archive_path = root / "state" / "archive" / COGNITIVE_ARCHIVE_NAME
    raw_state = state_path.read_bytes()
    progress = load_json(state_path)
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    migrated, details = transform_training_workflow(progress, roadmap)
    progress_would_change = migrated != progress
    cognitive_weeks = sorted(
        week_value
        for week_value, plan in migrated.get("weekly_plans", {}).items()
        if any(
            migrated.get("tasks", {}).get(task_id, {}).get("workflow_version")
            == COGNITIVE_WORKFLOW_VERSION
            for task_id in plan.get("new_task_ids", [])
        )
    )
    from devops_coach.planner import render_week_plan

    expected_plans = {
        week_value: render_week_plan(migrated, week_value)
        for week_value in cognitive_weeks
    }
    plans_needing_sync = [
        week_value
        for week_value, expected in expected_plans.items()
        if not (path := root / "plans" / "weeks" / f"{week_value}.md").exists()
        or path.read_text(encoding="utf-8") != expected
    ]
    would_change = progress_would_change or bool(plans_needing_sync)
    summary = {
        "changed": would_change and not dry_run,
        "would_change": would_change,
        "dry_run": dry_run,
        "workflow_version": COGNITIVE_WORKFLOW_VERSION,
        "archive": archive_path.relative_to(root).as_posix(),
        "weekly_plans_synced": plans_needing_sync,
        **details,
    }
    if dry_run or not would_change:
        return summary

    if progress_would_change:
        if archive_path.exists():
            if archive_path.read_bytes() != raw_state:
                raise ValueError(
                    "Existing cognitive-apprenticeship archive differs from the migration source"
                )
        else:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_path.write_bytes(raw_state)
        migrated["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_json(state_path, migrated)
    for week_value in plans_needing_sync:
        write_text(
            root / "plans" / "weeks" / f"{week_value}.md",
            expected_plans[week_value],
        )
    return summary


def retire_policy_backlog(root: Path, dry_run: bool = False) -> dict[str, Any]:
    """Logically retire the pre-policy active queue while preserving audit evidence."""
    state_path = root / "state" / "progress.json"
    archive_path = (
        root
        / "state"
        / "archive"
        / f"progress-pre-queue-policy-{POLICY_RESET_DATE}.json"
    )
    raw_state = state_path.read_bytes()
    progress = load_json(state_path)
    if progress.get("schema_version") != 2:
        raise ValueError("Progress schema v2 is required before retiring the policy backlog")

    missing = [task_id for task_id in POLICY_BACKLOG_TASK_IDS if task_id not in progress["tasks"]]
    if missing:
        raise ValueError(f"Policy backlog tasks are missing: {', '.join(missing)}")
    retire_ids = [
        task_id
        for task_id in POLICY_BACKLOG_TASK_IDS
        if progress["tasks"][task_id].get("status") in ACTIVE_STATUSES
    ]
    summary = {
        "changed": bool(retire_ids) and not dry_run,
        "dry_run": dry_run,
        "policy_date": POLICY_RESET_DATE,
        "archive": archive_path.relative_to(root).as_posix(),
        "retired_ids": retire_ids,
    }
    if not retire_ids or dry_run:
        return summary

    if archive_path.exists():
        if archive_path.read_bytes() != raw_state:
            raise ValueError("Existing queue-policy archive differs from the migration source")
    else:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(raw_state)

    for task_id in retire_ids:
        task = progress["tasks"][task_id]
        task["status"] = "cancelled"
        task["completed_on"] = None
        task["next_review"] = None
        for checkpoint in task.get("checkpoints", []):
            if checkpoint.get("status") != "done":
                checkpoint["status"] = "cancelled"
                checkpoint["next_review"] = None

    retired = set(retire_ids)
    progress["blockers"] = [
        task_id for task_id in progress.get("blockers", []) if task_id not in retired
    ]
    current_plan = progress.get("weekly_plans", {}).get("2026-W35")
    if current_plan:
        current_plan["execution_slots"] = list(current_plan["new_task_ids"])
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(state_path, progress)

    from devops_coach.planner import refresh_week_plan

    for week_value in ("2026-W34", "2026-W35"):
        refresh_week_plan(root, week_value)
    return summary
