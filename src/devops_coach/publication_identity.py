from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

LEDGER_PATH = Path("private") / "devops-coach" / "publication-ledger.json"
LEDGER_SCHEMA_VERSION = 2
PUBLICATION_KINDS = ("primary", "carryover")


def publication_key(target: date, kind: str, task_id: str | None = None) -> str:
    if kind not in PUBLICATION_KINDS:
        raise ValueError(f"Unknown publication kind: {kind}")
    if kind == "primary":
        return f"{target.isoformat()}:primary"
    if not task_id:
        raise ValueError("A carryover publication requires a task id")
    return f"{target.isoformat()}:carryover:{task_id}"


def legacy_publication_key(target: date, kind: str) -> str:
    if kind not in PUBLICATION_KINDS:
        raise ValueError(f"Unknown publication kind: {kind}")
    return f"{target.isoformat()}:{kind}"


def publication_branch_token(task_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", task_id.lower()).strip("-")[:48].rstrip("-")
    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'task'}-{digest}"


def publication_branch(
    policy: dict[str, Any], target: date, kind: str, task_id: str | None = None
) -> str:
    if kind == "primary":
        return f"{policy['branch_prefix']}/{target.isoformat()}"
    if kind != "carryover":
        raise ValueError(f"Unknown publication kind: {kind}")
    if not task_id:
        raise ValueError("A carryover publication requires a task id")
    token = publication_branch_token(task_id)
    return f"{policy['branch_prefix']}/{target.isoformat()}-carryover-{token}"


def publication_subject(target: date, kind: str, task_id: str | None = None) -> str:
    if kind == "primary":
        return f"learn: complete {target.isoformat()}"
    if kind != "carryover":
        raise ValueError(f"Unknown publication kind: {kind}")
    if not task_id:
        raise ValueError("A carryover publication requires a task id")
    return f"learn: complete {target.isoformat()} carryover {task_id}"


def load_publication_ledger(root: Path) -> dict[str, Any]:
    path = root / LEDGER_PATH
    if not path.exists():
        return {"schema_version": LEDGER_SCHEMA_VERSION, "publications": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("publications"), dict):
        raise ValueError(f"Invalid publication ledger: {LEDGER_PATH.as_posix()}")
    if value.get("schema_version") not in {1, LEDGER_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported publication ledger schema: {value.get('schema_version')}")
    return value


def resolve_publication_entry(
    ledger: dict[str, Any], target: date, kind: str, task_id: str
) -> tuple[str, dict[str, Any]]:
    key = publication_key(target, kind, task_id if kind == "carryover" else None)
    entry = ledger["publications"].get(key)
    if isinstance(entry, dict):
        return key, entry
    if kind == "carryover":
        legacy_key = legacy_publication_key(target, kind)
        legacy = ledger["publications"].get(legacy_key)
        if isinstance(legacy, dict) and legacy.get("task_id") == task_id:
            return legacy_key, legacy
    return key, {}


def publication_is_complete(root: Path, target: date, kind: str, task_id: str) -> bool:
    ledger = load_publication_ledger(root)
    _, entry = resolve_publication_entry(ledger, target, kind, task_id)
    return entry.get("status") == "complete"
