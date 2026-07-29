from pathlib import Path

from devops_coach.validation import validate_project


def test_project_schemas_and_78_week_coverage(project_copy: Path) -> None:
    assert validate_project(project_copy) == []
