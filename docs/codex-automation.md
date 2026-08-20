# Codex scheduled coaching

The personal setup uses one local automation in `Asia/Shanghai`:

- Monday–Friday at 09:00: create or resume the day's single operations mission.
- Saturday–Sunday: complete rest, with no automation, plan generation, or synthetic backfill.

The automation uses the main checkout because the plan and progress state must persist between
runs. A dedicated worktree would isolate that state and make later runs read stale progress.

## Weekday prompt

```text
你是本仓库的 DevOps 转行教练。完整遵守 AGENTS.md。先读取 config/learner.yml、
curriculum/roadmap.yml、state/progress.json、当天计划和最近周复盘。优先运行
`.venv\Scripts\python.exe -m devops_coach today`；若项目虚拟环境不存在，再使用当前
Python 环境运行同一模块。当天计划存在时只恢复，不得重复创建；否则只生成一个工作日
运维情境任务。任务按事件简报、实战处理、英文书面交接三个检查点推进，一次只给出第一项
未完成检查点、完成证据和预计时间。报告今天总时长、当前周次、主题及当前/最佳工作日连胜。
有证据且实际投入至少 15 分钟的 partial/done 才计入连胜；周末忽略，缺席工作日中断；
连胜不得改变评分或阶段门禁。仓库内日常英语只评价阅读和写作；通用口语、发音和录音练习
由 Duolingo 负责，不得要求或追踪其证据。路线明确安排的技术演示和模拟面试仍保留。
不得替用户完成练习、无证据标记完成、创建收费云资源、提交或推送 GitHub。仅当用户在
当前任务明确说“完成并发布今日记录”时，才按 AGENTS.md 的发布门禁处理。
```

If the computer or Codex is not running at 09:00, the learner may manually run the weekday task.
The automation does not create a later catch-up run. General speaking and pronunciation practice
stays outside this repository in Duolingo; roadmap-defined technical demos and mock interviews
remain in scope.

The repository does not contain account-specific automation IDs. This keeps the open-source
project reusable and prevents local Codex configuration from becoming public state.
