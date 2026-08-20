from __future__ import annotations

from pathlib import Path

import pytest

from devops_coach.cli import main


def test_today_cli_reports_weekend_rest_without_writing(
    project_copy: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_path = project_copy / "state" / "progress.json"
    before = state_path.read_bytes()

    result = main(
        [
            "--root",
            str(project_copy),
            "today",
            "--date",
            "2026-08-01",
        ]
    )

    assert result == 0
    assert "Rest day: no learning plan scheduled for 2026-08-01" in capsys.readouterr().out
    assert state_path.read_bytes() == before
