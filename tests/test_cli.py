from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_coach.cli import build_parser, main


def test_today_cli_prints_three_layer_overview(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["--root", str(project_copy), "today", "--date", "2026-08-21"])
    output = capsys.readouterr().out

    assert result == 0
    assert "总项目" in output
    assert "本周" in output
    assert "今天" in output
    assert "第 4/78 周" in output
    assert "今日计划任务" in output
    assert "预计时间" not in output
    assert "分钟" not in output


def test_today_cli_json_contains_project_week_and_today(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "--root",
            str(project_copy),
            "today",
            "--date",
            "2026-08-21",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["schema_version"] == 2
    assert set(payload) == {"schema_version", "project", "week", "today"}
    assert payload["project"]["calendar_week"] == 4
    assert len(payload["week"]["new_missions"]) == 5
    assert payload["today"]["quota"] == 1
    assert payload["today"]["active_task_kind"] == "primary"
    assert payload["today"]["optional_carryover_limit"] is None
    assert payload["today"]["optional_carryover_completed_count"] == 0
    assert payload["today"]["optional_carryover_completed_task_ids"] == []
    assert payload["today"]["next_checkpoint"]


def test_today_cli_accepts_explicit_carryover_flag() -> None:
    args = build_parser().parse_args(["today", "--continue-carryover"])
    assert args.continue_carryover is True


def test_publish_cli_requires_task_for_specific_carryover(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "--root",
            str(project_copy),
            "publish",
            "--date",
            "2026-07-29",
            "--kind",
            "carryover",
            "--dry-run",
        ]
    )

    assert result == 2
    assert "--task is required" in capsys.readouterr().err

    args = build_parser().parse_args(
        [
            "publish",
            "--date",
            "2026-07-29",
            "--kind",
            "carryover",
            "--task",
            "old-1",
            "--dry-run",
        ]
    )
    assert args.task == "old-1"

    result = main(
        [
            "--root",
            str(project_copy),
            "publish",
            "--recover",
            "--task",
            "old-1",
        ]
    )
    assert result == 2
    assert "--kind carryover" in capsys.readouterr().err


def test_today_cli_reports_weekend_rest_without_writing(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = project_copy / "state" / "progress.json"
    before = state_path.read_bytes()

    result = main(["--root", str(project_copy), "today", "--date", "2026-08-01"])
    output = capsys.readouterr().out

    assert result == 0
    assert "周末休息日" in output
    assert state_path.read_bytes() == before


def test_record_interface_requires_checkpoint_and_has_no_minutes_option() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "record",
                "--task",
                "task-1",
                "--checkpoint",
                "lab",
                "--status",
                "done",
                "--score",
                "4",
                "--evidence",
                "proof",
                "--minutes",
                "15",
            ]
        )


def test_record_accepts_repeatable_artifacts_and_publish_modes() -> None:
    parser = build_parser()
    record = parser.parse_args(
        [
            "record",
            "--task",
            "task-1",
            "--checkpoint",
            "lab",
            "--status",
            "done",
            "--score",
            "4",
            "--evidence",
            "proof",
            "--artifact",
            "evidence/one.txt",
            "--artifact",
            "evidence/two.txt",
        ]
    )
    recovery = parser.parse_args(["publish", "--recover", "--json"])
    dry_run = parser.parse_args(
        ["publish", "--date", "2026-08-24", "--kind", "primary", "--dry-run"]
    )

    assert record.artifact == ["evidence/one.txt", "evidence/two.txt"]
    assert recovery.recover is True
    assert recovery.date is None
    assert dry_run.dry_run is True
    assert dry_run.kind == "primary"


def test_record_accepts_cognitive_evidence_without_requiring_score() -> None:
    args = build_parser().parse_args(
        [
            "record",
            "--task",
            "task-1",
            "--checkpoint",
            "lab",
            "--status",
            "done",
            "--evidence",
            "guided evidence",
            "--hint-level",
            "2",
            "--prediction",
            "expected result",
            "--learner-action",
            "learner command",
            "--observed-result",
            "actual result",
            "--interpretation",
            "why it happened",
            "--handoff",
            "Ready for review.",
        ]
    )

    assert args.score is None
    assert args.hint_level == 2
    assert args.independent is False
    assert args.observed_result == "actual result"


def test_record_cli_passes_structured_cognitive_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_record(*args: object, **kwargs: object) -> dict[str, object]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"id": "task-1", "status": "in_progress"}

    monkeypatch.setattr("devops_coach.cli.record_checkpoint", fake_record)
    result = main(
        [
            "--root",
            str(tmp_path),
            "record",
            "--task",
            "task-1",
            "--checkpoint",
            "written_handoff",
            "--status",
            "in_progress",
            "--score",
            "4",
            "--evidence",
            "structured proof",
            "--hint-level",
            "0",
            "--independent",
            "--prediction",
            "prediction",
            "--learner-action",
            "action",
            "--observed-result",
            "result",
            "--interpretation",
            "interpretation",
            "--handoff",
            "handoff",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out)["task"]["id"] == "task-1"
    assert captured["kwargs"] == {
        "artifacts": [],
        "hint_level_used": 0,
        "independent": True,
        "evidence_details": {
            "prediction": "prediction",
            "learner_action": "action",
            "observed_result": "result",
            "interpretation": "interpretation",
            "handoff": "handoff",
        },
    }


def test_migrate_cli_dry_run_is_json_and_read_only(
    migration_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = migration_project / "state" / "progress.json"
    before = state_path.read_bytes()

    result = main(
        [
            "--root",
            str(migration_project),
            "migrate",
            "--to-schema",
            "2",
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dry_run"] is True
    assert state_path.read_bytes() == before


def test_migrate_targets_are_mutually_exclusive() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "migrate",
                "--to-schema",
                "2",
                "--to-training",
                "cognitive_apprenticeship_v1",
            ]
        )


def test_training_migrate_cli_dispatches_selected_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_migration(root: Path, dry_run: bool = False) -> dict[str, object]:
        captured.update({"root": root, "dry_run": dry_run})
        return {
            "changed": False,
            "dry_run": dry_run,
            "workflow_version": "cognitive_apprenticeship_v1",
        }

    monkeypatch.setattr("devops_coach.cli.migrate_to_training_workflow", fake_migration)
    result = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "--to-training",
            "cognitive_apprenticeship_v1",
            "--dry-run",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert captured == {"root": tmp_path.resolve(), "dry_run": True}
    assert payload["workflow_version"] == "cognitive_apprenticeship_v1"


def test_lab_status_cli_reports_missing_lab_as_json(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(
        [
            "--root",
            str(project_copy),
            "lab",
            "status",
            "--week",
            "2026-W36",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["status"] == "missing"
    assert payload["week"] == "2026-W36"


def test_lab_reproduce_cli_accepts_explicit_date() -> None:
    args = build_parser().parse_args(
        ["lab", "reproduce", "--week", "2026-W36", "--date", "2026-09-04"]
    )

    assert args.week == "2026-W36"
    assert args.date.isoformat() == "2026-09-04"
