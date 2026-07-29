from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from devops_coach.planner import create_today_plan, record_task
from devops_coach.review import review_week
from devops_coach.storage import load_json, project_root
from devops_coach.validation import validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devops-coach", description="Evidence-based DevOps coach")
    parser.add_argument("--root", type=Path, default=project_root(), help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    today_parser = subparsers.add_parser("today", help="Create or resume today's plan")
    today_parser.add_argument("--date", type=date.fromisoformat, default=date.today())

    record_parser = subparsers.add_parser("record", help="Record verified task progress")
    record_parser.add_argument("--task", required=True)
    record_parser.add_argument("--status", choices=("done", "partial", "blocked"), required=True)
    record_parser.add_argument("--score", type=int, choices=range(0, 6), required=True)
    record_parser.add_argument("--minutes", type=int, required=True)
    record_parser.add_argument("--evidence", default="")

    review_parser = subparsers.add_parser("review", help="Create a weekly review")
    review_parser.add_argument("--week", default=date.today().strftime("%G-W%V"))

    subparsers.add_parser("status", help="Show current learning state")
    subparsers.add_parser("validate", help="Validate schemas and roadmap semantics")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "today":
        path, created = create_today_plan(root, args.date)
        verb = "Created" if created else "Resuming"
        print(f"{verb}: {path}")
        return 0
    if args.command == "record":
        task = record_task(
            root,
            args.task,
            args.status,
            args.score,
            args.minutes,
            args.evidence,
        )
        print(json.dumps(task, ensure_ascii=False, indent=2))
        return 0
    if args.command == "review":
        path, summary = review_week(root, args.week)
        print(f"Review: {path}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        progress = load_json(root / "state" / "progress.json")
        summary = {
            "current_week": progress["current_week"],
            "current_phase": progress["current_phase"],
            "plans": len(progress["daily_plans"]),
            "tasks": len(progress["tasks"]),
            "blockers": progress["blockers"],
            "adaptation": progress["adaptation"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate":
        errors = validate_project(root)
        if errors:
            print("Validation failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Validation passed: schemas, 78-week coverage, and time budgets are valid.")
        return 0
    return 2
