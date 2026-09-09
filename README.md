# Remote DevOps Engineer Roadmap

[简体中文](README.zh-CN.md)

An open-source, evidence-based Codex coach for a beginner working toward an overseas remote DevOps role through a 78-week route.

This repository is not a link list or a promise of employment. It combines a competency roadmap, one complete weekday operations mission, verified evidence, content-based weekly adaptation, progressive technical English, portfolio gates, and a bridge into real operations experience.

## Who this is for

The included learner profile assumes:

- a beginner in IT and approximately A2 English;
- Monday through Friday learning, with complete weekend rest;
- AWS as the primary cloud track;
- a monthly learning and cloud budget of at most USD 20;
- overseas employee and long-term contractor roles as valid outcomes;
- junior operations, cloud support, and open-source contribution as experience bridges.

Remote DevOps roles commonly combine Linux, cloud infrastructure, Terraform, containers, CI/CD, observability, incident response, and strong written communication. The roadmap targets job readiness and a credible opportunity pipeline; it does not guarantee a job offer.

## What the coach does

- Maintains a human-readable [78-week master plan](plans/master-plan.md) and one living plan per calendar week.
- Creates five new missions for each Monday–Friday week and keeps each mission assigned to its scheduled workday.
- Starts today's scheduled mission first. After it is complete and published, each explicit continue request starts one oldest carryover; the learner may repeat this without a daily carryover limit.
- Uses cognitive apprenticeship: explanation and demonstration, guided practice, then an independently scored transfer and delivery.
- Treats copied commands and raw output as guided evidence only; mastery requires a learner-authored action, prediction, observed result, and interpretation.
- Schedules weak skills for reteaching or retrieval and adapts content without changing the daily task quantity.
- Counts a weekday streak only when a complete mission has evidence; weekends are skipped and missed weekdays break the streak.
- Advances calendar topics every week, while unmet phase gates replace next-phase work with remediation or retesting.
- Assesses routine English through reading and writing only. General speaking and pronunciation stay in Duolingo; roadmap technical demos and mock interviews remain in scope.
- Keeps private application, company, income, and contact data outside Git.
- Automatically publishes only evidence-complete tasks through a Ready PR, required CI, and a verified squash merge. The phrase `完成并发布今日记录` remains a manual recovery command.

## Quick start

Requirements: Python 3.11 or later and Git.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m devops_coach migrate --to-schema 2 --dry-run
python -m devops_coach migrate --to-schema 2
python -m devops_coach plan master
python -m devops_coach validate
python -m devops_coach today
```

Migration is idempotent. An existing schema-v1 progress file is archived byte-for-byte at `state/archive/progress-v1.json`; historical daily plans are not rewritten. New planning uses `plans/master-plan.md` and `plans/weeks/YYYY-Www.md` and does not create daily Markdown files.

## CLI

```text
python -m devops_coach migrate --to-schema 2 [--dry-run]
python -m devops_coach migrate --to-training cognitive_apprenticeship_v1 [--dry-run]
python -m devops_coach migrate --refresh-teaching [--dry-run]
python -m devops_coach plan master
python -m devops_coach plan week --week YYYY-Www
python -m devops_coach today [--date YYYY-MM-DD] [--continue-carryover] [--json]
python -m devops_coach record --task ID --checkpoint ID --status in_progress|done|blocked [--score 0..5] --evidence TEXT [--hint-level 0..3] [--independent] [--prediction TEXT --learner-action TEXT --observed-result TEXT --interpretation TEXT --handoff TEXT] [--artifact PATH ...]
python -m devops_coach lab prepare|status|reproduce --week YYYY-Www [--date YYYY-MM-DD] [--json]
python -m devops_coach publish --date YYYY-MM-DD --kind primary --dry-run|--apply [--json]
python -m devops_coach publish --date YYYY-MM-DD --kind carryover --task ID --dry-run|--apply [--json]
python -m devops_coach publish --recover [--date YYYY-MM-DD] [--kind primary] [--json]
python -m devops_coach publish --recover [--date YYYY-MM-DD] [--kind carryover [--task ID]] [--json]
python -m devops_coach review [--week YYYY-Www]
python -m devops_coach status
python -m devops_coach validate
```

Example checkpoint update:

```powershell
python -m devops_coach record `
  --task TASK-ID `
  --checkpoint briefing `
  --status done `
  --hint-level 1 `
  --evidence "Verified learner-authored explanation after a demonstration" `
  --artifact evidence/week-05/git/briefing.md
```

For teaching-only maintenance, see [Teaching refresh](docs/teaching-refresh.md). Preview first; raw state is backed up before changes. Completed work, in-progress evidence, scores, hints, review dates, and completion records remain unchanged. This maintenance is not authorized by daily learning publication.

## Cognitive apprenticeship

- **Explanation and demonstration:** teach the purpose, object relationships, and an example first; fully explain unfamiliar commands. Use at most one meaningful question per concept block, or assess understanding through a post-operation explanation. This stage is formative and unscored.
- **Guided practice:** after a demonstration, the learner runs the explained action and interprets real results. Fade hints only for previously taught content. Use predictions for meaningful outcome differences, scope choices, or fault hypotheses, not exact unknown versions. A wrong prediction can be corrected through safe observation; never invent observations or attribute a coach's explanation to the learner. Ordinary queries need no repeated configuration-change quiz; explain concrete side effects upfront. Return to explanation when the learner does not understand.
- **Independent transfer and delivery:** the learner handles a changed condition without the complete command, explains the evidence, and writes a short authentic English PR comment or handoff. This is the only scored stage.

Each week uses one ignored local project under `private/labs/YYYY-Www/`. Monday through Thursday share its working clone; Friday reproduces the outcome from a fresh clone of a local bare remote. GitHub learning is local-first and read-only by default; it never uses this learning-system checkout as the practice repository.

## Weekday mission contract

| Day | Required quota | Optional carryover | Required checkpoints |
|---|---:|---:|---|
| Monday–Friday | 1 scheduled mission | Unlimited; one oldest task per explicit continue request and separate publication | Explanation and demonstration, guided practice, independent transfer and delivery |
| Saturday–Sunday | Rest | None | No generation, rescheduling, or backfill |

All carryovers are shown, but they never displace today's scheduled mission. After the primary mission is complete and published, the coach stops by default. The learner can explicitly request one oldest carryover with `python -m devops_coach today --continue-carryover`; after that task is separately published, another explicit request may start the next one. There is no daily carryover count limit, and every completion on the same date still counts as one streak workday.

The project contains six phases: foundations, systems automation, containers and CI/CD, AWS and Terraform, Kubernetes and SRE, and a production capstone with the global job search. Every phase ends with an evidence gate. If evidence is insufficient, the route extends; gates are never lowered to preserve the nominal end date.

## Cost and privacy boundaries

Before creating a potentially billable AWS resource, the coach must provide a cost estimate, verify a budget alarm, receive explicit approval, and include a teardown command. Persistent EKS is outside the USD 20 monthly budget; Kubernetes practice uses a local cluster by default.

The entire `private/` directory is ignored. Public learning logs must not contain credentials, private keys, personal email addresses, employer data, internal hostnames, private repository names, or unredacted local paths. Run the scanner before publication:

```powershell
python scripts/privacy_scan.py
```

## Codex scheduled coaching

One weekday coach runs at 09:00 in `Asia/Shanghai`. There is no weekend automation or synthetic backfill. It may assess English reading and writing, but not general speaking, pronunciation, or recording practice. See [Codex automation setup](docs/codex-automation.md).

## Contributing

Curriculum fixes, accessible beginner explanations, deterministic tests, and privacy-safe labs are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [PRIVACY.md](PRIVACY.md) before opening a pull request.

## License

MIT. See [LICENSE](LICENSE).
