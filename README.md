# Remote DevOps Engineer Roadmap

[简体中文](README.zh-CN.md)

An open-source, evidence-based Codex coach for a beginner working toward an overseas remote DevOps role in 18 months.

This repository is not a list of links or a promise of employment. It combines a 78-week competency map, daily time-boxed practice, verified evidence, weekly adaptation, progressive technical English, portfolio gates, and a bridge into real operations experience.

## Who this is for

The included learner profile assumes:

- a beginner in IT and approximately A2 English;
- 10–12 sustainable hours per week;
- AWS as the primary cloud track;
- a monthly learning and cloud budget of at most USD 20;
- overseas employee and long-term contractor roles as valid outcomes;
- junior operations, cloud support, and open-source contribution as experience bridges.

Remote DevOps roles commonly combine Linux, cloud infrastructure, Terraform, containers, CI/CD, observability, incident response, and strong written communication. Many current roles also ask for several years of production experience. The roadmap therefore targets job readiness and a credible opportunity pipeline; it does not guarantee a job.

## What the coach does

- Generates or resumes one idempotent plan for a date.
- Preserves a single machine-readable progress state.
- Requires command output, code, tests, a runbook, or a demo before marking work complete.
- Schedules weak skills for review after two or seven days.
- Reduces, preserves, or increases the next week's load based on completion and mastery.
- Keeps at least 25% of learning time in English, including English project documentation.
- Keeps private application, company, income, and contact data outside Git.
- Never pushes daily progress until the learner explicitly says `完成并发布今日记录`.

## Quick start

Requirements: Python 3.11 or later and Git.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m devops_coach validate
python -m devops_coach today
```

Then open the generated plan under `plans/` or tell Codex:

```text
开始今天学习
```

The durable coaching rules are in [`AGENTS.md`](AGENTS.md). The learner-safe public settings are in [`config/learner.yml`](config/learner.yml); copy [`config/learner.example.yml`](config/learner.example.yml) when adapting the project.

## CLI

```text
python -m devops_coach today [--date YYYY-MM-DD]
python -m devops_coach record --task ID --status done|partial|blocked --score 0..5 --minutes N --evidence PATH
python -m devops_coach review [--week YYYY-Www]
python -m devops_coach status
python -m devops_coach validate
```

Example evidence update:

```powershell
python -m devops_coach record `
  --task 2026-07-29-practice `
  --status done `
  --score 4 `
  --minutes 25 `
  --evidence evidence/week-01/wsl-environment.md
```

## Weekly schedule

| Day | English | Technical or project work | Review | Total |
|---|---:|---:|---:|---:|
| Monday–Friday | 20 min | 45 min | 10 min | 75 min |
| Saturday | 30 min + 15 min English README | 120 min project work | 15 min | 180 min |
| Sunday | 30 min | 45 min retrieval | 45 min review and planning | 120 min |

The weekday coach starts automatically at 09:00. English reading and writing may be included, but reading aloud, recording, and spoken-English output are deferred to a manual session after 18:00 in `Asia/Shanghai`.

The project contains six 13-week phases: foundations, systems automation, containers and CI/CD, AWS and Terraform, Kubernetes and SRE, and a production capstone with the global job search. Every phase ends with a runnable public artifact, bilingual documentation, an English demo, and an evidence gate.

## Cost and privacy boundaries

Before creating a potentially billable AWS resource, the coach must provide a cost estimate, require a budget alarm, receive explicit approval, and include a teardown command. Persistent EKS is out of scope for the USD 20 monthly budget; Kubernetes practice uses a local cluster by default.

The entire `private/` directory is ignored. Public learning logs must not contain credentials, private keys, personal email addresses, employer data, internal hostnames, private repository names, or unredacted local paths. Run the scanner before publication:

```powershell
python scripts/privacy_scan.py
```

## Codex scheduled coaching

The weekday coach runs automatically at 09:00 and may include English reading or writing, while spoken-English practice starts manually after 18:00. The weekend coach runs automatically at 10:00 in `Asia/Shanghai`. No API key is needed. See [Codex automation setup](docs/codex-automation.md).

## Contributing

Curriculum fixes, accessible beginner explanations, deterministic tests, and privacy-safe labs are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [PRIVACY.md](PRIVACY.md) before opening a pull request.

## License

MIT. See [LICENSE](LICENSE).
