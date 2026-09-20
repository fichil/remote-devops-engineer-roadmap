from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from devops_coach.planner import ensure_week_plan, record_checkpoint, today_overview
from devops_coach.publication import (
    LEDGER_PATH,
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


def _old_task(task_id: str, scheduled_for: str, queue_order: int) -> dict[str, Any]:
    return {
        "id": task_id,
        "created_on": scheduled_for,
        "scheduled_for": scheduled_for,
        "curriculum_week": 1,
        "phase": "foundations",
        "section": "legacy",
        "title": f"Old task {task_id}",
        "status": "queued",
        "score": None,
        "evidence": None,
        "completed_on": None,
        "next_review": None,
        "queue_order": queue_order,
        "source": "test",
        "carryover_activated_on": None,
        "checkpoints": [
            {
                "id": "work",
                "title": "历史任务",
                "instruction": "Complete the old task.",
                "status": "queued",
                "score": None,
                "evidence": None,
                "next_review": None,
            }
        ],
    }


def _complete_carryover(project: Path, target: date, task_id: str) -> None:
    record_checkpoint(
        project,
        task_id,
        "work",
        "done",
        4,
        f"verified {task_id}",
        target,
    )


class FakeGitHubRunner(CommandRunner):
    def __init__(self, root: Path, *, fail_checks_once: bool = False):
        super().__init__(root)
        self.prs: dict[str, dict[str, object]] = {}
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
            branch = args[args.index("--head") + 1]
            pr = self.prs.get(branch)
            return self._result(args, json.dumps([pr] if pr else []), check=check)
        if args[1:3] == ["pr", "create"]:
            head = super().run(["git", "rev-parse", "HEAD"]).stdout.strip()
            branch = args[args.index("--head") + 1]
            number = len(self.prs) + 1
            pr = {
                "number": number,
                "state": "OPEN",
                "isDraft": False,
                "url": f"https://example.invalid/pr/{number}",
                "headRefOid": head,
            }
            self.prs[branch] = pr
            return self._result(args, str(pr["url"]) + "\n", check=check)
        if args[1:3] == ["pr", "view"]:
            identifier = args[3]
            pr = next(
                (
                    item
                    for item in self.prs.values()
                    if str(item["number"]) == identifier or item["url"] == identifier
                ),
                None,
            )
            assert pr is not None
            return self._result(args, json.dumps(pr), check=check)
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
            number = int(args[3])
            pr = next(item for item in self.prs.values() if item["number"] == number)
            branch = super().run(["git", "branch", "--show-current"]).stdout.strip()
            super().run(["git", "push", "origin", "HEAD:main"])
            super().run(["git", "push", "origin", "--delete", branch])
            pr.update(
                {
                    "state": "MERGED",
                    "mergedAt": "2026-07-29T12:00:00Z",
                    "mergeCommit": {"oid": pr["headRefOid"]},
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


def test_three_carryovers_use_independent_publications(project_copy: Path) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for index in range(1, 4):
        task_id = f"old-{index}"
        state["tasks"][task_id] = _old_task(task_id, "2026-07-28", index)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    target = date(2026, 7, 29)
    runner = FakeGitHubRunner(project_copy)
    publish_completed_task(
        project_copy,
        target,
        "primary",
        apply=True,
        runner=runner,
        run_checks=False,
    )

    results: list[dict[str, Any]] = []
    for index in range(1, 4):
        task_id = f"old-{index}"
        overview = today_overview(project_copy, target, continue_carryover=True)
        assert overview["today"]["active_task"]["id"] == task_id
        _complete_carryover(project_copy, target, task_id)
        results.append(
            publish_completed_task(
                project_copy,
                target,
                "carryover",
                task_id=task_id,
                apply=True,
                runner=runner,
                run_checks=False,
            )
        )

    keys = [result["publication_key"] for result in results]
    branches = [result["branch"] for result in results]
    assert keys == [
        "2026-07-29:carryover:old-1",
        "2026-07-29:carryover:old-2",
        "2026-07-29:carryover:old-3",
    ]
    assert len(set(branches)) == 3
    assert all(branch.startswith("learn/2026-07-29-carryover-old-") for branch in branches)
    assert len(runner.prs) == 4
    ledger = load_publication_ledger(project_copy)
    assert ledger["schema_version"] == 2
    assert all(ledger["publications"][key]["status"] == "complete" for key in keys)
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []


def test_recovery_refuses_multiple_unfrozen_completions(project_copy: Path) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    state_path = project_copy / "state" / "progress.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["completion_log"].append(
        {
            "date": "2026-07-29",
            "task_id": "unexpected-second-task",
            "kind": "carryover",
            "evidence": "unexpected unisolated evidence",
            "artifacts": [],
        }
    )
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(PublicationError, match="not isolated"):
        recover_publications(
            project_copy,
            runner=FakeGitHubRunner(project_copy),
            run_checks=False,
        )


def test_legacy_carryover_key_is_reused_without_republication(project_copy: Path) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-28", 1)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    target = date(2026, 7, 29)
    runner = FakeGitHubRunner(project_copy)
    publish_completed_task(
        project_copy,
        target,
        "primary",
        apply=True,
        runner=runner,
        run_checks=False,
    )
    today_overview(project_copy, target, continue_carryover=True)
    _complete_carryover(project_copy, target, "old-1")
    published = publish_completed_task(
        project_copy,
        target,
        "carryover",
        task_id="old-1",
        apply=True,
        runner=runner,
        run_checks=False,
    )

    ledger_path = project_copy / LEDGER_PATH
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entry = ledger["publications"].pop(published["publication_key"])
    ledger["publications"]["2026-07-29:carryover"] = entry
    ledger["schema_version"] = 1
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    pr_count = len(runner.prs)

    repeated = publish_completed_task(
        project_copy,
        target,
        "carryover",
        task_id="old-1",
        apply=True,
        runner=runner,
        run_checks=False,
    )
    assert repeated["already_complete"] is True
    assert repeated["publication_key"] == "2026-07-29:carryover"
    assert len(runner.prs) == pr_count
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []


@pytest.mark.parametrize("field", ["status", "evidence", "score", "carryover_activated_on"])
def test_scope_rejects_other_task_in_same_state(project_copy: Path, field: str) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    path = project_copy / "state/progress.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tasks"]["2026-W31-04-mission"][field] = "unexpected"
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(PublicationError, match="2026-W31-04-mission"):
        inspect_publication(project_copy, date(2026, 7, 29), "primary")


def test_scope_rejects_other_tasks_registered_artifact(project_copy: Path) -> None:
    _prepare_repository(project_copy)
    path = project_copy / "state/progress.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tasks"]["2026-W31-04-mission"]["artifacts"] = ["evidence/other.txt"]
    path.write_text(json.dumps(state), encoding="utf-8")
    _git(project_copy, "add", "state/progress.json")
    _git(project_copy, "commit", "-m", "test: register other artifact")
    _complete_primary(project_copy)
    (project_copy / "evidence/other.txt").write_text("other evidence", encoding="utf-8")
    with pytest.raises(PublicationError, match="target-task path"):
        inspect_publication(project_copy, date(2026, 7, 29), "primary")


def test_scope_rejects_edited_weekly_plan(project_copy: Path) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    path = project_copy / "plans/weeks/2026-W31.md"
    path.write_text(path.read_text(encoding="utf-8") + "Unreviewed note\n", encoding="utf-8")
    with pytest.raises(PublicationError, match="not synchronized"):
        inspect_publication(project_copy, date(2026, 7, 29), "primary")


def test_scope_rejects_contaminated_recovery_commit(project_copy: Path) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)
    _git(project_copy, "switch", "-c", "learn/2026-07-29")
    (project_copy / "rogue.txt").write_text("unrelated", encoding="utf-8")
    _git(project_copy, "add", "state", "plans", "evidence", "rogue.txt")
    _git(project_copy, "commit", "-m", "DevOps-Coach-Publication: 2026-07-29:primary")
    with pytest.raises(PublicationError, match="target-task path"):
        inspect_publication(project_copy, date(2026, 7, 29), "primary")


@pytest.mark.parametrize("changed_task", ["2026-W31-04-mission", "2026-W31-03-mission"])
def test_scope_rechecks_staged_content(project_copy: Path, changed_task: str) -> None:
    _prepare_repository(project_copy)
    _complete_primary(project_copy)

    class ChangedIndexRunner(FakeGitHubRunner):
        def run(self, args, *, check=True):
            result = super().run(args, check=check)
            if args[:2] == ["git", "add"]:
                path = self.root / "state/progress.json"
                state = json.loads(path.read_text(encoding="utf-8"))
                state["tasks"][changed_task]["evidence"] = "unexpected"
                path.write_text(json.dumps(state), encoding="utf-8")
                super().run(["git", "add", "--", "state/progress.json"])
            return result

    message = "2026-W31-04-mission" if changed_task.endswith("04-mission") else "Staged content"
    with pytest.raises(PublicationError, match=message):
        publish_completed_task(
            project_copy,
            date(2026, 7, 29),
            "primary",
            apply=True,
            runner=ChangedIndexRunner(project_copy),
            run_checks=False,
        )


def test_scope_accepts_deterministic_new_week_only(project_copy: Path) -> None:
    _prepare_repository(project_copy)
    ensure_week_plan(project_copy, "2026-W32")
    target = date(2026, 8, 3)
    state = json.loads((project_copy / "state/progress.json").read_text(encoding="utf-8"))
    task_id = "2026-W32-01-mission"
    for checkpoint in state["tasks"][task_id]["checkpoints"]:
        record_checkpoint(
            project_copy,
            task_id,
            checkpoint["id"],
            "done",
            3 if checkpoint.get("assessment") == "summative" else None,
            "Learner evidence",
            target,
            evidence_details={
                "prediction": "The test should pass.",
                "learner_action": "Selected the check.",
                "observed_result": "The check passed.",
                "interpretation": "The result matches the requirement.",
                "handoff": "The check passed. Ready for review.",
            },
        )
    assert inspect_publication(project_copy, target, "primary")["ready"]
    path = project_copy / "state/progress.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tasks"]["2026-W32-02-mission"]["title"] = "changed curriculum"
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(PublicationError, match="2026-W32-02-mission"):
        inspect_publication(project_copy, target, "primary")


def test_weekend_carryovers_publish_separately_and_recover_original_identity(project_copy: Path):
    _prepare_repository(project_copy)
    path = project_copy / "state/progress.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tasks"]["old-1"] = _old_task("old-1", "2026-07-20", -2)
    state["tasks"]["old-2"] = _old_task("old-2", "2026-07-21", -1)
    path.write_text(json.dumps(state), encoding="utf-8")
    _git(project_copy, "add", "state/progress.json")
    _git(project_copy, "commit", "-m", "test: existing carryovers")
    _git(project_copy, "push", "origin", "main")
    target = date(2026, 8, 8)  # No current-week plan, no weekend primary.
    today_overview(project_copy, target, True)
    _complete_carryover(project_copy, target, "old-1")
    with pytest.raises(PublicationError, match="Weekend publications"):
        inspect_publication(project_copy, target, "primary")
    runner = FakeGitHubRunner(project_copy, fail_checks_once=True)
    with pytest.raises(PublicationError, match="simulated CI failure"):
        publish_completed_task(
            project_copy, target, "carryover", task_id="old-1",
            apply=True, runner=runner, run_checks=False,
        )
    original = next(iter(load_publication_ledger(project_copy)["publications"]))
    with pytest.raises(ValueError, match="publication"):
        today_overview(project_copy, date(2026, 8, 9), True)
    recovered = recover_publications(project_copy, runner=runner, run_checks=False)
    assert recovered[0]["publication_key"] == original
    assert len(runner.prs) == 1
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []
    assert today_overview(project_copy, target)["today"]["active_task"] is None
    assert today_overview(project_copy, target, True)["today"]["active_task"]["id"] == "old-2"
    _complete_carryover(project_copy, target, "old-2")
    second = publish_completed_task(
        project_copy, target, "carryover", task_id="old-2",
        apply=True, runner=runner, run_checks=False,
    )
    assert second["publication_key"] != original
    assert len(runner.prs) == 2
    assert all(pr["state"] == "MERGED" and not pr["isDraft"] for pr in runner.prs.values())
    assert _git(project_copy, "status", "--porcelain") == ""
    assert _git(project_copy, "branch", "--show-current") == "main"
    assert _git(project_copy, "branch", "--list", "learn/*") == ""
    assert _git(project_copy, "worktree", "list", "--porcelain").count("worktree ") == 1
    state = json.loads(path.read_text(encoding="utf-8"))
    assert "2026-W32" not in state["weekly_plans"]
    assert len(state["completion_log"]) == 2
    assert all(item["date"] == target.isoformat() for item in state["completion_log"])


def test_weekend_publication_rejects_missing_activation_and_other_task_changes(project_copy: Path):
    _prepare_repository(project_copy)
    target = date(2026, 8, 2)
    active = today_overview(project_copy, target, True)["today"]["active_task"]["id"]
    path = project_copy / "state/progress.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    for checkpoint in state["tasks"][active]["checkpoints"]:
        record_checkpoint(
            project_copy, active, checkpoint["id"], "done",
            3 if checkpoint.get("assessment") == "summative" else None,
            "Verified learner evidence", target,
            evidence_details={
                "prediction": "Expected a match.", "learner_action": "Checked my prefix.",
                "observed_result": "It matched.", "interpretation": "The target is included.",
                "handoff": "The offline check passed. No network changes were made.",
            },
        )
    inspect_publication(project_copy, target, "carryover", task_id=active)
    state = json.loads(path.read_text(encoding="utf-8"))
    state["tasks"][active]["carryover_activated_on"] = None
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(PublicationError, match="activation"):
        inspect_publication(project_copy, target, "carryover", task_id=active)
    state["tasks"][active]["carryover_activated_on"] = target.isoformat()
    state["tasks"]["2026-W31-05-mission"]["title"] = "unrelated edit"
    path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(PublicationError, match="Unrelated task changes"):
        inspect_publication(project_copy, target, "carryover", task_id=active)
