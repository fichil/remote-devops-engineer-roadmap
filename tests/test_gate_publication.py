from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest
from test_drafts import complete_without_artifact
from test_publication import FakeGitHubRunner, _git, _prepare_repository

from devops_coach import drafts
from devops_coach.planner import ensure_week_plan, record_checkpoint
from devops_coach.publication import publish_completed_task, recover_publications
from devops_coach.storage import load_json

EARLY = (date(2026, 10, 23), "2026-W43-05-mission")
LATE = (date(2026, 10, 30), "2026-W44-05-mission")


@pytest.fixture
def gate_project(project_copy: Path, monkeypatch) -> Path:
    class FutureDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 6)

    monkeypatch.setattr("devops_coach.planner.date", FutureDate)
    monkeypatch.setattr("devops_coach.publication.date", FutureDate)
    _prepare_repository(project_copy)
    # Initialize an assessment and its remediation before either has passed.
    ensure_week_plan(project_copy, "2026-W43")
    ensure_week_plan(project_copy, "2026-W44")
    _git(project_copy, "add", "--", drafts.STATE, "plans")
    _git(project_copy, "commit", "-m", "test: scheduled gate and remediation")
    _git(project_copy, "push", "origin", "main")
    drafts.import_drafts(project_copy, apply=True)
    artifact = project_copy / "evidence/unfinished.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("private unfinished evidence\n", encoding="utf-8")
    record_checkpoint(
        project_copy, "2026-W31-03-mission", "briefing", "done", None,
        "unfinished private task", date(2026, 7, 29), artifacts=[artifact], hint_level_used=3,
    )
    return project_copy


def publish(root: Path, target: date, runner: FakeGitHubRunner):
    return publish_completed_task(
        root, target, "primary", apply=True, runner=runner, run_checks=False,
    )


@pytest.mark.parametrize("interruption", [None, "merged", "finalize", "rebased"])
def test_same_gate_pending_publications_preserve_drafts_and_recover(
    gate_project: Path, monkeypatch, interruption: str | None,
):
    root = gate_project
    complete_without_artifact(root, *EARLY, score=4, evidence="earlier assessment")
    early_gate = copy.deepcopy(drafts.load_progress(root)["phase_gates"]["foundations"])
    complete_without_artifact(root, *LATE, score=5, evidence="later assessment")
    before = drafts.load_progress(root)
    expected_gate = copy.deepcopy(before["phase_gates"]["foundations"])
    private_task = copy.deepcopy(before["tasks"]["2026-W31-03-mission"])
    private_artifacts = copy.deepcopy(drafts.unseal(drafts.working_path(root))["artifacts"])

    class InterruptRunner(FakeGitHubRunner):
        interrupted = False

        def run(self, args, *, check=True):
            result = super().run(args, check=check)
            if interruption == "merged" and args[:3] == ["gh", "pr", "merge"]:
                if not self.interrupted:
                    self.interrupted = True
                    raise OSError("after merge")
            return result

    runner = InterruptRunner(root)
    original_finish = drafts.finish_snapshot
    original_previews = drafts.previews
    if interruption in {"finalize", "rebased"}:
        def interrupt(*args):
            raise OSError("during finalize")

        hook = "finish_snapshot" if interruption == "finalize" else "previews"
        monkeypatch.setattr(drafts, hook, interrupt)
    if interruption:
        with pytest.raises(OSError):
            publish(root, EARLY[0], runner)
        monkeypatch.setattr(drafts, "finish_snapshot", original_finish)
        monkeypatch.setattr(drafts, "previews", original_previews)
        recover_publications(root, target=EARLY[0], runner=runner, run_checks=False)
    else:
        publish(root, EARLY[0], runner)
    published = load_json(root / drafts.STATE)
    assert published["phase_gates"]["foundations"] == early_gate
    assert published["tasks"][LATE[1]]["status"] != "done"
    effective = drafts.load_progress(root)
    assert effective["phase_gates"]["foundations"] == expected_gate
    assert effective["tasks"][LATE[1]] == before["tasks"][LATE[1]]
    assert effective["tasks"]["2026-W31-03-mission"] == private_task
    assert drafts.unseal(drafts.working_path(root))["artifacts"] == private_artifacts
    results = recover_publications(root, runner=runner, run_checks=False)
    assert [item["publication_key"] for item in results] == ["2026-10-30:primary"]
    assert load_json(root / drafts.STATE)["phase_gates"]["foundations"] == expected_gate
    assert drafts.load_progress(root)["tasks"]["2026-W31-03-mission"] == private_task
    assert drafts.unseal(drafts.working_path(root))["artifacts"] == private_artifacts
    assert len(runner.prs) == 2
    assert recover_publications(root, runner=runner, run_checks=False) == []
    assert _git(root, "status", "--porcelain") == ""


def test_backdated_gate_keeps_newer_published_result(gate_project: Path):
    root = gate_project
    complete_without_artifact(root, *LATE, score=4, evidence="later assessment")
    expected_gate = copy.deepcopy(drafts.load_progress(root)["phase_gates"]["foundations"])
    runner = FakeGitHubRunner(root)
    publish(root, LATE[0], runner)
    complete_without_artifact(root, *EARLY, score=5, evidence="earlier assessment")
    assert drafts.load_progress(root)["phase_gates"]["foundations"] == expected_gate
    # Publishing the stronger but older result must not replace the later metadata.
    publish(root, EARLY[0], runner)
    assert load_json(root / drafts.STATE)["phase_gates"]["foundations"] == expected_gate
    assert drafts.load_progress(root)["phase_gates"]["foundations"] == expected_gate
    assert len(runner.prs) == 2
    assert recover_publications(root, runner=runner, run_checks=False) == []


def test_reverse_recording_order_preserves_latest_gate(gate_project: Path):
    root = gate_project
    complete_without_artifact(root, *LATE, score=4, evidence="later assessment")
    expected_gate = copy.deepcopy(drafts.load_progress(root)["phase_gates"]["foundations"])
    complete_without_artifact(root, *EARLY, score=5, evidence="earlier assessment")
    assert drafts.load_progress(root)["phase_gates"]["foundations"] == expected_gate
    runner = FakeGitHubRunner(root)
    results = recover_publications(root, runner=runner, run_checks=False)
    assert [item["publication_key"] for item in results] == [
        "2026-10-23:primary", "2026-10-30:primary",
    ]
    assert load_json(root / drafts.STATE)["phase_gates"]["foundations"] == expected_gate


@pytest.mark.parametrize("change", ["gate", "task"])
def test_same_gate_merge_does_not_hide_unproven_edits(gate_project: Path, change: str):
    root = gate_project
    complete_without_artifact(root, *EARLY, score=4, evidence="earlier assessment")
    complete_without_artifact(root, *LATE, score=5, evidence="later assessment")
    local = drafts.load_progress(root)
    base = drafts.unseal(drafts.working_path(root))["baseline"]
    remote = drafts.candidate(root, local, local["completion_log"][0])
    if change == "gate":
        local["phase_gates"]["foundations"]["evidence"] = "not derived from an assessment"
    else:
        remote["tasks"][LATE[1]]["evidence"] = "conflicting task evidence"
    with pytest.raises(drafts.DraftError, match="Concurrent progress conflict"):
        drafts.merge_progress(base, local, remote)
