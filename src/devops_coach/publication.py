from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from devops_coach.planner import task_has_complete_evidence
from devops_coach.storage import load_json, load_yaml

LEDGER_PATH = Path("private") / "devops-coach" / "publication-ledger.json"
PUBLICATION_KINDS = ("primary", "carryover")


class PublicationError(RuntimeError):
    """A fail-closed publication error that leaves learner evidence intact."""


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def __init__(self, root: Path):
        self.root = root

    def run(self, args: list[str], *, check: bool = True) -> CommandResult:
        completed = subprocess.run(
            args,
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result = CommandResult(
            tuple(args), completed.returncode, completed.stdout, completed.stderr
        )
        if check and completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            if len(detail) > 2000:
                detail = detail[-2000:]
            command = " ".join(args)
            raise PublicationError(
                f"Command failed with exit {completed.returncode}: {command}"
                + (f"\n{detail}" if detail else "")
            )
        return result


def _policy(root: Path) -> dict[str, Any]:
    learner = load_yaml(root / "config" / "learner.yml")["learner"]
    policy = learner.get("publication")
    if not isinstance(policy, dict):
        raise PublicationError("Automatic publication is not configured")
    if policy.get("mode") != "auto_after_task_completion":
        raise PublicationError("Automatic publication mode is disabled")
    if policy.get("integration") != "ready_pr_squash":
        raise PublicationError("Only Ready PR squash integration is supported")
    return policy


def publication_key(target: date, kind: str) -> str:
    if kind not in PUBLICATION_KINDS:
        raise PublicationError(f"Unknown publication kind: {kind}")
    return f"{target.isoformat()}:{kind}"


def publication_branch(policy: dict[str, Any], target: date, kind: str) -> str:
    suffix = "" if kind == "primary" else "-carryover"
    return f"{policy['branch_prefix']}/{target.isoformat()}{suffix}"


def publication_subject(target: date, kind: str) -> str:
    suffix = "" if kind == "primary" else " carryover"
    return f"learn: complete {target.isoformat()}{suffix}"


def _ledger_file(root: Path) -> Path:
    return root / LEDGER_PATH


def load_publication_ledger(root: Path) -> dict[str, Any]:
    path = _ledger_file(root)
    if not path.exists():
        return {"schema_version": 1, "publications": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("publications"), dict):
        raise PublicationError(f"Invalid publication ledger: {LEDGER_PATH.as_posix()}")
    return value


def _write_ledger(root: Path, ledger: dict[str, Any]) -> None:
    path = _ledger_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _update_ledger(root: Path, key: str, **values: Any) -> dict[str, Any]:
    ledger = load_publication_ledger(root)
    entry = dict(ledger["publications"].get(key, {}))
    entry.update(values)
    ledger["publications"][key] = entry
    _write_ledger(root, ledger)
    return entry


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise PublicationError(f"Unsafe repository path in structured state: {value}")
    if path.parts[0] in {".git", "private"}:
        raise PublicationError(f"Private or Git metadata cannot be published: {value}")
    return path.as_posix()


def _eligible_completion(
    progress: dict[str, Any], target: date, kind: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if target.weekday() >= 5:
        raise PublicationError("Routine learning publications are forbidden on weekends")
    matches = [
        item
        for item in progress.get("completion_log", [])
        if item.get("date") == target.isoformat() and item.get("kind") == kind
    ]
    if len(matches) != 1:
        raise PublicationError(
            f"Expected exactly one {kind} completion for {target.isoformat()}, found {len(matches)}"
        )
    completion = matches[0]
    task = progress.get("tasks", {}).get(completion.get("task_id"))
    if not task or not task_has_complete_evidence(task):
        raise PublicationError(
            "Publication requires a complete task with evidence at every checkpoint"
        )
    scheduled_for = task.get("scheduled_for") or task.get("created_on")
    if kind == "primary" and scheduled_for != target.isoformat():
        raise PublicationError("A primary publication must be the task scheduled for that workday")
    if kind == "carryover":
        primary = [
            item
            for item in progress.get("completion_log", [])
            if item.get("date") == target.isoformat() and item.get("kind") == "primary"
        ]
        if len(primary) != 1:
            raise PublicationError("A carryover publication requires that day's completed primary")
        if scheduled_for >= target.isoformat():
            raise PublicationError(
                "A carryover must have been scheduled before the publication date"
            )
    return completion, task


def _allowed_learning_paths(progress: dict[str, Any]) -> set[str]:
    allowed = {"state/progress.json"}
    for plan in progress.get("weekly_plans", {}).values():
        path = plan.get("path")
        if path:
            allowed.add(_safe_relative(str(path)))
    for task in progress.get("tasks", {}).values():
        for artifact in task.get("artifacts", []):
            allowed.add(_safe_relative(str(artifact)))
        for checkpoint in task.get("checkpoints", []):
            for artifact in checkpoint.get("artifacts", []):
                allowed.add(_safe_relative(str(artifact)))
    for item in progress.get("completion_log", []):
        for artifact in item.get("artifacts", []):
            allowed.add(_safe_relative(str(artifact)))
    return allowed


def _dirty_paths(runner: CommandRunner) -> set[str]:
    result = runner.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    dirty: set[str] = set()
    records = result.stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise PublicationError("Could not parse Git status output")
        status = record[:2]
        if "R" in status or "C" in status:
            raise PublicationError("Renamed or copied paths require manual publication review")
        dirty.add(record[3:].replace("\\", "/"))
    return dirty


def inspect_publication(
    root: Path,
    target: date,
    kind: str,
    *,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    policy = _policy(root)
    progress = load_json(root / "state" / "progress.json")
    completion, task = _eligible_completion(progress, target, kind)
    active_runner = runner or CommandRunner(root)
    dirty = _dirty_paths(active_runner)
    allowed = _allowed_learning_paths(progress)
    unknown = sorted(dirty - allowed)
    if unknown:
        raise PublicationError(
            "Unrelated or unregistered worktree changes block publication: "
            + ", ".join(unknown)
        )
    changed = sorted(dirty & allowed)
    key = publication_key(target, kind)
    ledger_entry = load_publication_ledger(root)["publications"].get(key, {})
    return {
        "publication_key": key,
        "date": target.isoformat(),
        "kind": kind,
        "task_id": completion["task_id"],
        "task_title": task["title"],
        "branch": publication_branch(policy, target, kind),
        "base_branch": policy["base_branch"],
        "changed_paths": changed,
        "unknown_paths": unknown,
        "ledger_status": ledger_entry.get("status"),
        "ready": bool(changed) or ledger_entry.get("status") == "complete",
    }


def _run_quality_checks(root: Path, runner: CommandRunner) -> None:
    commands = (
        [sys.executable, "-m", "devops_coach", "validate"],
        [sys.executable, "-m", "pytest"],
        [sys.executable, "scripts/check_markdown_links.py"],
        [sys.executable, "scripts/privacy_scan.py"],
        [sys.executable, "-m", "ruff", "check", "."],
        ["git", "diff", "--check"],
    )
    for command in commands:
        runner.run(list(command))


def _local_ref(runner: CommandRunner, branch: str) -> str | None:
    result = runner.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch}"], check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _remote_ref(runner: CommandRunner, branch: str) -> str | None:
    result = runner.run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"]
    )
    line = result.stdout.strip()
    return line.split()[0] if line else None


def _current_branch(runner: CommandRunner) -> str:
    return runner.run(["git", "branch", "--show-current"]).stdout.strip()


def _commit_has_key(runner: CommandRunner, revision: str, key: str) -> bool:
    result = runner.run(["git", "show", "-s", "--format=%B", revision], check=False)
    return result.returncode == 0 and f"DevOps-Coach-Publication: {key}" in result.stdout


def _json_output(result: CommandResult) -> Any:
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError as exc:
        raise PublicationError(f"Expected JSON from command: {' '.join(result.args)}") from exc


def _existing_pr(runner: CommandRunner, branch: str) -> dict[str, Any] | None:
    result = runner.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--head",
            branch,
            "--json",
            "number,state,isDraft,url,headRefOid",
        ]
    )
    prs = _json_output(result)
    if not isinstance(prs, list):
        raise PublicationError("GitHub PR list returned an unexpected response")
    if len(prs) > 1:
        raise PublicationError(f"Multiple pull requests exist for {branch}")
    return prs[0] if prs else None


def _add_available_labels(runner: CommandRunner, pr_number: int) -> None:
    labels_result = runner.run(
        ["gh", "label", "list", "--limit", "200", "--json", "name"], check=False
    )
    if labels_result.returncode != 0:
        return
    labels = _json_output(labels_result)
    available = {item.get("name") for item in labels if isinstance(item, dict)}
    selected = [label for label in ("codex", "codex-automation") if label in available]
    if selected:
        runner.run(
            ["gh", "pr", "edit", str(pr_number), "--add-label", ",".join(selected)],
            check=False,
        )


def _prepare_commit(
    root: Path,
    target: date,
    kind: str,
    plan: dict[str, Any],
    runner: CommandRunner,
    *,
    run_checks: bool,
) -> str:
    key = plan["publication_key"]
    branch = plan["branch"]
    base = plan["base_branch"]
    local_head = _local_ref(runner, branch)
    remote_head = _remote_ref(runner, branch)
    if local_head:
        if not _commit_has_key(runner, local_head, key):
            raise PublicationError(f"Existing local branch {branch} is not this publication")
        if remote_head and remote_head != local_head:
            raise PublicationError(f"Local and remote {branch} heads differ")
        if _current_branch(runner) != branch:
            runner.run(["git", "switch", branch])
        return local_head
    if remote_head:
        runner.run(["git", "switch", "-c", branch, "--track", f"origin/{branch}"])
        if not _commit_has_key(runner, remote_head, key):
            raise PublicationError(f"Existing remote branch {branch} is not this publication")
        return remote_head
    if _current_branch(runner) != base:
        raise PublicationError(
            f"New publication must start on {base}, not {_current_branch(runner)}"
        )
    local_base = runner.run(["git", "rev-parse", base]).stdout.strip()
    remote_base = runner.run(["git", "rev-parse", f"origin/{base}"]).stdout.strip()
    if local_base != remote_base:
        raise PublicationError(f"Local {base} must exactly match origin/{base} before publishing")
    if not plan["changed_paths"]:
        raise PublicationError("No eligible learning changes are available to publish")
    if run_checks:
        _run_quality_checks(root, runner)
    runner.run(["git", "switch", "-c", branch])
    runner.run(["git", "add", "--", *plan["changed_paths"]])
    cached = {
        item
        for item in runner.run(
            ["git", "diff", "--cached", "--name-only", "-z"]
        ).stdout.split("\0")
        if item
    }
    expected = set(plan["changed_paths"])
    if cached != expected:
        raise PublicationError(
            "Staged paths differ from the explicit publication set: "
            f"expected={sorted(expected)}, staged={sorted(cached)}"
        )
    subject = publication_subject(target, kind)
    runner.run(
        [
            "git",
            "commit",
            "-m",
            subject,
            "-m",
            f"DevOps-Coach-Publication: {key}",
        ]
    )
    return runner.run(["git", "rev-parse", "HEAD"]).stdout.strip()


def _ensure_pr(
    runner: CommandRunner,
    plan: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    branch = plan["branch"]
    existing = _existing_pr(runner, branch)
    if existing:
        if existing.get("headRefOid") != head:
            raise PublicationError("Existing pull request head does not match the publication")
        if existing.get("state") == "CLOSED":
            raise PublicationError("The publication pull request was closed without merging")
        return existing
    title = publication_subject(date.fromisoformat(plan["date"]), plan["kind"])
    body = (
        "Evidence-backed DevOps coaching publication.\n\n"
        f"- Task: `{plan['task_id']}`\n"
        f"- Publication: `{plan['publication_key']}`\n"
        "- Scope: structured learning state, weekly plan, and registered evidence only"
    )
    result = runner.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            plan["base_branch"],
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        ]
    )
    url = result.stdout.strip()
    created = _json_output(
        runner.run(
            ["gh", "pr", "view", url, "--json", "number,state,isDraft,url,headRefOid"]
        )
    )
    if created.get("isDraft"):
        raise PublicationError("Automatic publication requires a Ready pull request")
    _add_available_labels(runner, int(created["number"]))
    return created


def _finish_merge(
    root: Path,
    runner: CommandRunner,
    plan: dict[str, Any],
    pr: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    number = int(pr["number"])
    if pr.get("state") != "MERGED":
        runner.run(["gh", "pr", "checks", str(number), "--watch", "--interval", "10"])
        runner.run(
            [
                "gh",
                "pr",
                "merge",
                str(number),
                "--squash",
                "--delete-branch",
                "--match-head-commit",
                head,
            ]
        )
    merged = _json_output(
        runner.run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--json",
                "number,state,mergedAt,mergeCommit,url,headRefOid",
            ]
        )
    )
    if merged.get("state") != "MERGED" or merged.get("headRefOid") != head:
        raise PublicationError("Pull request merge verification failed")
    base = plan["base_branch"]
    branch = plan["branch"]
    if _current_branch(runner) != base:
        runner.run(["git", "switch", base])
    runner.run(["git", "fetch", "origin", base])
    runner.run(["git", "merge", "--ff-only", f"origin/{base}"])
    if _remote_ref(runner, branch):
        runner.run(["git", "push", "origin", "--delete", branch])
    if _local_ref(runner, branch):
        deleted = runner.run(["git", "branch", "-d", branch], check=False)
        if deleted.returncode != 0:
            runner.run(["git", "branch", "-D", branch])
    runner.run(["git", "worktree", "prune"])
    dirty = _dirty_paths(runner)
    if dirty:
        raise PublicationError(
            "Publication merged, but the worktree is not clean: " + ", ".join(sorted(dirty))
        )
    merge_commit = merged.get("mergeCommit")
    if isinstance(merge_commit, dict):
        merge_commit = merge_commit.get("oid")
    return {
        "status": "complete",
        "pr_number": number,
        "pr_url": merged.get("url"),
        "head": head,
        "merge_commit": merge_commit,
        "branch": branch,
        "base_branch": base,
    }


def publish_completed_task(
    root: Path,
    target: date,
    kind: str,
    *,
    apply: bool,
    runner: CommandRunner | None = None,
    run_checks: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    active_runner = runner or CommandRunner(root)
    plan = inspect_publication(root, target, kind, runner=active_runner)
    key = plan["publication_key"]
    existing = load_publication_ledger(root)["publications"].get(key, {})
    if existing.get("status") == "complete":
        return {**plan, **existing, "already_complete": True}
    if not apply:
        return {**plan, "status": "dry_run"}

    base = plan["base_branch"]
    active_runner.run(["git", "fetch", "origin", base])
    head = _prepare_commit(
        root, target, kind, plan, active_runner, run_checks=run_checks
    )
    _update_ledger(
        root,
        key,
        status="committed",
        date=target.isoformat(),
        kind=kind,
        task_id=plan["task_id"],
        branch=plan["branch"],
        head=head,
    )
    remote_head = _remote_ref(active_runner, plan["branch"])
    if remote_head and remote_head != head:
        raise PublicationError("Remote publication branch has a different head")
    if not remote_head:
        active_runner.run(["git", "push", "-u", "origin", plan["branch"]])
    _update_ledger(root, key, status="pushed", head=head)
    pr = _ensure_pr(active_runner, plan, head)
    _update_ledger(
        root,
        key,
        status="pr_ready" if pr.get("state") != "MERGED" else "merged",
        pr_number=int(pr["number"]),
        pr_url=pr.get("url"),
    )
    result = _finish_merge(root, active_runner, plan, pr, head)
    _update_ledger(root, key, **result)
    return {**plan, **result, "already_complete": False}


def recover_publications(
    root: Path,
    *,
    target: date | None = None,
    kind: str | None = None,
    runner: CommandRunner | None = None,
    run_checks: bool = True,
) -> list[dict[str, Any]]:
    root = root.resolve()
    _policy(root)
    progress = load_json(root / "state" / "progress.json")
    ledger = load_publication_ledger(root)["publications"]
    candidates: list[tuple[date, str]] = []
    for item in progress.get("completion_log", []):
        item_kind = item.get("kind")
        if item_kind not in PUBLICATION_KINDS:
            continue
        item_date = date.fromisoformat(item["date"])
        if target and item_date != target:
            continue
        if kind and item_kind != kind:
            continue
        key = publication_key(item_date, item_kind)
        if ledger.get(key, {}).get("status") != "complete":
            candidates.append((item_date, item_kind))
    candidates.sort(key=lambda item: (item[0], PUBLICATION_KINDS.index(item[1])))
    active_runner = runner or CommandRunner(root)
    return [
        publish_completed_task(
            root,
            item_date,
            item_kind,
            apply=True,
            runner=active_runner,
            run_checks=run_checks,
        )
        for item_date, item_kind in candidates
    ]
