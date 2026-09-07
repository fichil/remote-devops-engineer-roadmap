from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from devops_coach.planner import ensure_week_plan, record_checkpoint, today_overview
from devops_coach.publication import (
    CommandResult,
    CommandRunner,
    PublicationError,
    inspect_publication,
    load_publication_ledger,
    publish_completed_task,
    recover_publications,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return completed.stdout.strip()


def _prepare_repository(project: Path) -> Path:
    target = date(2026, 7, 29)
    ensure_week_plan(project, "2026-W31")
    today_overview(project, target)
    (project / ".gitignore").write_text("private/\n", encoding="utf-8")
    remote = project.parent / f"{project.name}-remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    _git(project, "init", "-b", "main")
    _git(project, "config", "user.name", "DevOps Coach Test")
    _git(project, "config", "user.email", "devops-coach.invalid")
    _git(project, "remote", "add", "origin", str(remote))
    _git(project, "add", "--", ".gitignore", "config", "curriculum", "schemas", "state", "plans")
    _git(project, "commit", "-m", "test: baseline")
    _git(project, "push", "-u", "origin", "main")
    return remote


def _complete_primary(project: Path) -> None:
    target = date(2026, 7, 29)
    task_id = "2026-W31-03-mission"
    artifact = project / "evidence" / "git" / "result.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("verified learner evidence\n", encoding="utf-8")
    for checkpoint_id in ("briefing", "lab", "written_handoff"):
        record_checkpoint(
            project,
            task_id,
            checkpoint_id,
            "done",
            4 if checkpoint_id == "written_handoff" else None,
            f"verified {checkpoint_id}",
            target,
            artifacts=[artifact] if checkpoint_id == "lab" else (),
            hint_level_used=0,
            independent=True,
            evidence_details={
                "prediction": "The variation should preserve the result.",
                "learner_action": "Ran an independently selected verification.",
                "observed_result": "The variation passed verification.",
                "interpretation": "The result confirms the selected approach.",
                "handoff": "Verification passed. The evidence is attached.",
            },
        )


class FakeGitHubRunner(CommandRunner):
    def __init__(self, root: Path, *, fail_checks_once: bool = False):
        super().__init__(root)
        self.pr: dict[str, object] | None = None
        self.fail_checks_once = fail_checks_once
        self.labels: list[str] = []

    def _result(
        self, args: list[str], stdout: str = "", returncode: int = 0, check: bool = True
    ) -> CommandResult:
        result = CommandResult(tuple(args), returncode, stdout, "simulated CI failure")
        if check and returncode:
            raise PublicationError("simulated CI failure")
        return result

    def run(self, args: list[str], *, check: bool = True) -> CommandResult:
        if args[0] != "gh":
            return super().run(args, check=check)
        if args[1:3] == ["pr", "list"]:
            return self._result(args, json.dumps([self.pr] if self.pr else []), check=check)
        if args[1:3] == ["pr", "create"]:
            head = super().run(["git", "rev-parse", "HEAD"]).stdout.strip()
            self.pr = {
                "number": 1,
                "state": "OPEN",
                "isDraft": False,
                "url": "https://example.invalid/pr/1",
                "headRefOid": head,
            }
            return self._result(args, str(self.pr["url"]) + "\n", check=check)
        if args[1:3] == ["pr", "view"]:
            assert self.pr is not None
            return self._result(args, json.dumps(self.pr), check=check)
        if args[1:3] == ["label", "list"]:
            return self._result(
                args,
                json.dumps([{"name": "codex"}, {"name": "codex-automation"}]),
                check=check,
            )
        if args[1:3] == ["pr", "edit"]:
            self.labels = args[-1].split(",")
            return self._result(args, check=check)
        if args[1:3] == ["pr", "checks"]:
            if self.fail_checks_once:
                self.fail_checks_once = False
                return self._result(args, returncode=1, check=check)
            return self._result(args, "all checks passed\n", check=check)
        if args[1:3] == ["pr", "merge"]:
            assert self.pr is not None
            branch = super().run(["git", "branch", "--show-current"]).stdout.strip()
            super().run(["git", "push", "origin", "HEAD:main"])
            super().run(["git", "push", "origin", "--delete", branch])
            self.pr.update(
                {
                    "state": "MERGED",
                    "mergedAt": "2026-07-29T12:00:00Z",
                    "mergeCommit": {"oid": self.pr["headRefOid"]},
                }
            )
            return self._result(args, check=check)
        raise AssertionError(f"Unexpected GitHub command: {args}")


def test_publication_rejects_unknown_changes_and_recovers_one_pr(
    project_copy: Path,
) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    rogue = project_copy / "rogue.txt"
    rogue.write_text("unrelated\n", encoding="utf-8")
    with pytest.raises(PublicationError, match="Unrelated"):
        inspect_publication(project_copy, date(2026, 7, 29), "primary")
    rogue.unlink()

    runner = FakeGitHubRunner(project_copy, fail_checks_once=True)
    with pytest.raises(PublicationError, match="simulated CI failure"):
        publish_completed_task(
            project_copy,
            date(2026, 7, 29),
            "primary",
            apply=True,
            runner=runner,
            run_checks=False,
        )
    ledger = load_publication_ledger(project_copy)
    assert ledger["publications"]["2026-07-29:primary"]["status"] == "pr_ready"

    result = publish_completed_task(
        project_copy,
        date(2026, 7, 29),
        "primary",
        apply=True,
        runner=runner,
        run_checks=False,
    )

    assert result["status"] == "complete"
    assert runner.labels == ["codex", "codex-automation"]
    assert _git(project_copy, "branch", "--show-current") == "main"
    assert _git(project_copy, "status", "--porcelain") == ""
    assert _git(project_copy, "branch", "--list", "learn/2026-07-29") == ""
    remote_refs = _git(project_copy, "ls-remote", "--heads", "origin")
    assert "refs/heads/learn/2026-07-29" not in remote_refs
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []

    repeated = publish_completed_task(
        project_copy,
        date(2026, 7, 29),
        "primary",
        apply=True,
        runner=runner,
        run_checks=False,
    )
    assert repeated["already_complete"] is True
