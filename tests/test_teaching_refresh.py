from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from devops_coach.cli import main
from devops_coach.migration import refresh_teaching
from devops_coach.planner import ensure_week_plan, record_checkpoint, task_has_complete_evidence
from devops_coach.storage import load_json, load_yaml, write_json
from devops_coach.teaching import TEACHING_FIELDS, checkpoint_teaching


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def prepare(root: Path) -> dict:
    ensure_week_plan(root, "2026-W37")
    state = load_json(root / "state/progress.json")
    first, completed, blocked, cancelled, queued = state["tasks"].values()
    first["status"] = "in_progress"
    first["checkpoints"][0].update(status="done", evidence="learner explanation", hint_level_used=1)
    lab = first["checkpoints"][1]
    lab.update(
        status="in_progress", hint_level_used=3, evidence="three layers verified",
        artifacts=["evidence/layers.md"],
        evidence_details={
            "prediction": "uncertain, perhaps a different version",
            "learner_action": "read host and WSL information",
            "observed_result": "Windows host and WSL2 observed",
            "interpretation": "learner's own explanation", "handoff": None,
        },
    )
    completed.update(status="done", completed_on="2026-09-08", score=4, evidence="verified")
    for checkpoint in completed["checkpoints"]:
        checkpoint.update(status="done", evidence="historical verified evidence")
    cancelled["status"] = "cancelled"
    blocked.update(status="blocked", score=3, next_review="2026-09-16")
    blocked["checkpoints"][2].update(
        status="blocked", score=3, hint_level_used=2, independent=False,
        evidence="partial independent attempt", next_review="2026-09-16",
    )
    # Deliberately stale historical wording, including immutable completed checkpoints.
    for task in state["tasks"].values():
        for checkpoint in task["checkpoints"]:
            for field in TEACHING_FIELDS:
                checkpoint[field] = "old " + field
    state["completion_log"] = [{"task_id": completed["id"], "evidence": "historical log"}]
    state["weekly_reviews"] = {"2026-W36": {"retained": "historical review"}}
    write_json(root / "state/progress.json", state)
    return state


def test_refresh_dry_run_is_zero_writes(project_copy: Path) -> None:
    prepare(project_copy)
    before = snapshot(project_copy)
    result = refresh_teaching(project_copy, dry_run=True)
    assert result["would_change"] is True
    assert result["changed"] is False
    assert result["checkpoints_refreshed"] == 8
    assert snapshot(project_copy) == before


def test_refresh_preserves_every_non_teaching_field_and_completed_checkpoint(
    project_copy: Path,
) -> None:
    before = prepare(project_copy)
    raw = (project_copy / "state/progress.json").read_bytes()
    result = refresh_teaching(project_copy)
    after = load_json(project_copy / "state/progress.json")
    assert (project_copy / result["backup"]).read_bytes() == raw
    expected = deepcopy(before)
    for task_id, task in expected["tasks"].items():
        if task["status"] not in {"done", "cancelled"}:
            for index, checkpoint in enumerate(task["checkpoints"]):
                if checkpoint["status"] not in {"done", "cancelled"}:
                    for field in TEACHING_FIELDS:
                        checkpoint[field] = after["tasks"][task_id]["checkpoints"][index][field]
    assert after == expected
    assert "uname -r" in after["tasks"]["2026-W37-01-mission"]["checkpoints"][1]["instruction"]
    assert not task_has_complete_evidence(after["tasks"]["2026-W37-01-mission"])
    first_pass = snapshot(project_copy)
    assert refresh_teaching(project_copy)["changed"] is False
    assert snapshot(project_copy) == first_pass


@pytest.mark.parametrize("week", ["2026-W31", "2026-W35", "2026-W37", "2026-W44"])
def test_new_generation_and_refresh_use_identical_teaching(project_copy: Path, week: str) -> None:
    ensure_week_plan(project_copy, week)
    before = snapshot(project_copy)
    assert refresh_teaching(project_copy)["changed"] is False
    assert snapshot(project_copy) == before
    state = load_json(project_copy / "state/progress.json")
    for task in state["tasks"].values():
        assert [c["assessment"] for c in task["checkpoints"]] == [
            "formative", "formative", "summative",
        ]
        assert all(c["status"] == "queued" and c["score"] is None for c in task["checkpoints"])


@pytest.mark.parametrize("mode", ["reteach", "stretch"])
def test_refresh_preserves_original_adaptation(project_copy: Path, mode: str) -> None:
    state_path = project_copy / "state/progress.json"
    state = load_json(state_path)
    state["adaptation"]["mode"] = mode
    write_json(state_path, state)
    ensure_week_plan(project_copy, "2026-W37")
    state = load_json(state_path)
    state["adaptation"]["mode"] = "standard"
    instruction = state["tasks"]["2026-W37-01-mission"]["checkpoints"][0]["instruction"]
    write_json(state_path, state)
    refresh_teaching(project_copy)
    after = load_json(state_path)
    assert after["tasks"]["2026-W37-01-mission"]["checkpoints"][0]["instruction"] == instruction


def test_refresh_repairs_interrupted_plan_sync_without_rewriting_state(project_copy: Path) -> None:
    prepare(project_copy)
    refresh_teaching(project_copy)
    state_before = (project_copy / "state/progress.json").read_bytes()
    plan = project_copy / "plans/weeks/2026-W37.md"
    expected = plan.read_bytes()
    plan.write_text("stale plan\n", encoding="utf-8")
    result = refresh_teaching(project_copy)
    assert result["task_ids"] == []
    assert result["plans_synced"] == ["plans/weeks/2026-W37.md"]
    assert (project_copy / "state/progress.json").read_bytes() == state_before
    assert plan.read_bytes() == expected


def test_missing_blueprint_fails_before_any_write(project_copy: Path) -> None:
    state = prepare(project_copy)
    state["tasks"]["2026-W37-01-mission"]["curriculum_week"] = 78
    write_json(project_copy / "state/progress.json", state)
    before = snapshot(project_copy)
    with pytest.raises(ValueError, match="Missing training blueprint"):
        refresh_teaching(project_copy)
    assert snapshot(project_copy) == before


def test_refresh_backup_collision_fails_without_touching_progress(project_copy: Path) -> None:
    prepare(project_copy)
    preview = refresh_teaching(project_copy, dry_run=True)
    backup = project_copy / preview["backup"]
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"different backup")
    before = snapshot(project_copy)
    with pytest.raises(ValueError, match="backup differs"):
        refresh_teaching(project_copy)
    assert snapshot(project_copy) == before


def test_refresh_cli_never_records_or_publishes(project_copy: Path, monkeypatch) -> None:
    prepare(project_copy)

    def forbidden(*args, **kwargs):
        pytest.fail("teaching maintenance must not record or publish")

    for function in ("record_checkpoint", "publish_completed_task", "recover_publications"):
        monkeypatch.setattr("devops_coach.cli." + function, forbidden)
    assert main(["--root", str(project_copy), "migrate", "--refresh-teaching", "--dry-run"]) == 0
    assert main(["--root", str(project_copy), "migrate", "--refresh-teaching"]) == 0


@pytest.mark.parametrize("conflict", [["--to-schema", "2"], [
    "--to-training", "cognitive_apprenticeship_v1",
]])
def test_refresh_cli_is_mutually_exclusive(project_copy: Path, conflict: list[str]) -> None:
    before = snapshot(project_copy)
    with pytest.raises(SystemExit):
        main(["--root", str(project_copy), "migrate", "--refresh-teaching", *conflict])
    assert snapshot(project_copy) == before


def test_teaching_scenarios_and_all_course_prompts(project_copy: Path) -> None:
    roadmap = load_yaml(project_copy / "curriculum/roadmap.yml")
    for blueprint in roadmap["training_blueprints"]:
        for mission in blueprint["missions"]:
            teaching = checkpoint_teaching("lab", mission)
            assert any(word in teaching["instruction"] for word in ("示范", "演示", "示例"))
            assert "陌生命令直接完整拆解" in teaching["coach_action"]
            assert "错误预测不是编造证据" in teaching["coach_action"]
            assert "不重复询问配置会不会变化" in teaching["coach_action"]
            assert "不懂时返回讲解与示范" in teaching["coach_action"]
            assert "教练解释不能记成学习者解释" in teaching["coach_action"]
            assert "最后才" not in teaching["instruction"]
            assert "先预测" not in teaching["instruction"]
            assert "不评分" in teaching["hint_policy"]


@pytest.mark.parametrize("missing", [
    "prediction", "learner_action", "observed_result", "interpretation", "handoff",
])
def test_refreshed_summative_rejects_missing_evidence(project_copy: Path, missing: str) -> None:
    ensure_week_plan(project_copy, "2026-W37")
    refresh_teaching(project_copy)
    details = {
        "prediction": "A different query should describe a different layer, not change it.",
        "learner_action": "Selected and executed a read-only query.",
        "observed_result": "The query returned the observed layer information.",
        "interpretation": "The query describes a different layer of the same environment.",
        "handoff": "The layer is verified. No configuration change was requested.",
    }
    details.pop(missing)
    before = snapshot(project_copy)
    with pytest.raises(ValueError, match="requires prediction"):
        record_checkpoint(
            project_copy, "2026-W37-01-mission", "written_handoff", "done", 4,
            "independent attempt", date(2026, 9, 7),
            hint_level_used=0, independent=True, evidence_details=details,
        )
    assert snapshot(project_copy) == before


@pytest.mark.parametrize("week,day", [
    ("2026-W31", date(2026, 7, 29)), ("2026-W37", date(2026, 9, 7)),
])
def test_full_demonstration_cannot_earn_a_formative_score(project_copy, week, day) -> None:
    ensure_week_plan(project_copy, week)
    task_id = f"{week}-0{day.weekday() + 1}-mission"
    before = snapshot(project_copy)
    with pytest.raises(ValueError, match="do not accept a score"):
        record_checkpoint(
            project_copy, task_id, "briefing", "done", 5, "coach demonstration", day,
            hint_level_used=3,
        )
    assert snapshot(project_copy) == before
