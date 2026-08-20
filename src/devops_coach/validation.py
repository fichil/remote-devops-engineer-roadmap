from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from devops_coach.planner import DAY_BUDGETS
from devops_coach.storage import load_json, load_yaml


def _validate(instance: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


def validate_project(root: Path) -> list[str]:
    errors: list[str] = []
    learner = load_yaml(root / "config" / "learner.yml")
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    progress = load_json(root / "state" / "progress.json")
    errors.extend(
        f"learner: {item}"
        for item in _validate(learner, root / "schemas" / "learner.schema.json")
    )
    errors.extend(
        f"roadmap: {item}"
        for item in _validate(roadmap, root / "schemas" / "roadmap.schema.json")
    )
    errors.extend(
        f"progress: {item}"
        for item in _validate(progress, root / "schemas" / "progress.schema.json")
    )

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

    schedule = learner.get("learner", {}).get("schedule", {})
    for name, budget in DAY_BUDGETS.items():
        configured = schedule.get(f"{name}_minutes")
        if configured != budget.total:
            errors.append(f"schedule: {name} must equal {budget.total} minutes")
        if budget.total and budget.english_minutes / budget.total < 0.25:
            errors.append(f"schedule: {name} English share is below 25%")
    return errors
