"""Private working progress and immutable, single-task publication transactions.

The tracked state is always the published view. No draft is implicitly trusted as
publication scope: snapshots still pass publication_scope's original validator.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, write_json

DIRECTORY = Path("private/devops-coach/drafts")
STATE = "state/progress.json"
MISSING = object()


class DraftError(ValueError):
    """Preserve evidence and stop when draft provenance cannot be verified."""


class Progress(dict):
    revision: str


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if result.returncode:
        raise DraftError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def enabled(root: Path) -> bool:
    return (root / DIRECTORY / "working.json").is_file()


def safe_path(root: Path, name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or path.parts[0] in {".git", "private"}:
        raise DraftError(f"Unsafe managed path: {name}")
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise DraftError(f"Managed path escapes repository: {name}")
    return target


@contextmanager
def lock(root: Path):
    directory = root / DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "write.lock").open("a+b") as handle:
        handle.seek(0)
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DraftError("Another draft writer/publication is active") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def seal(path: Path, payload: dict) -> None:
    atomic(path, encoded({"version": 1, "sha256": digest(encoded(payload)), "payload": payload}))


def unseal(path: Path) -> dict:
    try:
        envelope = load_json(path)
        payload = envelope["payload"]
        if envelope["version"] != 1 or envelope["sha256"] != digest(encoded(payload)):
            raise DraftError(f"Draft checksum/version mismatch: {path.name}")
        return payload
    except (KeyError, json.JSONDecodeError) as exc:
        raise DraftError(f"Invalid draft envelope: {path.name}") from exc


def expand(root: Path, base: dict, working: dict) -> dict:
    """Replay deterministic week definitions, never learner actions."""
    from devops_coach.planner import ensure_week_plan

    weeks = sorted(set(working.get("weekly_plans", {})) - set(base.get("weekly_plans", {})))
    if not weeks:
        return copy.deepcopy(base)
    with tempfile.TemporaryDirectory(prefix="coach-draft-") as temporary:
        scratch = Path(temporary)
        for name in ("config", "curriculum"):
            shutil.copytree(root / name, scratch / name)
        write_json(scratch / STATE, base)
        for week in weeks:
            ensure_week_plan(scratch, week)
        result = load_json(scratch / STATE)
    result["updated_at"] = base.get("updated_at")
    return result


def merge(base: Any, local: Any, remote: Any, field: str = "") -> Any:
    if local == base:
        return copy.deepcopy(remote) if remote is not MISSING else MISSING
    if remote == base or local == remote:
        return copy.deepcopy(local) if local is not MISSING else MISSING
    if field == "/updated_at":
        return max(str(local), str(remote))
    if all(isinstance(x, dict) for x in (base, local, remote)):
        result = {}
        for key in sorted(set(base) | set(local) | set(remote)):
            value = merge(
                base.get(key, MISSING),
                local.get(key, MISSING),
                remote.get(key, MISSING),
                field + "/" + str(key),
            )
            if value is not MISSING:
                result[key] = value
        return result
    if field.endswith("/checkpoints") and all(isinstance(v, list) for v in (base, local, remote)):
        maps = [{item["id"]: item for item in values} for values in (base, local, remote)]
        joined = merge(*maps, field + "/items")
        order = list(dict.fromkeys(item["id"] for item in local + remote))
        return [joined[key] for key in order if key in joined]
    if field == "/completion_log":

        def key(item):
            return (item["task_id"], item["date"], item.get("kind"))

        maps = [{key(v): v for v in values} for values in (base, local, remote)]
        joined = merge(*maps, field + "/entries")
        order = list(dict.fromkeys(key(item) for item in remote + local))
        order.sort(key=lambda value: (value[1], 0 if value[2] == "primary" else 1))
        return [joined[value] for value in order if value in joined]
    raise DraftError(f"Concurrent progress conflict at {field}")


def working_path(root: Path) -> Path:
    return root / DIRECTORY / "working.json"


def revision(root: Path) -> str:
    return digest(working_path(root).read_bytes() + (root / STATE).read_bytes())


def merge_progress(base: dict, local: dict, remote: dict) -> dict:
    """Recompute competing derived gates after merging their underlying evidence."""
    from devops_coach.planner import latest_gate_result

    local = copy.deepcopy(local)
    remote = copy.deepcopy(remote)
    derived = []
    for gate_id, original in base.get("phase_gates", {}).items():
        left = local.get("phase_gates", {}).get(gate_id)
        right = remote.get("phase_gates", {}).get(gate_id)
        # Equal summaries can represent distinct assessments; always check provenance.
        # Do not silently resolve manual edits, unknown metadata or evidence conflicts.
        if (
            left is not None and right is not None
            and left == latest_gate_result(local, gate_id)
            and right == latest_gate_result(remote, gate_id)
        ):
            local["phase_gates"][gate_id] = copy.deepcopy(original)
            remote["phase_gates"][gate_id] = copy.deepcopy(original)
            derived.append(gate_id)
    result = merge(base, local, remote)
    for gate_id in derived:
        gate = latest_gate_result(result, gate_id)
        if gate is None:
            raise DraftError(f"Cannot derive merged gate: {gate_id}")
        result["phase_gates"][gate_id] = gate
    return result


def load_progress(root: Path) -> dict:
    published = load_json(root / STATE)
    if not enabled(root):
        return published
    token = revision(root)
    payload = unseal(working_path(root))
    baseline = expand(root, payload["baseline"], payload["current"])
    remote = expand(root, published, payload["current"])
    result = Progress(merge_progress(baseline, payload["current"], remote))
    if token != revision(root):
        raise DraftError("Progress changed while reading; retry")
    result.revision = token
    return result


def plan_path(root: Path, relative: str | Path) -> Path:
    return root / DIRECTORY / "preview" / relative if enabled(root) else root / relative


def previews(root: Path, progress: dict) -> None:
    from devops_coach.planner import render_week_plan

    for week, plan in progress["weekly_plans"].items():
        path = plan_path(root, plan["path"])
        value = (render_week_plan(progress, week)).encode("utf-8")
        if not path.exists() or path.read_bytes() != value:
            atomic(path, value)


def artifacts(progress: dict) -> set[str]:
    result = set()
    for task in progress["tasks"].values():
        result.update(task.get("artifacts", []))
        for checkpoint in task.get("checkpoints", []):
            result.update(checkpoint.get("artifacts", []))
    for item in progress.get("completion_log", []):
        result.update(item.get("artifacts", []))
    return result


def head_file(root: Path, name: str, ref: str = "HEAD") -> bytes | None:
    result = subprocess.run(["git", "show", f"{ref}:{name}"], cwd=root, capture_output=True)
    if result.returncode:
        # Verify the ref separately so a Git failure cannot masquerade as absence.
        git(root, "rev-parse", "--verify", ref)
        tracked = git(root, "ls-tree", "-r", "--name-only", ref, "--", name).decode().strip()
        if tracked:
            raise DraftError(f"Cannot read tracked file: {name}")
        return None
    return result.stdout


def matches_ref(root: Path, name: str, ref: str, content: bytes | None) -> bool:
    stored = head_file(root, name, ref)
    if content is None or stored is None:
        return content is stored
    result = subprocess.run(
        ["git", "hash-object", f"--path={name}", "--stdin"],
        input=content,
        cwd=root,
        capture_output=True,
        check=True,
    )
    oid = git(root, "rev-parse", f"{ref}:{name}").strip()
    return result.stdout.strip() == oid


def pack(data: bytes | None) -> dict:
    return {
        "sha256": digest(data) if data is not None else None,
        "data": base64.b64encode(data).decode() if data is not None else None,
    }


def unpack(value: dict) -> bytes | None:
    data = base64.b64decode(value["data"], validate=True) if value["data"] is not None else None
    if value["sha256"] != (digest(data) if data is not None else None):
        raise DraftError("Artifact checksum mismatch")
    return data


def artifact_available(root: Path, name: str) -> bool:
    if not enabled(root):
        return False
    record = unseal(working_path(root)).get("artifacts", {}).get(name)
    return record is not None and unpack(record) is not None


def save_progress(root: Path, progress: dict, *, artifact_paths: Sequence[str] = ()) -> None:
    if not enabled(root):
        write_json(root / STATE, progress)
        return
    with lock(root):
        if getattr(progress, "revision", None) != revision(root):
            raise DraftError("Concurrent draft modification; reload before recording")
        payload = unseal(working_path(root))
        files = payload.get("artifacts", {})
        for name in sorted(artifact_paths):
            path = safe_path(root, name)
            if path.is_file():
                content = path.read_bytes()
                base = head_file(root, name)
                if not matches_ref(root, name, "HEAD", content):
                    if name in files and unpack(files[name]) != content:
                        # A learner may revise a registered artifact; keep old bytes in backups.
                        seal(root / DIRECTORY / "history" / (digest(content) + ".json"), files)
                    prior = files.get(name)
                    files[name] = {
                        **pack(content),
                        "baseline": prior["baseline"] if prior else pack(base),
                    }
        payload = {
            "baseline": load_json(root / STATE),
            "current": dict(progress),
            "artifacts": files,
            "baseline_commit": git(root, "rev-parse", "HEAD").decode().strip(),
        }
        seal(working_path(root), payload)
        # Artifact bytes remain on disk until publication/import parks them safely.
        progress.revision = revision(root)


def dirty_paths(root: Path) -> set[str]:
    records = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode("utf-8")
    paths = set()
    for record in records.split("\0"):
        if not record:
            continue
        if len(record) < 4 or any(c in record[:2] for c in "RCU"):
            raise DraftError("Renamed, conflicted or copied paths require manual review")
        paths.add(record[3:].replace("\\", "/"))
    return paths


def restore_files(root: Path, files: dict, destination: str) -> None:
    """Resumable compare-and-swap, one explicit file at a time."""
    for name, record in files.items():
        path = safe_path(root, name)
        actual = path.read_bytes() if path.exists() else None
        old, new = unpack(record["before"]), unpack(record[destination])
        if actual == new:
            continue
        if actual != old:
            raise DraftError(f"Concurrent file modification: {name}")
        if new is None:
            if path.exists():
                path.unlink()
        else:
            atomic(path, new)


def import_drafts(root: Path, *, apply: bool) -> dict:
    from devops_coach.planner import render_week_plan
    from devops_coach.publication_scope import task_definition

    root = root.resolve()
    journal = root / DIRECTORY / "import.json"
    if journal.exists():
        prior = unseal(journal)
        if prior.get("complete"):
            return {"status": "already_imported", "tasks": prior["tasks"], "paths": []}
        if apply:
            with lock(root):
                if not enabled(root):
                    seal(working_path(root), prior["working"])
                restore_files(root, prior["files"], "published")
                prior["complete"] = True
                seal(journal, prior)
                previews(root, load_progress(root))
        return {
            "status": "imported" if apply else "dry_run",
            "tasks": prior["tasks"],
            "paths": sorted(prior["files"]),
            "resumed": True,
        }
    if enabled(root):
        return {"status": "already_enabled", "tasks": [], "paths": []}
    if git(root, "diff", "--cached", "--name-only").strip():
        raise DraftError("Staged changes require manual review before draft import")
    baseline = json.loads(git(root, "show", "HEAD:" + STATE))
    current = load_json(root / STATE)
    expected = expand(root, baseline, current)
    changed = []
    for name, task in current["tasks"].items():
        original = expected["tasks"].get(name)
        if original is None or task_definition(task) != task_definition(original):
            raise DraftError(f"Unrelated task definition changes: {name}")
        if task != original:
            changed.append(name)
    if set(current["tasks"]) != set(expected["tasks"]):
        raise DraftError("Unrelated task removal")
    mutable = {"tasks", "completion_log", "updated_at", "current_week", "current_phase", "blockers"}
    for key in set(expected) | set(current):
        if key not in mutable and expected.get(key) != current.get(key):
            raise DraftError(f"Unrelated progress field: {key}")
    if current["completion_log"][: len(baseline["completion_log"])] != baseline["completion_log"]:
        raise DraftError("Historical completion log changed")
    paths = dirty_paths(root)
    plans = {p["path"]: week for week, p in current["weekly_plans"].items()}
    allowed = {STATE} | set(plans) | artifacts(current)
    if paths - allowed:
        raise DraftError("Unrelated paths: " + ", ".join(sorted(paths - allowed)))
    for name in paths & set(plans):
        if safe_path(root, name).read_text(encoding="utf-8") != render_week_plan(
            current, plans[name]
        ):
            raise DraftError(f"Weekly plan is not generated from current progress: {name}")
    files = {
        name: {
            "before": pack(safe_path(root, name).read_bytes()),
            "published": pack(head_file(root, name)),
        }
        for name in sorted(paths)
    }
    result = {
        "status": "imported" if apply else "dry_run",
        "tasks": sorted(changed),
        "paths": sorted(paths),
        "resumed": False,
    }
    if not apply:
        return result
    with lock(root):
        if dirty_paths(root) != paths:
            raise DraftError("Worktree changed since import inspection")
        for name, record in files.items():
            if safe_path(root, name).read_bytes() != unpack(record["before"]):
                raise DraftError(f"File changed before backup: {name}")
        payload = {
            "baseline": baseline,
            "current": current,
            "baseline_commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "artifacts": {
                name: {**files[name]["before"], "baseline": files[name]["published"]}
                for name in paths & artifacts(current)
            },
        }
        # Backup and verify the transaction before changing any public file.
        seal(journal, {"files": files, "tasks": sorted(changed), "working": payload})
        restored = unseal(journal)
        seal(working_path(root), restored["working"])
        restore_files(root, restored["files"], "published")
        restored["complete"] = True
        seal(journal, restored)
        previews(root, load_progress(root))
    return result


def snapshot_path(root: Path, key: str) -> Path:
    return root / DIRECTORY / "publications" / (digest(key.encode()) + ".json")


def candidate(root: Path, progress: dict, completion: dict) -> dict:
    from devops_coach.planner import update_task_gate
    from devops_coach.publication_scope import validate_state_scope

    baseline = json.loads(git(root, "show", "HEAD:" + STATE))
    target = date.fromisoformat(completion["date"])
    week = target.strftime("%G-W%V")
    seed = {"weekly_plans": {week: progress["weekly_plans"][week]}} if target.weekday() < 5 else {}
    result = expand(root, baseline, seed)
    if target.weekday() < 5:
        plan = result["weekly_plans"][week]
        result["current_week"] = plan["week"]
        result["current_phase"] = plan["execution_phase"]
    tid = completion["task_id"]
    task = copy.deepcopy(progress["tasks"][tid])
    # Weekly-review guidance stays private, including after publication cleanup.
    # Retain the published value; every other definition change must still fail scope checks.
    original = result["tasks"][tid]
    if "coaching_action" in original:
        task["coaching_action"] = copy.deepcopy(original["coaching_action"])
    else:
        task.pop("coaching_action", None)
    result["tasks"][tid] = task
    result["completion_log"].append(copy.deepcopy(completion))
    update_task_gate(result, result["tasks"][completion["task_id"]])
    result["updated_at"] = progress["updated_at"]
    validate_state_scope(root, baseline, result, completion["task_id"], target, completion)
    return result


def prepare_snapshot(root: Path, key: str, completion: dict, *, apply: bool) -> dict:
    from devops_coach.planner import render_week_plan

    frozen = snapshot_path(root, key)
    if frozen.exists():
        transaction = unseal(frozen)
    else:
        progress = load_progress(root)
        snapshot = candidate(root, progress, completion)
        payload = unseal(working_path(root))
        task = snapshot["tasks"][completion["task_id"]]
        names = set(task.get("artifacts", [])) | set(completion.get("artifacts", []))
        for checkpoint in task.get("checkpoints", []):
            names.update(checkpoint.get("artifacts", []))
        before = json.loads(git(root, "show", "HEAD:" + STATE))
        output = {STATE: encoded(snapshot)}
        for week, plan in snapshot["weekly_plans"].items():
            text = (render_week_plan(snapshot, week)).encode()
            if week not in before["weekly_plans"] or text != head_file(root, plan["path"]):
                output[plan["path"]] = text
        for name in names:
            path = safe_path(root, name)
            if name in payload.get("artifacts", {}):
                record = payload["artifacts"][name]
                content = unpack(record)
                if not any(
                    matches_ref(root, name, "HEAD", value)
                    for value in (unpack(record["baseline"]), content)
                ):
                    raise DraftError(f"Concurrent artifact conflict: {name}")
                owners = [
                    tid
                    for tid, item in progress["tasks"].items()
                    if name in artifacts({"tasks": {tid: item}})
                ]
                if len(owners) > 1:
                    raise DraftError(f"Shared draft artifact requires review: {name}")
                if path.exists() and path.read_bytes() not in (content, head_file(root, name)):
                    raise DraftError(f"Artifact changed since recording: {name}")
            else:
                content = path.read_bytes() if path.exists() else None
            if content is None:
                raise DraftError(f"Missing evidence artifact: {name}")
            output[name] = content
        dirty = dirty_paths(root)
        registered = payload.get("artifacts", {})
        if dirty - set(registered):
            raise DraftError(
                "Unrelated worktree changes: " + ", ".join(sorted(dirty - set(registered)))
            )
        for name in dirty:
            if safe_path(root, name).read_bytes() != unpack(registered[name]):
                raise DraftError(f"Unrecorded artifact change: {name}")
        # Park other registered drafts, not arbitrary user files.
        all_names = set(output) | dirty
        files = {}
        for name in sorted(all_names):
            path = safe_path(root, name)
            files[name] = {
                "before": pack(path.read_bytes() if path.exists() else None),
                "snapshot": pack(output.get(name, head_file(root, name))),
            }
        transaction = {
            "key": key,
            "completion": completion,
            "progress": snapshot,
            "baseline_commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "files": files,
            "artifacts": sorted(names),
        }
    if apply:
        if not frozen.exists():
            seal(frozen, transaction)
        # Never re-install a frozen snapshot on an unrelated HEAD.
        head = git(root, "rev-parse", "HEAD").decode().strip()
        if head == transaction["baseline_commit"]:
            unexpected = dirty_paths(root) - set(transaction["files"])
            if unexpected:
                raise DraftError("Unrelated worktree changes: " + ", ".join(sorted(unexpected)))
            restore_files(root, transaction["files"], "snapshot")
        else:
            for name, record in transaction["files"].items():
                path = safe_path(root, name)
                content = path.read_bytes() if path.exists() else None
                if content != unpack(record["snapshot"]):
                    raise DraftError(f"Frozen publication file changed: {name}")
            actual = load_json(root / STATE)
            if actual != transaction["progress"]:
                raise DraftError("Frozen publication differs from current HEAD/state")
    return transaction


def finish_snapshot(root: Path, key: str) -> None:
    transaction = unseal(snapshot_path(root, key))
    published = load_json(root / STATE)
    tid = transaction["completion"]["task_id"]
    if (
        published["tasks"].get(tid) != transaction["progress"]["tasks"][tid]
        or transaction["completion"] not in published["completion_log"]
    ):
        raise DraftError("Published task does not match frozen snapshot")
    effective = load_progress(root)
    payload = unseal(working_path(root))
    remaining = {
        name: record
        for name, record in payload.get("artifacts", {}).items()
        if name not in transaction["artifacts"]
    }
    seal(
        working_path(root),
        {
            "baseline": published,
            "current": dict(effective),
            "baseline_commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "artifacts": remaining,
        },
    )
    previews(root, effective)
    transaction["finalized"] = True
    seal(snapshot_path(root, key), transaction)
