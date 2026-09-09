from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from devops_coach.planner import (
    COGNITIVE_WORKFLOW,
    SUMMATIVE_EVIDENCE_FIELDS,
    focus_for_week,
    phase_for_week,
    render_master_plan,
    task_has_complete_evidence,
)
from devops_coach.storage import load_json, load_yaml

FORBIDDEN_ACTIVE_KEYS = {
    "planned_minutes",
    "actual_minutes",
    "minimum_session_minutes",
    "weekday_minutes",
    "saturday_minutes",
    "sunday_minutes",
    "minutes",
    "load_factor",
}
FORBIDDEN_PLAN_TERMS = (
    "planned_minutes",
    "actual_minutes",
    "minimum_session_minutes",
    "load_factor",
    "预计时间",
    "总时长",
)
FORBIDDEN_ACTIVE_TERMS = ("分钟", " minute", "minutes")


def _validate(instance: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


def _forbidden_keys(value: Any, path: str = "<root>") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_ACTIVE_KEYS or key.endswith("_minutes"):
                errors.append(f"{child_path}: time-based field is forbidden in schema v2")
            errors.extend(_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_forbidden_keys(child, f"{path}[{index}]"))
    return errors


def validate_project(root: Path) -> list[str]:
    errors: list[str] = []
    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    progress = load_json(root / "state" / "progress.json")
    errors.extend(
        f"learner: {item}" for item in _validate(learner, root / "schemas" / "learner.schema.json")
    )
    errors.extend(
        f"roadmap: {item}" for item in _validate(roadmap, root / "schemas" / "roadmap.schema.json")
    )
    errors.extend(
        f"progress: {item}"
        for item in _validate(progress, root / "schemas" / "progress.schema.json")
    )
    errors.extend(f"learner: {item}" for item in _forbidden_keys(learner))
    errors.extend(f"progress: {item}" for item in _forbidden_keys(progress))
    learner_text = json.dumps(learner, ensure_ascii=False).lower()
    progress_text = json.dumps(progress, ensure_ascii=False).lower()
    for term in FORBIDDEN_ACTIVE_TERMS:
        if term in learner_text:
            errors.append(f"learner: active config contains forbidden duration term {term}")
        if term in progress_text:
            errors.append(f"progress: active state contains forbidden duration term {term}")

    phases = roadmap.get("phases", [])
    expected_week = 1
    focus_weeks: list[int] = []
    for phase in phases:
        if phase["week_start"] != expected_week:
            errors.append(f"roadmap: phase {phase['id']} should start at week {expected_week}")
        expected_week = phase["week_end"] + 1
        focus_weeks.extend(item["week"] for item in phase["weekly_focus"])
    if expected_week != 79:
        errors.append("roadmap: phases must cover weeks 1 through 78")
    if focus_weeks != list(range(1, 79)):
        errors.append("roadmap: weekly_focus must contain each week 1 through 78 exactly once")

    starter_weeks = roadmap.get("starter_weeks", [])
    if [item.get("week") for item in starter_weeks] != [1, 2, 3, 4]:
        errors.append("roadmap: starter_weeks must contain weeks 1 through 4 in order")
    for starter in starter_weeks:
        if len(starter.get("missions", [])) != 5:
            errors.append(f"roadmap: starter week {starter.get('week')} must contain 5 missions")

    blueprints = roadmap.get("training_blueprints", [])
    blueprint_weeks = [item.get("week") for item in blueprints]
    if blueprint_weeks != list(range(5, 14)):
        errors.append("roadmap: training_blueprints must contain weeks 5 through 13 in order")
    project_ids = [item.get("project", {}).get("id") for item in blueprints]
    if len(project_ids) != len(set(project_ids)):
        errors.append("roadmap: training blueprint project ids must be unique")
    for blueprint in blueprints:
        if len(blueprint.get("missions", [])) != 5:
            errors.append(
                f"roadmap: training blueprint week {blueprint.get('week')} must contain 5 missions"
            )

    schedule = learner.get("learner", {}).get("schedule", {})
    expected_schedule = {
        "weekday_missions": 1,
        "saturday_missions": 0,
        "sunday_missions": 0,
    }
    if {key: schedule.get(key) for key in expected_schedule} != expected_schedule:
        errors.append(
            "schedule: weekdays require one primary mission and weekends must have none"
        )
    backlog_order = learner.get("learner", {}).get("engagement", {}).get("backlog_order")
    if backlog_order != "today_first_then_oldest":
        errors.append("engagement: backlog order must prioritize today, then the oldest carryover")
    publication = learner.get("learner", {}).get("publication", {})
    expected_publication = {
        "mode": "auto_after_task_completion",
        "integration": "ready_pr_squash",
        "base_branch": "main",
        "branch_prefix": "learn",
        "primary_per_workday": 1,
        "recover_before_today": True,
    }
    if {key: publication.get(key) for key in expected_publication} != expected_publication:
        errors.append(
            "publication: completed primary and carryover tasks require separate Ready PRs, "
            "squash merge, and next-workday recovery"
        )
    if schedule.get("optional_carryover_missions") != publication.get(
        "optional_carryover_per_workday"
    ):
        errors.append(
            "carryover: schedule and publication limits must match; null means unlimited"
        )

    expected_gate_ids = [str(phase["id"]) for phase in phases]
    actual_gate_ids = set(progress.get("phase_gates", {}))
    if actual_gate_ids != set(expected_gate_ids):
        errors.append("progress: phase_gates must match the six roadmap phases")
    for gate_id, gate in progress.get("phase_gates", {}).items():
        if gate.get("status") == "passed" and (
            gate.get("score") is None or gate["score"] < 4 or not gate.get("evidence")
        ):
            errors.append(
                f"progress: passed gate {gate_id} requires score 4/5 or higher and evidence"
            )

    cognitive_tasks = [
        task
        for task in progress.get("tasks", {}).values()
        if task.get("workflow_version") == COGNITIVE_WORKFLOW
    ]
    if cognitive_tasks and progress.get("workflow_version") != COGNITIVE_WORKFLOW:
        errors.append("progress: cognitive tasks require the cognitive workflow version")
    assessed_tasks = cognitive_tasks + [
        task for task in progress.get("tasks", {}).values()
        if task.get("workflow_version") != COGNITIVE_WORKFLOW
        and any(
            checkpoint.get("assessment") in {"formative", "summative"}
            for checkpoint in task.get("checkpoints", [])
        )
    ]
    for task in assessed_tasks:
        task_id = task.get("id", "<unknown>")
        required_fields = (
            ("weekly_project_id", "learning_goal", "success_criteria")
            if task.get("workflow_version") == COGNITIVE_WORKFLOW else ()
        )
        for field in required_fields:
            if not task.get(field):
                errors.append(f"progress: cognitive task {task_id} requires {field}")
        checkpoints = task.get("checkpoints", [])
        assessments = [item.get("assessment") for item in checkpoints]
        if (
            len(assessments) != 3
            or any(value not in {"legacy", "formative"} for value in assessments[:2])
            or assessments[-1:] != ["summative"]
        ):
            errors.append(
                f"progress: cognitive task {task_id} requires formative stages "
                "followed by summative"
            )
        for checkpoint in checkpoints:
            checkpoint_id = checkpoint.get("id", "<unknown>")
            for field in (
                "success_criteria",
                "coach_action",
                "learner_action",
                "hint_policy",
                "independent",
            ):
                if field not in checkpoint or checkpoint.get(field) in {None, ""}:
                    errors.append(
                        f"progress: cognitive checkpoint {task_id}/{checkpoint_id} requires {field}"
                    )
            assessment = checkpoint.get("assessment")
            if assessment == "legacy" and not (
                checkpoint.get("status") == "done" and checkpoint.get("evidence")
            ):
                errors.append(
                    f"progress: legacy checkpoint {task_id}/{checkpoint_id} "
                    "must preserve done evidence"
                )
            if assessment == "formative" and checkpoint.get("score") is not None:
                errors.append(
                    f"progress: formative checkpoint {task_id}/{checkpoint_id} cannot be scored"
                )
            if assessment == "summative" and checkpoint.get("status") == "done":
                details = checkpoint.get("evidence_details")
                if not isinstance(details, dict) or any(
                    not isinstance(details.get(field), str) or not details[field].strip()
                    for field in SUMMATIVE_EVIDENCE_FIELDS
                ):
                    errors.append(
                        f"progress: summative checkpoint {task_id}/{checkpoint_id} "
                        "requires structured evidence"
                    )
                if checkpoint.get("score") in {4, 5} and (
                    checkpoint.get("independent") is not True
                    or checkpoint.get("hint_level_used") != 0
                ):
                    errors.append(
                        f"progress: score 4-5 for {task_id}/{checkpoint_id} "
                        "requires independent work with hint level 0"
                    )
        if task.get("status") == "done" and not task_has_complete_evidence(task):
            errors.append(f"progress: cognitive task {task_id} lacks complete summative evidence")

    master_path = root / "plans" / "master-plan.md"
    expected_master = render_master_plan(learner, roadmap)
    if not master_path.exists():
        errors.append("plans: master-plan.md is missing")
    elif master_path.read_text(encoding="utf-8") != expected_master:
        errors.append("plans: master-plan.md is not synchronized with learner.yml and roadmap.yml")

    for week_value, plan in progress.get("weekly_plans", {}).items():
        if len(plan.get("new_task_ids", [])) != 5:
            errors.append(f"plans: {week_value} must contain exactly five new tasks")
        if len(plan.get("execution_slots", [])) != 5:
            errors.append(f"plans: {week_value} must have five execution slots")
        monday = date.fromisoformat(plan["monday"])
        friday = date.fromisoformat(plan["friday"])
        if (
            monday.weekday() != 0
            or friday != monday + timedelta(days=4)
            or monday.strftime("%G-W%V") != week_value
        ):
            errors.append(f"plans: {week_value} must span calendar Monday through Friday")
        expected_phase = phase_for_week(roadmap, int(plan["week"]))
        expected_focus = focus_for_week(expected_phase, int(plan["week"]))
        if plan["calendar_phase"] != expected_phase["id"]:
            errors.append(f"plans: {week_value} calendar phase is out of sync")
        if (
            plan["theme_zh"] != expected_focus["title_zh"]
            or plan["theme_en"] != expected_focus["title_en"]
        ):
            errors.append(f"plans: {week_value} theme is out of sync with roadmap.yml")
        for task_id in plan.get("new_task_ids", []):
            task = progress.get("tasks", {}).get(task_id)
            if not task:
                errors.append(f"plans: {week_value} references missing task {task_id}")
            elif len(task.get("checkpoints", [])) != 3:
                errors.append(f"plans: new task {task_id} must have three checkpoints")
            elif [item["id"] for item in task["checkpoints"]] != [
                "briefing",
                "lab",
                "written_handoff",
            ]:
                errors.append(f"plans: new task {task_id} has invalid checkpoint ids")
        week_path = root / plan["path"]
        if not week_path.exists():
            errors.append(f"plans: weekly file is missing for {week_value}")
        else:
            content = week_path.read_text(encoding="utf-8")
            for term in FORBIDDEN_PLAN_TERMS:
                if term in content:
                    errors.append(f"plans: {week_value} contains forbidden time term {term}")
    return errors
