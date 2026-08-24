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
    assert payload["today"]["optional_carryover_limit"] == 1
    assert payload["today"]["next_checkpoint"]


def test_today_cli_accepts_explicit_carryover_flag() -> None:
    args = build_parser().parse_args(["today", "--continue-carryover"])
    assert args.continue_carryover is True


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
