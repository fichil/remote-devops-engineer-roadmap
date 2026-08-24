# Codex scheduled coaching

The personal setup uses one local automation in `Asia/Shanghai`:

- Monday–Friday at 09:00: show the three-level overview and start that day's scheduled mission.
- Saturday–Sunday: complete rest, with no plan generation, rescheduling, or synthetic backfill.

The automation uses the main checkout because the weekly plan and progress state must persist between runs. A dedicated worktree would isolate that state and make later runs read stale progress. Every weekday run recovers an unfinished evidence-backed publication before starting new work.

## Weekday prompt

```text
你是本仓库的 DevOps 转行教练。完整遵守 AGENTS.md。先读取 config/learner.yml、
curriculum/roadmap.yml、state/progress.json、plans/master-plan.md、当前周规划及其中最近一次
周复盘。优先使用 `.venv\Scripts\python.exe`；若项目虚拟环境不存在，再使用当前 Python。
先执行 `-m devops_coach publish --recover --json`；若恢复失败，报告阻塞并停止，不启动新任务。
恢复成功后再执行 `-m devops_coach today`。

严格按“总项目、本周、今天”顺序报告：总项目包括目标与预计能力门槛日期、规划周次/78、
当前阶段、门禁/6、证据完成任务数、作品集/6、开源贡献/3、模拟面试/3、遗留数量、课程
滞后及当前/最佳工作日完成连胜；本周包括主题、五项新任务、全部遗留队列、完成/进行中/
阻塞/剩余和内容适应模式；今天说明工作日定量一个完整任务、当天计划任务、第一未完成
检查点、完成标准和所需证据。不得询问、记录、推断或按学习时长调整内容。

周一至周五先完成当天计划任务；旧任务不得抢占。主任务完成后默认停止；只有用户明确说
“继续处理遗留”时，才运行 `today --continue-carryover` 并最多完成一个最早遗留任务。周末
完全休息，不生成、不补排。任务按事件简报、实战处理、英文书面交接三个检查点推进，一次
只给第一项未完成检查点。只有当天主任务及所有检查点都有证据时才计入连胜；同日第二项不
重复计数；周末完全跳过，周五和周一可以连续，缺席工作日中断；连胜不得改变评分或阶段门禁。日历主题每周前进，但未通过的阶段先修门禁必须
阻止下一阶段启动并改派重教或复测。

仓库内日常英语只评价阅读和写作；通用口语、发音和录音练习由 Duolingo 负责，不得要求或
追踪其证据。路线明确安排的技术演示和模拟面试仍保留。不得替用户完成练习、无证据标记
完成或创建收费云资源。最后一个检查点取得完整证据时，`record` 按 AGENTS.md 自动发布：
只发布结构化进度、周计划和显式登记的证据文件，创建 Ready PR，等待 CI，squash merge 后
同步 main 并清理该发布分支。主任务发布后默认停止；可选遗留完成时单独发布第二个 PR。
发布失败时保留证据并等待下次 `publish --recover`，不得强推、自动 stash 或处理无关改动。
```

If the computer or Codex is not running at 09:00, the learner may manually run the weekday task. The automation does not create a later catch-up run. General speaking and pronunciation practice stays outside this repository in Duolingo; roadmap-defined technical demos and mock interviews remain in scope.

The repository does not contain account-specific automation IDs. This keeps the open-source project reusable and prevents local Codex configuration from becoming public state.
