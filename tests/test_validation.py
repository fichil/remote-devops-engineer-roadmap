from pathlib import Path

from devops_coach.planner import ensure_week_plan
from devops_coach.storage import load_json, write_json
from devops_coach.validation import validate_project


def test_project_schemas_and_78_week_plan_are_valid(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W34")
    assert validate_project(project_copy) == []


def test_validation_detects_master_plan_drift(project_copy: Path) -> None:
    master = project_copy / "plans" / "master-plan.md"
    master.write_text(master.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")

    errors = validate_project(project_copy)

    assert any("not synchronized" in error for error in errors)


def test_validation_rejects_time_fields_in_active_state(project_copy: Path) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["adaptation"]["load_factor"] = 1.0
    write_json(state_path, state)

    errors = validate_project(project_copy)

    assert any("time-based field is forbidden" in error for error in errors)
