from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from devops_coach.lab import (
    prepare_friday_reproduction,
    prepare_week_lab,
    week_lab_status,
)
from devops_coach.planner import ensure_week_plan


def _outside_private_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).parts[0] != "private"
    }


def test_week_lab_is_local_continuous_and_idempotent(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W36")
    outside_before = _outside_private_snapshot(project_copy)

    first = prepare_week_lab(project_copy, "2026-W36")
    manifest_path = Path(first["lab_root"]) / "manifest.json"
    before = manifest_path.read_bytes()
    second = prepare_week_lab(project_copy, "2026-W36")

    assert first["created"] is True
    assert second["created"] is False
    assert first["local_remote"].startswith(str(project_copy / "private" / "labs"))
    assert first["worktree"].startswith(str(project_copy / "private" / "labs"))
    assert first["worktree_status"] == "## main...origin/main"
    assert manifest_path.read_bytes() == before
    assert json.loads(before)["local_only"] is True
    assert week_lab_status(project_copy, "2026-W36")["status"] == "ready"
    assert _outside_private_snapshot(project_copy) == outside_before


def test_friday_reproduction_uses_fresh_clone(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W36")
    outside_before = _outside_private_snapshot(project_copy)

    result = prepare_friday_reproduction(project_copy, "2026-W36", date(2026, 9, 4))
    repeated = prepare_friday_reproduction(project_copy, "2026-W36", date(2026, 9, 4))

    reproduction = Path(result["friday_reproduction"])
    assert result["reproduction_created"] is True
    assert repeated["reproduction_created"] is False
    assert reproduction.is_dir()
    assert reproduction != Path(result["worktree"])
    assert _outside_private_snapshot(project_copy) == outside_before


def test_friday_reproduction_rejects_non_friday(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W36")

    with pytest.raises(ValueError, match="only created on Friday"):
        prepare_friday_reproduction(project_copy, "2026-W36", date(2026, 8, 31))


def test_week_lab_refuses_unrecognized_existing_directory(project_copy: Path) -> None:
    ensure_week_plan(project_copy, "2026-W36")
    lab_root = project_copy / "private" / "labs" / "2026-W36"
    lab_root.mkdir(parents=True)
    (lab_root / "unknown.txt").write_text("do not overwrite\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        prepare_week_lab(project_copy, "2026-W36")


def test_gate_remediation_lab_uses_concrete_prior_phase_blueprint(
    project_copy: Path,
) -> None:
    ensure_week_plan(project_copy, "2026-W44")

    result = prepare_week_lab(project_copy, "2026-W44")

    assert result["curriculum_week"] == 13
    assert result["project_id"] == "foundation-gate-incident"
    assert Path(result["lab_root"]).name == "2026-W44"
