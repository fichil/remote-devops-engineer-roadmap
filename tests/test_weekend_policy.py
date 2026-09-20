"""Policy checks independent of filesystem fixtures or Git availability."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from devops_coach import planner
from devops_coach.publication import PublicationError, _eligible_completion
from devops_coach.publication_scope import validate_state_scope


def _state():
    return {
        "tasks": {
            "old": {
                "id": "old", "title": "Old task", "status": "in_progress",
                "scheduled_for": "2026-07-31", "created_on": "2026-07-31", "queue_order": 1,
                "carryover_activated_on": "2026-08-02",
                "checkpoints": [{"id": "work", "status": "in_progress", "evidence": None}],
            }
        },
        "weekly_plans": {}, "completion_log": [], "current_week": 1,
        "current_phase": "foundations", "updated_at": "unchanged",
    }


@pytest.mark.parametrize("target", [date(2026, 8, 1), date(2026, 8, 2)])
def test_weekend_policy_needs_explicit_oldest_but_no_primary(target):
    state = _state()
    state["tasks"]["old"]["carryover_activated_on"] = target.isoformat()
    assert planner._recording_kind(state, "old", target, None) == ("carryover", None)
    with pytest.raises(ValueError, match="oldest"):
        planner._recording_kind(state, "another", target, None)
    state["tasks"]["old"]["carryover_activated_on"] = None
    with pytest.raises(ValueError, match="continue-carryover"):
        planner._recording_kind(state, "old", target, None)


def test_historical_migration_entries_are_not_new_publication_requests(monkeypatch):
    state = _state()
    state["completion_log"] = [
        {"date": "2026-07-29", "task_id": "legacy-v1"},
        {"date": "2026-07-31", "task_id": "primary", "kind": "primary"},
    ]
    calls = []

    def is_complete(root, target, kind, task_id):
        calls.append((target, kind, task_id))
        return False

    monkeypatch.setattr(planner, "publication_is_complete", is_complete)
    assert planner._all_pending_publication_task_ids(Path("."), state, date(2026, 8, 2)) == [
        "primary"
    ]
    assert calls == [(date(2026, 7, 31), "primary", "primary")]


def test_weekend_publication_and_scope_without_creating_a_week():
    before = _state()
    after = deepcopy(before)
    task = after["tasks"]["old"]
    task.update(status="done", completed_on="2026-08-02", score=3, evidence="Verified")
    task["checkpoints"][0].update(status="done", score=3, evidence="Verified")
    completion = {"task_id": "old", "date": "2026-08-02", "kind": "carryover"}
    after["completion_log"].append(completion)
    target = date(2026, 8, 2)
    assert _eligible_completion(after, target, "carryover", "old") == (completion, task)
    validate_state_scope(Path("."), before, after, "old", target, completion)
    with pytest.raises(PublicationError, match="Weekend publications"):
        _eligible_completion(after, target, "primary", "old")
    task["carryover_activated_on"] = None
    with pytest.raises(PublicationError, match="activation"):
        _eligible_completion(after, target, "carryover", "old")
    task["carryover_activated_on"] = target.isoformat()
    task["checkpoints"][0]["evidence"] = None
    with pytest.raises(PublicationError, match="evidence"):
        _eligible_completion(after, target, "carryover", "old")
    after["current_week"] = 2
    with pytest.raises(ValueError, match="current_week"):
        validate_state_scope(Path("."), before, after, "old", target, completion)


@pytest.mark.parametrize(
    ("target", "friday_complete", "expected"),
    [
        (date(2026, 9, 18), False, (1, 1)),
        (date(2026, 9, 19), False, (0, 1)),
        (date(2026, 9, 20), False, (0, 1)),
        (date(2026, 9, 21), False, (0, 1)),
        (date(2026, 9, 19), True, (2, 2)),
        (date(2026, 9, 20), True, (2, 2)),
        (date(2026, 9, 21), True, (2, 2)),
    ],
)
def test_weekend_streak_cannot_grant_grace_to_a_missed_friday(
    target, friday_complete, expected
):
    completed_dates = ["2026-09-17"]
    if friday_complete:
        completed_dates.append("2026-09-18")
    state = {"tasks": {}, "completion_log": []}
    for completed_on in completed_dates:
        state["tasks"][completed_on] = {
            "id": completed_on, "status": "done", "scheduled_for": completed_on,
            "evidence": "Verified evidence",
            "checkpoints": [{"status": "done", "evidence": "Verified evidence"}],
        }
        state["completion_log"].append({
            "date": completed_on, "task_id": completed_on,
            "kind": "primary", "evidence": "Verified evidence",
        })
    assert planner.completion_streak(state, date(2026, 9, 17), target) == expected
