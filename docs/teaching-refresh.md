# 教学文案刷新（维护操作）

统一阶段为 **讲解与示范 → 引导练习 → 独立迁移与交付**。新任务、旧工作流转换和已有任务刷新共用 `src/devops_coach/teaching.py`，具体任务来自 `curriculum/roadmap.yml`。内部 ID 仍为 `briefing`、`lab`、`written_handoff`，schema v2 和证据字段不变。

## 使用方式

由教练内部执行，不作为学习者作业：

```powershell
.venv\Scripts\python.exe -X utf8 -m devops_coach migrate --refresh-teaching --dry-run
.venv\Scripts\python.exe -X utf8 -m devops_coach migrate --refresh-teaching
```

预演仅返回拟修改的任务、检查点数量、计划路径和备份路径，零写入。正式刷新前，把原始状态字节保存到被 Git 忽略的 `private/backups/teaching-refresh/<SHA256>.json`。重复执行无变化；周计划写入中断后可重跑同步。不要重跑旧 `--to-training` 迁移来刷新教学文案。

只刷新未完成任务中未完成检查点的 `title`、`instruction`、`success_criteria`、`coach_action`、`learner_action` 和 `hint_policy`，同步相关周计划及总计划模板。任务元信息、历史完成检查点、状态、评分模式、成绩、提示等级、独立标志、证据与附件、复习日期、完成记录和活动时间均保留。已完成检查点的旧阶段名属于历史记录，不强行改写。

这是维护操作，不调用 `record` 或 `publish`，不使用每日学习任务授权提交或合并。修改保存的自动化时只更新提示，保留其计划、模型和其他设置；更新后读回，与仓库的[自动化提示](codex-automation.md)核对。

## 场景验收

| 场景 | 期望教练行为 | 证据边界 |
|---|---|---|
| 首次遇到命令 | 先解释用途、对象关系、完整命令和示例，再带练 | 示范不自动标记掌握 |
| 预测的版本与输出不同 | 不要求猜版本号；已有错误预测用真实观察纠正 | 预测允许错误，观察不能编造 |
| 普通只读查询 | 不重复追问配置是否变化；具体副作用事先说明 | 运行状态变化不等于配置变更 |
| 学习者说“不懂” | 暂停操作，回到讲解与示范 | 不升级为连续猜参数 |
| 独立变化题需要完整命令 | 本次退回带练，另给无提示变化题 | 形成性不评分，4–5 分仍要求提示等级 0 和真实完整证据 |

当前 Layer Map 带练保留已经取得的物理 CPU、Windows 宿主系统和 WSL2 边界证据，从 Linux 内核与 Ubuntu 发行版的关系接续。先讲内核负责进程、内存等核心管理，发行版提供工具与软件环境；再讲 `uname -r` 与 `/etc/os-release` 的用途，一次带领一项操作，不猜具体版本号。
