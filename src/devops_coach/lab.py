from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from devops_coach.storage import load_json, load_yaml, write_json, write_text

LAB_PROTOCOL_VERSION = 1
PLACEHOLDER_NAME = "DevOps Training Lab"
PLACEHOLDER_EMAIL = "devops-lab.local"


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Local Git lab command failed ({result.returncode}): {detail}")
    return result.stdout.strip()


def _week_blueprint(root: Path, week_value: str) -> tuple[int, dict[str, Any]]:
    progress = load_json(root / "state" / "progress.json")
    plan = progress.get("weekly_plans", {}).get(week_value)
    if not plan:
        raise ValueError(f"No weekly plan exists for {week_value}")
    task_ids = list(plan.get("new_task_ids", []))
    missing = [task_id for task_id in task_ids if task_id not in progress.get("tasks", {})]
    if missing:
        raise ValueError(f"Weekly plan {week_value} references missing tasks: {missing}")
    curriculum_weeks = {
        int(progress["tasks"][task_id]["curriculum_week"]) for task_id in task_ids
    }
    if len(curriculum_weeks) != 1:
        raise ValueError(
            f"Weekly plan {week_value} must use one concrete training blueprint"
        )
    curriculum_week = curriculum_weeks.pop()
    roadmap = load_yaml(root / "curriculum" / "roadmap.yml")
    try:
        blueprint = next(
            item
            for item in roadmap.get("training_blueprints", [])
            if int(item["week"]) == curriculum_week
        )
    except StopIteration as exc:
        raise ValueError(
            f"No cognitive-apprenticeship blueprint exists for curriculum week {curriculum_week}"
        ) from exc
    project_ids = {
        str(progress["tasks"][task_id].get("weekly_project_id")) for task_id in task_ids
    }
    if project_ids != {str(blueprint["project"]["id"])}:
        raise ValueError(
            f"Weekly plan {week_value} tasks do not match blueprint week {curriculum_week}"
        )
    return curriculum_week, blueprint


def _safe_seed_path(lab_seed: Path, raw_path: str) -> Path:
    posix_path = PurePosixPath(raw_path)
    if posix_path.is_absolute() or not posix_path.parts or ".." in posix_path.parts:
        raise ValueError(f"Unsafe lab seed path: {raw_path}")
    if posix_path.parts[0] in {".git", "private"}:
        raise ValueError(f"Reserved lab seed path: {raw_path}")
    candidate = lab_seed.joinpath(*posix_path.parts).resolve()
    try:
        candidate.relative_to(lab_seed.resolve())
    except ValueError as exc:
        raise ValueError(f"Lab seed path escaped the seed directory: {raw_path}") from exc
    return candidate


def _lab_root(root: Path, week_value: str) -> Path:
    resolved_root = root.resolve()
    private_labs = (resolved_root / "private" / "labs").resolve()
    candidate = (private_labs / week_value).resolve()
    try:
        candidate.relative_to(private_labs)
    except ValueError as exc:
        raise ValueError(f"Lab path escaped private/labs: {week_value}") from exc
    return candidate


def _manifest_result(lab_root: Path, manifest: dict[str, Any], *, created: bool) -> dict[str, Any]:
    work = lab_root / "work"
    origin = lab_root / "origin.git"
    reproduction = lab_root / "friday-reproduction"
    return {
        "status": "ready",
        "created": created,
        "week": manifest["week"],
        "curriculum_week": manifest["curriculum_week"],
        "project_id": manifest["project_id"],
        "lab_root": str(lab_root),
        "worktree": str(work),
        "local_remote": str(origin),
        "friday_reproduction": str(reproduction) if reproduction.exists() else None,
        "worktree_status": _run_git(["-C", str(work), "status", "--short", "--branch"]),
    }


def prepare_week_lab(root: Path, week_value: str) -> dict[str, Any]:
    """Create or resume one deterministic, local-only weekly training project."""
    curriculum_week, blueprint = _week_blueprint(root, week_value)
    project = blueprint["project"]
    lab_root = _lab_root(root, week_value)
    manifest_path = lab_root / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        expected = {
            "protocol_version": LAB_PROTOCOL_VERSION,
            "week": week_value,
            "curriculum_week": curriculum_week,
            "project_id": str(project["id"]),
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"Existing lab manifest does not match {week_value}")
        if not (lab_root / "origin.git").is_dir() or not (lab_root / "work" / ".git").is_dir():
            raise RuntimeError(f"Existing lab is incomplete: {lab_root}")
        return _manifest_result(lab_root, manifest, created=False)
    if lab_root.exists() and any(lab_root.iterdir()):
        raise RuntimeError(f"Refusing to overwrite an unrecognized lab directory: {lab_root}")

    lab_root.mkdir(parents=True, exist_ok=True)
    origin = lab_root / "origin.git"
    seed = lab_root / "seed"
    work = lab_root / "work"
    _run_git(["init", "--bare", "--initial-branch=main", str(origin)])
    _run_git(["init", "--initial-branch=main", str(seed)])
    _run_git(["-C", str(seed), "config", "user.name", PLACEHOLDER_NAME])
    _run_git(["-C", str(seed), "config", "user.email", PLACEHOLDER_EMAIL])

    seed_files = project.get("seed_files", {})
    if not isinstance(seed_files, dict) or not seed_files:
        raise ValueError(f"Blueprint {curriculum_week} must define non-empty seed_files")
    normalized_paths: list[str] = []
    for raw_path, content in seed_files.items():
        target = _safe_seed_path(seed, str(raw_path))
        write_text(target, str(content))
        normalized_paths.append(PurePosixPath(str(raw_path)).as_posix())
    for relative_path in sorted(normalized_paths):
        _run_git(["-C", str(seed), "add", "--", relative_path])
    _run_git(["-C", str(seed), "commit", "-m", "Seed weekly training project"])
    _run_git(["-C", str(seed), "remote", "add", "origin", str(origin)])
    _run_git(["-C", str(seed), "push", "-u", "origin", "main"])
    _run_git(["clone", str(origin), str(work)])
    _run_git(["-C", str(work), "config", "user.name", PLACEHOLDER_NAME])
    _run_git(["-C", str(work), "config", "user.email", PLACEHOLDER_EMAIL])

    manifest = {
        "protocol_version": LAB_PROTOCOL_VERSION,
        "week": week_value,
        "curriculum_week": curriculum_week,
        "project_id": str(project["id"]),
        "goal": str(project["goal"]),
        "environment": str(project["environment"]),
        "seed_files": sorted(normalized_paths),
        "local_only": True,
    }
    write_json(manifest_path, manifest)
    return _manifest_result(lab_root, manifest, created=True)


def week_lab_status(root: Path, week_value: str) -> dict[str, Any]:
    lab_root = _lab_root(root, week_value)
    manifest_path = lab_root / "manifest.json"
    if not manifest_path.exists():
        return {"status": "missing", "week": week_value, "lab_root": str(lab_root)}
    return _manifest_result(lab_root, load_json(manifest_path), created=False)


def prepare_friday_reproduction(
    root: Path, week_value: str, target: date | None = None
) -> dict[str, Any]:
    """Create a fresh Friday clone without resetting or deleting prior learner work."""
    base = target or date.today()
    if base.weekday() != 4:
        raise ValueError("A fresh weekly reproduction is only created on Friday")
    prepared = prepare_week_lab(root, week_value)
    lab_root = Path(prepared["lab_root"])
    reproduction = lab_root / "friday-reproduction"
    if reproduction.exists():
        if not (reproduction / ".git").is_dir():
            raise RuntimeError(f"Refusing to overwrite an incomplete reproduction: {reproduction}")
        prepared["friday_reproduction"] = str(reproduction)
        prepared["reproduction_created"] = False
        return prepared
    _run_git(["clone", str(lab_root / "origin.git"), str(reproduction)])
    _run_git(["-C", str(reproduction), "config", "user.name", PLACEHOLDER_NAME])
    _run_git(["-C", str(reproduction), "config", "user.email", PLACEHOLDER_EMAIL])
    prepared["friday_reproduction"] = str(reproduction)
    prepared["reproduction_created"] = True
    return prepared
