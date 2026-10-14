from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from test_publication import FakeGitHubRunner, _complete_primary, _git, _prepare_repository

from devops_coach import drafts
from devops_coach.planner import record_checkpoint, render_week_plan, today_overview
from devops_coach.publication import (
    PublicationError,
    publish_completed_task,
    recover_publications,
)
from devops_coach.storage import load_json, write_json


def files(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }


def mixed(root: Path) -> tuple[dict, list[str]]:
    _prepare_repository(root)
    today_overview(root, date(2026, 8, 5))
    _complete_primary(root, date(2026, 8, 5), "2026-W32-03-mission")
    state = load_json(root / drafts.STATE)
    ids = [
        "2026-W31-01-mission",
        "2026-W31-02-mission",
        "2026-W32-01-mission",
        "2026-W32-02-mission",
    ]
    for tid in ids:
        t = state["tasks"][tid]
        t["status"] = "in_progress"
        t["evidence"] = "retained learner evidence " + tid
        t["checkpoints"][0].update(status="done", evidence=t["evidence"], hint_level_used=3)
    write_json(root / drafts.STATE, state)
    for week, plan in state["weekly_plans"].items():
        (root / plan["path"]).write_text(render_week_plan(state, week), encoding="utf-8")
    return state, ids


def test_import_and_single_task_publication_preserve_four_drafts(project_copy: Path):
    original, ids = mixed(project_copy)
    before = files(project_copy)
    preview = drafts.import_drafts(project_copy, apply=False)
    assert preview["status"] == "dry_run"
    assert files(project_copy) == before
    drafts.import_drafts(project_copy, apply=True)
    assert _git(project_copy, "status", "--porcelain") == ""
    assert drafts.load_progress(project_copy) == original
    assert drafts.import_drafts(project_copy, apply=True)["status"] == "already_imported"
    runner = FakeGitHubRunner(project_copy, fail_checks_once=True)
    with pytest.raises(PublicationError, match="simulated CI failure"):
        publish_completed_task(
            project_copy, date(2026, 8, 5), "primary", apply=True, runner=runner, run_checks=False
        )
    result = recover_publications(project_copy, runner=runner, run_checks=False)
    assert result[0]["publication_key"] == "2026-08-05:primary"
    assert len(runner.prs) == 1
    assert _git(project_copy, "status", "--porcelain") == ""
    published = load_json(project_copy / drafts.STATE)
    effective = drafts.load_progress(project_copy)
    for tid in ids:
        assert effective["tasks"][tid] == original["tasks"][tid]
        assert published["tasks"][tid] != original["tasks"][tid]
    assert effective["completion_log"] == original["completion_log"]
    assert (project_copy / "evidence/git/result.txt").read_text() == "verified learner evidence\n"
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []


def test_record_and_weekend_read_use_private_view(project_copy: Path):
    _prepare_repository(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    before_public = (project_copy / drafts.STATE).read_bytes()
    record_checkpoint(
        project_copy,
        "2026-W31-03-mission",
        "briefing",
        "done",
        None,
        "learner judgment",
        date(2026, 7, 29),
        hint_level_used=3,
    )
    assert (project_copy / drafts.STATE).read_bytes() == before_public
    assert (
        drafts.load_progress(project_copy)["tasks"]["2026-W31-03-mission"]["checkpoints"][0][
            "status"
        ]
        == "done"
    )
    before = files(project_copy)
    overview = today_overview(project_copy, date(2026, 8, 1))
    assert overview["today"]["rest"]
    assert files(project_copy) == before
    assert _git(project_copy, "status", "--porcelain") == ""


def test_stale_writer_and_conflicting_baseline_fail_closed(project_copy: Path):
    _prepare_repository(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    a = drafts.load_progress(project_copy)
    b = drafts.load_progress(project_copy)
    a["tasks"]["2026-W31-03-mission"]["evidence"] = "one"
    drafts.save_progress(project_copy, a)
    with pytest.raises(drafts.DraftError, match="Concurrent"):
        drafts.save_progress(project_copy, b)
    published = load_json(project_copy / drafts.STATE)
    published["tasks"]["2026-W31-03-mission"]["evidence"] = "two"
    write_json(project_copy / drafts.STATE, published)
    with pytest.raises(drafts.DraftError, match="conflict"):
        drafts.load_progress(project_copy)


def test_corrupt_draft_and_unknown_path_block(project_copy: Path):
    mixed(project_copy)
    rogue = project_copy / "rogue.txt"
    rogue.write_text("not learning")
    before = files(project_copy)
    with pytest.raises(drafts.DraftError, match="Unrelated paths"):
        drafts.import_drafts(project_copy, apply=True)
    assert files(project_copy) == before
    rogue.unlink()
    drafts.import_drafts(project_copy, apply=True)
    envelope = load_json(drafts.working_path(project_copy))
    envelope["payload"]["current"]["current_week"] = 99
    write_json(drafts.working_path(project_copy), envelope)
    with pytest.raises(drafts.DraftError, match="checksum"):
        drafts.load_progress(project_copy)


def test_import_interruption_resumes_from_verified_backup(project_copy: Path, monkeypatch):
    original, _ = mixed(project_copy)
    actual_restore = drafts.restore_files

    def interrupt(*args):
        raise OSError("power loss")

    monkeypatch.setattr(drafts, "restore_files", interrupt)
    with pytest.raises(OSError, match="power loss"):
        drafts.import_drafts(project_copy, apply=True)
    monkeypatch.setattr(drafts, "restore_files", actual_restore)
    drafts.import_drafts(project_copy, apply=True)
    assert drafts.load_progress(project_copy) == original
    assert _git(project_copy, "status", "--porcelain") == ""


def test_frozen_materialization_recovers_without_overwriting_new_edits(project_copy: Path):
    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    completion = drafts.load_progress(project_copy)["completion_log"][-1]
    transaction = drafts.prepare_snapshot(
        project_copy, "2026-08-05:primary", completion, apply=True
    )
    path = project_copy / drafts.STATE
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(drafts.DraftError, match="Concurrent file"):
        drafts.prepare_snapshot(project_copy, "2026-08-05:primary", completion, apply=True)
    path.write_bytes(drafts.unpack(transaction["files"][drafts.STATE]["snapshot"]))
    result = recover_publications(
        project_copy, runner=FakeGitHubRunner(project_copy), run_checks=False
    )
    assert result[0]["status"] == "complete"


def test_dry_run_does_not_write_and_target_definition_stays_strict(project_copy: Path):
    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    before = files(project_copy)
    result = publish_completed_task(project_copy, date(2026, 8, 5), "primary", apply=False)
    assert result["status"] == "dry_run"
    assert files(project_copy) == before
    progress = drafts.load_progress(project_copy)
    progress["tasks"]["2026-W32-03-mission"]["title"] = "unauthorized definition"
    drafts.save_progress(project_copy, progress)
    with pytest.raises(ValueError, match="definition changes"):
        publish_completed_task(project_copy, date(2026, 8, 5), "primary", apply=False)


def test_non_conflicting_remote_change_preserved(project_copy: Path):
    _prepare_repository(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    local = drafts.load_progress(project_copy)
    local["tasks"]["2026-W31-03-mission"]["evidence"] = "local"
    drafts.save_progress(project_copy, local)
    remote = load_json(project_copy / drafts.STATE)
    remote["tasks"]["2026-W31-04-mission"]["evidence"] = "remote"
    write_json(project_copy / drafts.STATE, remote)
    merged = drafts.load_progress(project_copy)
    assert merged["tasks"]["2026-W31-03-mission"]["evidence"] == "local"
    assert merged["tasks"]["2026-W31-04-mission"]["evidence"] == "remote"


def test_new_records_publish_after_drafts_enabled(project_copy: Path):
    _prepare_repository(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    _complete_primary(project_copy)
    assert (
        load_json(project_copy / drafts.STATE)["tasks"]["2026-W31-03-mission"]["status"] != "done"
    )
    result = publish_completed_task(
        project_copy,
        date(2026, 7, 29),
        "primary",
        apply=True,
        runner=FakeGitHubRunner(project_copy),
        run_checks=False,
    )
    assert result["status"] == "complete"
    assert _git(project_copy, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "stage", ["branch", "commit", "push", "pr", "merge", "switch_main", "cleanup"]
)
def test_recovery_at_publication_boundaries(project_copy: Path, stage: str):
    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)

    class InterruptRunner(FakeGitHubRunner):
        interrupted = False

        def run(self, args, *, check=True):
            result = super().run(args, check=check)
            matches = {
                "branch": args[:3] == ["git", "switch", "-c"],
                "commit": args[:2] == ["git", "commit"],
                "push": args[:3] == ["git", "push", "-u"],
                "pr": args[:3] == ["gh", "pr", "create"],
                "merge": args[:3] == ["gh", "pr", "merge"],
                "switch_main": args == ["git", "switch", "main"],
                "cleanup": args == ["git", "worktree", "prune"],
            }
            if matches[stage] and not self.interrupted:
                self.interrupted = True
                raise PublicationError("interrupted boundary")
            return result

    runner = InterruptRunner(project_copy)
    with pytest.raises(PublicationError, match="interrupted"):
        publish_completed_task(
            project_copy, date(2026, 8, 5), "primary", apply=True, runner=runner, run_checks=False
        )
    result = recover_publications(project_copy, runner=runner, run_checks=False)
    assert result[0]["status"] == "complete"
    assert len(runner.prs) == 1
    assert _git(project_copy, "status", "--porcelain") == ""


def test_changed_remote_artifact_cannot_be_overwritten(project_copy: Path):
    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    path = project_copy / "evidence/git/result.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("concurrent remote evidence")
    _git(project_copy, "add", "--", "evidence/git/result.txt")
    _git(project_copy, "commit", "-m", "test: concurrent evidence")
    with pytest.raises(drafts.DraftError, match="artifact conflict"):
        publish_completed_task(project_copy, date(2026, 8, 5), "primary", apply=False)


@pytest.mark.parametrize("target", [date(2026, 8, 5), date(2026, 8, 8)])
def test_cross_week_carryover_uses_private_evidence(project_copy: Path, target: date):
    original, ids = mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    runner = FakeGitHubRunner(project_copy)
    publish_completed_task(
        project_copy, date(2026, 8, 5), "primary", apply=True, runner=runner, run_checks=False
    )
    overview = today_overview(project_copy, target, continue_carryover=True)
    tid = overview["today"]["active_task"]["id"]
    assert tid == ids[0]
    assert (
        drafts.load_progress(project_copy)["tasks"][tid]["checkpoints"][0]
        == original["tasks"][tid]["checkpoints"][0]
    )
    for checkpoint in ("lab", "written_handoff"):
        record_checkpoint(
            project_copy,
            tid,
            checkpoint,
            "done",
            4 if checkpoint == "written_handoff" else None,
            "verified learner evidence",
            target,
            hint_level_used=0,
            independent=True,
            evidence_details={
                "prediction": "expected variation",
                "learner_action": "own action",
                "observed_result": "actual result",
                "interpretation": "own explanation",
                "handoff": "I verified the result. The variation passed.",
            },
        )
    result = publish_completed_task(
        project_copy, target, "carryover", task_id=tid, apply=True, runner=runner, run_checks=False
    )
    assert result["publication_key"] == f"{target.isoformat()}:carryover:{tid}"
    assert len(runner.prs) == 2
    assert _git(project_copy, "status", "--porcelain") == ""
    for other in ids[1:]:
        assert drafts.load_progress(project_copy)["tasks"][other] == original["tasks"][other]


def test_merge_complete_before_private_cleanup_recovers(project_copy: Path, monkeypatch):
    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    runner = FakeGitHubRunner(project_copy)
    finish = drafts.finish_snapshot

    def interrupt(*args):
        raise OSError("private cleanup interrupted")

    monkeypatch.setattr(drafts, "finish_snapshot", interrupt)
    with pytest.raises(OSError, match="cleanup interrupted"):
        publish_completed_task(
            project_copy, date(2026, 8, 5), "primary", apply=True, runner=runner, run_checks=False
        )
    monkeypatch.setattr(drafts, "finish_snapshot", finish)
    assert recover_publications(project_copy, runner=runner, run_checks=False) == []
    assert len(runner.prs) == 1
    frozen = drafts.unseal(drafts.snapshot_path(project_copy, "2026-08-05:primary"))
    assert frozen["finalized"]


def test_draft_preview_validation(project_copy: Path):
    from devops_coach.validation import validate_project

    mixed(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    assert validate_project(project_copy) == []
    assert validate_project(project_copy, include_drafts=True) == []


def test_completion_union_preserves_primary_before_carryovers():
    primary = {"task_id": "primary", "date": "2026-08-05", "kind": "primary"}
    carry = {"task_id": "old", "date": "2026-08-05", "kind": "carryover"}
    assert drafts.merge([], [primary, carry], [primary], "/completion_log") == [primary, carry]


def test_different_checkpoint_fields_merge_without_discarding_evidence():
    base = {"checkpoints": [{"id": "lab", "evidence": None, "hint_level_used": None}]}
    local = {"checkpoints": [{"id": "lab", "evidence": "learner", "hint_level_used": None}]}
    remote = {"checkpoints": [{"id": "lab", "evidence": None, "hint_level_used": 3}]}
    merged = drafts.merge(base, local, remote)
    assert merged["checkpoints"][0] == {"id": "lab", "evidence": "learner", "hint_level_used": 3}


def test_import_refuses_staged_changes(project_copy: Path):
    mixed(project_copy)
    _git(project_copy, "add", "--", drafts.STATE)
    before = files(project_copy)
    with pytest.raises(drafts.DraftError, match="Staged"):
        drafts.import_drafts(project_copy, apply=True)
    assert files(project_copy) == before


def test_write_lock_blocks_another_writer(project_copy: Path):
    _prepare_repository(project_copy)
    drafts.import_drafts(project_copy, apply=True)
    progress = drafts.load_progress(project_copy)
    with drafts.lock(project_copy), pytest.raises(drafts.DraftError, match="Another draft writer"):
        drafts.save_progress(project_copy, progress)
