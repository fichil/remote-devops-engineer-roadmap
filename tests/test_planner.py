from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from devops_coach.planner import create_today_plan, record_task, weekday_streak
from devops_coach.storage import load_json, write_json


def test_weekday_plan_is_one_75_minute_mission(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    path, created = create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")
    daily = state["daily_plans"][target.isoformat()]
    task = state["tasks"]["2026-07-29-mission"]

    assert created is True
    assert path is not None and path.exists()
    assert daily["planned_minutes"] == 75
    assert daily["task_ids"] == ["2026-07-29-mission"]
    assert task["section"] == "mission"
    assert [item["minutes"] for item in task["checkpoints"]] == [15, 40, 20]
    assert "WSL Recon" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("load_factor", "total", "checkpoints"),
    [(0.8, 60, [10, 35, 15]), (1.0, 75, [15, 40, 20]), (1.1, 80, [15, 45, 20])],
)
def test_load_factor_scales_single_mission(
    project_copy: Path,
    load_factor: float,
    total: int,
    checkpoints: list[int],
) -> None:
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["adaptation"]["load_factor"] = load_factor
    write_json(state_path, state)

    create_today_plan(project_copy, date(2026, 7, 29))
    state = load_json(state_path)
    task = state["tasks"]["2026-07-29-mission"]
    assert task["planned_minutes"] == total
    assert [item["minutes"] for item in task["checkpoints"]] == checkpoints


@pytest.mark.parametrize("target", [date(2026, 8, 1), date(2026, 8, 2)])
def test_new_weekend_call_is_read_only_rest(
    project_copy: Path,
    target: date,
) -> None:
    state_path = project_copy / "state" / "progress.json"
    before = state_path.read_bytes()

    path, created = create_today_plan(project_copy, target)

    assert path is None
    assert created is False
    assert state_path.read_bytes() == before
    assert not (project_copy / "plans" / "2026" / "08" / f"{target.isoformat()}.md").exists()


def test_existing_historical_weekend_plan_is_resumed(project_copy: Path) -> None:
    target = date(2026, 8, 1)
    relative = Path("plans/2026/08/2026-08-01.md")
    historical = project_copy / relative
    historical.parent.mkdir(parents=True)
    historical.write_text("# Historical evidence\n", encoding="utf-8")
    state_path = project_copy / "state" / "progress.json"
    state = load_json(state_path)
    state["daily_plans"][target.isoformat()] = {
        "path": relative.as_posix(),
        "week": 1,
        "phase": "foundations",
        "planned_minutes": 180,
        "task_ids": ["2026-08-01-project"],
        "status": "partial",
    }
    write_json(state_path, state)
    before = state_path.read_bytes()

    path, created = create_today_plan(project_copy, target)

    assert path == historical
    assert created is False
    assert state_path.read_bytes() == before


def test_plan_is_idempotent(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    first_path, first_created = create_today_plan(project_copy, target)
    assert first_path is not None
    first_content = first_path.read_text(encoding="utf-8")
    first_state = (project_copy / "state" / "progress.json").read_bytes()

    second_path, second_created = create_today_plan(project_copy, target)

    assert first_created is True
    assert second_created is False
    assert first_path == second_path
    assert second_path is not None
    assert second_path.read_text(encoding="utf-8") == first_content
    assert (project_copy / "state" / "progress.json").read_bytes() == first_state


@pytest.mark.parametrize(
    ("target", "codename"),
    [
        (date(2026, 7, 29), "WSL Recon"),
        (date(2026, 8, 5), "Wildcard Hunt"),
        (date(2026, 8, 12), "Identity Recon"),
        (date(2026, 8, 19), "Process Recon"),
    ],
)
def test_first_four_weeks_use_curated_missions(
    project_copy: Path,
    target: date,
    codename: str,
) -> None:
    create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")
    assert state["tasks"][f"{target.isoformat()}-mission"]["title"].startswith(codename)


def test_later_weeks_use_five_day_rotation(project_copy: Path) -> None:
    targets = (
        date(2026, 8, 26),
        date(2026, 8, 27),
        date(2026, 8, 28),
        date(2026, 8, 31),
        date(2026, 9, 1),
    )
    expected = ("Recon", "Build", "Incident", "Handoff", "Boss Review")
    for target in targets:
        create_today_plan(project_copy, target)

    state = load_json(project_copy / "state" / "progress.json")
    titles = [state["tasks"][f"{target.isoformat()}-mission"]["title"] for target in targets]
    assert all(title.startswith(codename) for title, codename in zip(titles, expected, strict=True))
    assert state["tasks"]["2026-09-01-mission"]["weekly_review"] is True

    path = project_copy / state["daily_plans"]["2026-08-26"]["path"]
    task = state["tasks"]["2026-08-26-mission"]
    assert task["title"].startswith("Recon")
    assert "Git 本地工作流" in task["title"]
    assert path is not None
    content = path.read_text(encoding="utf-8")
    assert "英文书面交接" in content
    assert "口语、发音或录音证据" in content


def test_record_requires_evidence_and_syncs_daily_status(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    create_today_plan(project_copy, target)
    with pytest.raises(ValueError, match="require evidence"):
        record_task(
            project_copy,
            "2026-07-29-mission",
            "done",
            4,
            15,
            "",
            target,
        )

    partial = record_task(
        project_copy,
        "2026-07-29-mission",
        "partial",
        2,
        15,
        "evidence/week-01/mission.md",
        target,
    )
    state = load_json(project_copy / "state" / "progress.json")
    daily = state["daily_plans"][target.isoformat()]
    assert partial["next_review"] == "2026-07-31"
    assert daily["status"] == "partial"
    assert daily["actual_minutes"] == 15

    record_task(
        project_copy,
        "2026-07-29-mission",
        "done",
        4,
        75,
        "evidence/week-01/mission.md",
        target,
    )
    daily = load_json(project_copy / "state" / "progress.json")["daily_plans"][
        target.isoformat()
    ]
    assert daily["status"] == "done"
    assert daily["actual_minutes"] == 75


def test_weekday_streak_counts_evidenced_partial_and_skips_weekend(
    project_copy: Path,
) -> None:
    for target in (date(2026, 7, 31), date(2026, 8, 3)):
        create_today_plan(project_copy, target)
        record_task(
            project_copy,
            f"{target.isoformat()}-mission",
            "partial",
            2,
            15,
            f"evidence/{target.isoformat()}.md",
            target,
        )

    state = load_json(project_copy / "state" / "progress.json")
    assert weekday_streak(state, date(2026, 7, 29), date(2026, 8, 3), 15) == (2, 2)

    target = date(2026, 8, 5)
    create_today_plan(project_copy, target)
    record_task(
        project_copy,
        "2026-08-05-mission",
        "partial",
        2,
        15,
        "evidence/2026-08-05.md",
        target,
    )
    state = load_json(project_copy / "state" / "progress.json")
    assert weekday_streak(state, date(2026, 7, 29), target, 15) == (1, 2)


def test_streak_requires_both_minimum_minutes_and_evidence(project_copy: Path) -> None:
    target = date(2026, 7, 29)
    create_today_plan(project_copy, target)
    record_task(project_copy, "2026-07-29-mission", "partial", 2, 14, "proof", target)
    state = load_json(project_copy / "state" / "progress.json")
    assert weekday_streak(state, target, target, 15) == (0, 0)

    record_task(project_copy, "2026-07-29-mission", "partial", 2, 15, "", target)
    state = load_json(project_copy / "state" / "progress.json")
    assert weekday_streak(state, target, target, 15) == (0, 0)


def test_route_extends_at_week_78_instead_of_lowering_gate(project_copy: Path) -> None:
    target = date(2026, 7, 29) + timedelta(weeks=80)
    path, created = create_today_plan(project_copy, target)
    state = load_json(project_copy / "state" / "progress.json")

    assert created is True
    assert path is not None and path.exists()
    assert state["daily_plans"][target.isoformat()]["week"] == 78
    assert "最终能力门槛" in path.read_text(encoding="utf-8")
