from pathlib import Path

from devops_coach.planner import ensure_week_plan
from devops_coach.storage import load_json, write_json
from devops_coach.validation import validate_project


def test_project_schemas_and_78_week_plan_are_valid(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W34")
    assert validate_project(project_copy) == []


def test_matching_finite_carryover_limit_remains_valid(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W34")
    config_path = project_copy / "config" / "learner.yml"
    content = config_path.read_text(encoding="utf-8")
    content = content.replace("optional_carryover_missions: null", "optional_carryover_missions: 2")
    content = content.replace(
        "optional_carryover_per_workday: null", "optional_carryover_per_workday: 2"
    )
    config_path.write_text(content, encoding="utf-8")

    assert validate_project(project_copy) == []

    config_path.write_text(
        content.replace(
            "optional_carryover_per_workday: 2", "optional_carryover_per_workday: 1"
        ),
        encoding="utf-8",
    )
    errors = validate_project(project_copy)
    assert any("schedule and publication limits must match" in error for error in errors)


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


def test_validation_enforces_cognitive_assessment_invariants(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W35")
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    task = state["tasks"]["2026-W35-01-mission"]
    task["checkpoints"][0]["score"] = 4
    task["checkpoints"][2].update(
        {
            "status": "done",
            "score": 5,
            "evidence": "unstructured copied result",
            "hint_level_used": 2,
            "independent": False,
        }
    )
    write_json(state_path, state)

    errors = validate_project(project_copy)

    assert any("formative checkpoint" in error and "cannot be scored" in error for error in errors)
    assert any(
        "summative checkpoint" in error and "structured evidence" in error
        for error in errors
    )
    assert any("requires independent work with hint level 0" in error for error in errors)
