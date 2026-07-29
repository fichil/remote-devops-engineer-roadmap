# Codex scheduled coaching

The personal automation is deliberately split into two mutually exclusive scheduled tasks so that exactly one task is created per calendar day in `Asia/Shanghai`:

- Monday–Friday at 09:00
- Saturday–Sunday at 10:00

Both runs use the local project environment because the plan and progress state must persist in the main checkout. A dedicated worktree would isolate the state and make the next run read stale progress.

## Shared prompt

```text
你是本仓库的 DevOps 转行教练。完整遵守 AGENTS.md。先读取 config/learner.yml、curriculum/roadmap.yml、state/progress.json、当天计划和最近周复盘。优先运行 `.venv\\Scripts\\python.exe -m devops_coach today`；若项目虚拟环境不存在，再使用当前 Python 环境运行同一模块。当天计划存在时只恢复，不得重复创建；否则生成计划。报告今天总时长、当前周次和主题，只给出第一项未完成任务、完成标准和预计时间，然后等待用户参与。不得替用户完成练习、无证据标记完成、创建收费云资源、提交或推送 GitHub。仅当用户在当前任务明确说“完成并发布今日记录”时，才按 AGENTS.md 的发布门禁处理。
```

If the computer or Codex is not running at the scheduled time, open Scheduled in the desktop app and manually run the applicable task. The schedule does not create a synthetic backfill run.

The repository itself does not contain account-specific automation IDs. This keeps the open-source project reusable and prevents local Codex configuration from becoming public state.
