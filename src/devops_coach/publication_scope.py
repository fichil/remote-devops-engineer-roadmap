"""Read-only, task-level validation of a learning publication snapshot."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from devops_coach.planner import ensure_week_plan, render_week_plan
from devops_coach.storage import load_json, write_json


def validate_state_scope(
    root: Path,
    before: dict[str, Any],
    after: dict[str, Any],
    task_id: str,
    target: date,
    completion: dict[str, Any],
) -> None:
    expected = copy.deepcopy(before)
    week = target.strftime("%G-W%V")
    if target.weekday() < 5 and week not in expected.get("weekly_plans", {}):
        # Replay only deterministic initialization, never learning actions.
        with tempfile.TemporaryDirectory(prefix="devops-publication-") as directory:
            scratch = Path(directory)
            for name in ("config", "curriculum"):
                shutil.copytree(root / name, scratch / name)
            write_json(scratch / "state/progress.json", expected)
            ensure_week_plan(scratch, week)
            expected = load_json(scratch / "state/progress.json")
    if target.weekday() < 5:
        plan = expected["weekly_plans"][week]
        for name, value in (
            ("current_week", plan["week"]),
            ("current_phase", plan["execution_phase"]),
        ):
            if after.get(name) != before.get(name):
                expected[name] = value
    original = expected["tasks"].get(task_id)
    if original is None:
        raise ValueError(f"Unrelated task initialization: {task_id}")
    candidate = after["tasks"][task_id]
    mutable = {
        "status",
        "score",
        "evidence",
        "artifacts",
        "completed_on",
        "next_review",
        "carryover_activated_on",
        "carryover_publication_date",
    }
    checkpoint_mutable = mutable | {"evidence_details", "hint_level_used", "independent"}

    def definition(task: dict[str, Any]) -> dict[str, Any]:
        result = {key: value for key, value in task.items() if key not in mutable}
        result["checkpoints"] = [
            {key: value for key, value in item.items() if key not in checkpoint_mutable}
            for item in task.get("checkpoints", [])
        ]
        return result

    if definition(original) != definition(candidate):
        raise ValueError(f"Unrelated task definition changes: {task_id}")
    expected["tasks"][task_id] = candidate
    expected.setdefault("completion_log", []).append(completion)
    expected["updated_at"] = after.get("updated_at")
    for key in sorted(set(expected) | set(after)):
        if expected.get(key) == after.get(key):
            continue
        if key == "tasks":
            differing = sorted(
                name
                for name in set(expected[key]) | set(after[key])
                if expected[key].get(name) != after[key].get(name)
            )
            raise ValueError("Unrelated task changes: " + ", ".join(differing))
        raise ValueError(f"Unrelated progress field: {key}")


def validate_snapshot(
    root: Path,
    runner: Any,
    baseline: str,
    revision: str | None,
    progress: dict[str, Any],
    completion: dict[str, Any],
    paths: set[str],
) -> None:
    def read(path: str, ref: str | None) -> str:
        if ref is None:
            return (root / path).read_text(encoding="utf-8")
        return runner.run(["git", "show", f"{ref}:{path}"]).stdout

    before = json.loads(read("state/progress.json", baseline))
    validate_state_scope(
        root,
        before,
        progress,
        completion["task_id"],
        date.fromisoformat(completion["date"]),
        completion,
    )
    task = progress["tasks"][completion["task_id"]]
    artifacts = set(task.get("artifacts", [])) | set(completion.get("artifacts", []))
    for checkpoint in task.get("checkpoints", []):
        artifacts.update(checkpoint.get("artifacts", []))
    plans = {item["path"]: week for week, item in progress["weekly_plans"].items()}
    for path in sorted(paths):
        if path == "state/progress.json":
            continue
        if path in plans:
            if read(path, revision) != render_week_plan(progress, plans[path]):
                raise ValueError(f"Weekly plan is not synchronized: {path}")
        elif path not in artifacts:
            raise ValueError(f"Unrelated or unregistered target-task path: {path}")
