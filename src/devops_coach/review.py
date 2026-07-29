from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from devops_coach.storage import load_json, write_json, write_text


def parse_iso_week(value: str) -> tuple[int, int]:
    try:
        year_text, week_text = value.split("-W", maxsplit=1)
        year, week = int(year_text), int(week_text)
        date.fromisocalendar(year, week, 1)
        return year, week
    except (ValueError, TypeError) as exc:
        raise ValueError("Week must use YYYY-Www, for example 2026-W31") from exc


def review_week(root: Path, week_value: str) -> tuple[Path, dict[str, Any]]:
    year, week = parse_iso_week(week_value)
    progress_path = root / "state" / "progress.json"
    progress = load_json(progress_path)
    tasks = [
        task
        for task in progress["tasks"].values()
        if date.fromisoformat(task["date"]).isocalendar()[:2] == (year, week)
    ]
    done = [task for task in tasks if task["status"] == "done"]
    scored = [task["score"] for task in tasks if task["score"] is not None]
    completion = len(done) / len(tasks) if tasks else 0.0
    mean_score = sum(scored) / len(scored) if scored else 0.0
    blockers = [task["id"] for task in tasks if task["status"] == "blocked"]

    if completion < 0.70:
        factor, reason = 0.8, "完成率低于 70%，下周减载 20%"
    elif completion > 0.90 and mean_score >= 4 and not blockers:
        factor, reason = 1.1, "完成率超过 90%、掌握度达标且无阻塞，下周加速 10%"
    else:
        factor, reason = 1.0, "进度处于可持续区间，保持负载"

    carryover_actions: list[dict[str, str]] = []
    for task in tasks:
        if task["status"] == "done":
            continue
        if task.get("carryovers", 0) == 0:
            task["carryovers"] = 1
            task["adaptation_action"] = "roll_over"
            action = "顺延一次"
        else:
            task["adaptation_action"] = "split_and_reteach"
            action = "拆小并先处理阻塞"
        carryover_actions.append({"task": task["id"], "action": action})

    summary = {
        "week": week_value,
        "task_count": len(tasks),
        "done_count": len(done),
        "completion_rate": round(completion, 4),
        "mean_score": round(mean_score, 2),
        "blockers": blockers,
        "load_factor": factor,
        "reason": reason,
        "carryover_actions": carryover_actions,
    }
    progress["adaptation"] = {
        "load_factor": factor,
        "reason": reason,
        "source_week": week_value,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    progress["weekly_reviews"][week_value] = summary
    progress["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(progress_path, progress)

    review_path = root / "reviews" / f"{week_value}.md"
    lines = [
        f"# {week_value} 周复盘",
        "",
        f"- 完成：{len(done)}/{len(tasks)}（{completion:.0%}）",
        f"- 平均掌握度：{mean_score:.2f}/5",
        f"- 阻塞项：{', '.join(blockers) if blockers else '无'}",
        f"- 下周负载：{factor:.1f}（{reason}）",
        "",
        "## 未完成任务处理",
        "",
    ]
    if carryover_actions:
        lines.extend(f"- `{item['task']}`：{item['action']}" for item in carryover_actions)
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 教练问题",
            "",
            "1. 本周哪项证据最能证明你真正掌握了技能？",
            "2. 最大阻塞来自知识、时间、环境还是任务过大？",
            "3. 下周必须保留的一项英语输出是什么？",
        ]
    )
    write_text(review_path, "\n".join(lines))
    return review_path, summary
