from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from devops_coach.lab import prepare_friday_reproduction, prepare_week_lab, week_lab_status
from devops_coach.migration import (
    COGNITIVE_WORKFLOW_VERSION,
    migrate_to_schema_2,
    migrate_to_training_workflow,
    refresh_teaching,
)
from devops_coach.planner import (
    ensure_master_plan,
    ensure_week_plan,
    project_summary,
    record_checkpoint,
    render_today_text,
    today_overview,
)
from devops_coach.publication import (
    PublicationError,
    publish_completed_task,
    recover_publications,
)
from devops_coach.review import review_week
from devops_coach.storage import load_json, load_yaml, project_root
from devops_coach.validation import validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devops-coach", description="Evidence-based DevOps coach")
    parser.add_argument("--root", type=Path, default=project_root(), help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate", help="Migrate active data")
    migrate_target = migrate_parser.add_mutually_exclusive_group(required=True)
    migrate_target.add_argument("--to-schema", type=int, choices=(2,))
    migrate_target.add_argument(
        "--to-training",
        choices=(COGNITIVE_WORKFLOW_VERSION,),
        help="Migrate active missions to the cognitive-apprenticeship workflow",
    )
    migrate_target.add_argument(
        "--refresh-teaching", action="store_true",
        help="Refresh unfinished teaching text without changing evidence or assessments",
    )
    migrate_parser.add_argument("--dry-run", action="store_true")

    lab_parser = subparsers.add_parser("lab", help="Prepare or inspect a local weekly lab")
    lab_subparsers = lab_parser.add_subparsers(dest="lab_action", required=True)
    for action in ("prepare", "status", "reproduce"):
        action_parser = lab_subparsers.add_parser(action)
        action_parser.add_argument("--week", required=True)
        action_parser.add_argument("--json", action="store_true")
        if action == "reproduce":
            action_parser.add_argument("--date", type=date.fromisoformat, default=date.today())

    plan_parser = subparsers.add_parser("plan", help="Generate durable planning documents")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_kind", required=True)
    plan_subparsers.add_parser("master", help="Generate the 78-week master plan")
    week_parser = plan_subparsers.add_parser("week", help="Generate or resume one week")
    week_parser.add_argument("--week", required=True)

    today_parser = subparsers.add_parser("today", help="Show project, week, and today")
    today_parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    today_parser.add_argument(
        "--continue-carryover",
        action="store_true",
        help="After today's primary task, explicitly start the oldest carryover",
    )
    today_parser.add_argument("--json", action="store_true")

    record_parser = subparsers.add_parser("record", help="Record one verified checkpoint")
    record_parser.add_argument("--task", required=True)
    record_parser.add_argument("--checkpoint", required=True)
    record_parser.add_argument(
        "--status", choices=("in_progress", "done", "blocked"), required=True
    )
    record_parser.add_argument("--score", type=int, choices=range(0, 6))
    record_parser.add_argument("--evidence", required=True)
    record_parser.add_argument("--hint-level", type=int, choices=range(0, 4))
    record_parser.add_argument("--independent", action="store_true")
    record_parser.add_argument("--prediction")
    record_parser.add_argument("--learner-action")
    record_parser.add_argument("--observed-result")
    record_parser.add_argument("--interpretation")
    record_parser.add_argument("--handoff")
    record_parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Repository-contained evidence file; repeat for multiple artifacts",
    )

    publish_parser = subparsers.add_parser(
        "publish", help="Publish an evidence-complete task through a Ready PR"
    )
    publish_parser.add_argument("--date", type=date.fromisoformat)
    publish_parser.add_argument("--kind", choices=("primary", "carryover"))
    publish_parser.add_argument(
        "--task", help="Required task id for a specific carryover publication"
    )
    publish_mode = publish_parser.add_mutually_exclusive_group(required=True)
    publish_mode.add_argument("--dry-run", action="store_true")
    publish_mode.add_argument("--apply", action="store_true")
    publish_mode.add_argument("--recover", action="store_true")
    publish_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("review", help="Write a review into the weekly plan")
    review_parser.add_argument("--week", default=date.today().strftime("%G-W%V"))

    subparsers.add_parser("status", help="Show current structured progress")
    subparsers.add_parser("validate", help="Validate schemas, roadmap, and planning sync")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "migrate":
        if args.refresh_teaching:
            summary = refresh_teaching(root, dry_run=args.dry_run)
        elif args.to_training:
            summary = migrate_to_training_workflow(root, dry_run=args.dry_run)
        else:
            summary = migrate_to_schema_2(root, dry_run=args.dry_run)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "lab":
        if args.lab_action == "prepare":
            payload = prepare_week_lab(root, args.week)
        elif args.lab_action == "status":
            payload = week_lab_status(root, args.week)
        else:
            payload = prepare_friday_reproduction(root, args.week, args.date)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"Lab {payload['status']}: {payload['week']} "
                f"({payload.get('lab_root', 'unknown path')})"
            )
        return 0
    if args.command == "plan":
        if args.plan_kind == "master":
            path, created = ensure_master_plan(root)
        else:
            path, created = ensure_week_plan(root, args.week)
        print(f"{'Created' if created else 'Resuming'}: {path}")
        return 0
    if args.command == "today":
        overview = today_overview(root, args.date, args.continue_carryover)
        if args.json:
            print(json.dumps(overview, ensure_ascii=False, indent=2))
        else:
            print(render_today_text(overview))
        return 0
    if args.command == "record":
        task = record_checkpoint(
            root,
            args.task,
            args.checkpoint,
            args.status,
            args.score,
            args.evidence,
            artifacts=args.artifact,
            hint_level_used=args.hint_level,
            independent=args.independent,
            evidence_details={
                "prediction": args.prediction,
                "learner_action": args.learner_action,
                "observed_result": args.observed_result,
                "interpretation": args.interpretation,
                "handoff": args.handoff,
            },
        )
        payload: dict[str, object] = {"task": task}
        if task["status"] == "done":
            progress = load_json(root / "state" / "progress.json")
            completed = next(
                item
                for item in progress["completion_log"]
                if item["task_id"] == task["id"] and item["date"] == date.today().isoformat()
            )
            try:
                payload["publication"] = publish_completed_task(
                    root,
                    date.today(),
                    completed["kind"],
                    apply=True,
                    task_id=(
                        completed["task_id"]
                        if completed["kind"] == "carryover"
                        else None
                    ),
                )
            except PublicationError as exc:
                payload["publication"] = {
                    "status": "pending_recovery",
                    "error": str(exc),
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 1
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "publish":
        if args.task and args.kind != "carryover":
            print("--task is only valid with --kind carryover", file=sys.stderr)
            return 2
        try:
            if args.recover:
                results = recover_publications(
                    root, target=args.date, kind=args.kind, task_id=args.task
                )
                payload = {"status": "complete", "recovered": results}
            else:
                if args.date is None or args.kind is None:
                    print(
                        "--date and --kind are required with --dry-run or --apply",
                        file=sys.stderr,
                    )
                    return 2
                if args.kind == "carryover" and not args.task:
                    print("--task is required for a carryover publication", file=sys.stderr)
                    return 2
                payload = publish_completed_task(
                    root,
                    args.date,
                    args.kind,
                    apply=args.apply,
                    task_id=args.task,
                )
        except PublicationError as exc:
            payload = {"status": "blocked", "error": str(exc)}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"Publication blocked: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "review":
        path, summary = review_week(root, args.week)
        print(f"Review updated: {path}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        progress = load_json(root / "state" / "progress.json")
        learner = load_yaml(root / "config" / "learner.yml")
        summary = project_summary(learner, progress, date.today())
        summary["blockers"] = progress["blockers"]
        summary["adaptation"] = progress["adaptation"]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate":
        errors = validate_project(root)
        if errors:
            print("Validation failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print(
            "Validation passed: schema v2, 78-week coverage, task quotas, "
            "and planning sync are valid."
        )
        return 0
    return 2
