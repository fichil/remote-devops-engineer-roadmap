# 海外远程 DevOps 工程师转行路线

[English](README.md)

这是一个开源、证据驱动的 Codex 转行教练，目标是帮助 IT 和英语基础较弱的学习者，通过 78 周路线达到海外远程 DevOps 岗位的投递和面试门槛。

它不是链接清单，也不承诺必然入职。项目把能力路线、每个工作日一个完整任务、作业证据、内容型周复盘、技术英语、作品集门禁和真实经验桥梁放进同一个可运行系统。

## 当前个人目标

- IT 起点：初学者。
- 英语起点：约 A2，阅读略有基础。
- 安排：周一至周五学习，周六和周日完全休息。
- 技术主线：Linux、Python/Bash、Docker、GitHub Actions、AWS、Terraform、Kubernetes、可观测性和 SRE。
- 职业目标：海外远程正式雇员或长期合同工。
- 经验桥梁：初级运维、云支持、实习和开源贡献。
- 预算：每月不超过 20 美元，作品集优先，后续再按证据决定认证。

成功标准是具备真实竞争力、开始稳定投递并获得面试或合作机会，不是降低门槛制造“已学完”的状态。

## 教练能做什么

- 维护一份 [78 周总规划](plans/master-plan.md) 和每个日历周一份可持续更新的周规划。
- 每周创建五个新任务，并把它们固定为周一至周五各自的当天计划任务。
- 每个工作日先执行当天任务；完成后默认停止，只有学习者明确要求继续时才可选做一个最早遗留项。
- 每个标准任务采用认知学徒制：讲解与示范、引导练习、独立迁移与真实交付。
- 复制命令和只粘贴输出只能算引导练习；掌握证据必须包含学习者自己的选择或命令、预测、实际结果和解释。
- 根据完成数量、掌握度和阻塞调整下周内容，不改变每天一个任务的定量。
- 只有工作日完整完成一个有证据任务才计入连胜；周末跳过，缺席工作日中断。
- 日历主题每周前进，但阶段门禁未通过时会改派重教或复测，不启动下一阶段实作。
- 日常英语只评价阅读和写作；通用口语与发音由 Duolingo 负责，路线规定的技术演示和模拟面试仍保留。
- 公司名单、联系方式、收入和投递记录只进入被 Git 忽略的 `private/`。
- 只有证据完整的任务才自动通过 Ready PR、CI 与校验后的 squash merge 发布；“完成并发布今日记录”保留为人工恢复命令。

## 开始使用

需要 Python 3.11 以上版本和 Git。在 PowerShell 中运行：

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

迁移可重复执行。原 schema v1 进度会按原始字节归档到 `state/archive/progress-v1.json`，旧日计划不重写。新系统只使用 `plans/master-plan.md` 和 `plans/weeks/YYYY-Www.md`，不再创建新的每日 Markdown。

## 命令接口

```text
python -m devops_coach migrate --to-schema 2 [--dry-run]
python -m devops_coach migrate --to-training cognitive_apprenticeship_v1 [--dry-run]
python -m devops_coach migrate --refresh-teaching [--dry-run]
python -m devops_coach plan master
python -m devops_coach plan week --week YYYY-Www
python -m devops_coach today [--date YYYY-MM-DD] [--continue-carryover] [--json]
python -m devops_coach record --task ID --checkpoint ID --status in_progress|done|blocked [--score 0..5] --evidence TEXT [--hint-level 0..3] [--independent] [--prediction TEXT --learner-action TEXT --observed-result TEXT --interpretation TEXT --handoff TEXT] [--artifact PATH ...]
python -m devops_coach lab prepare|status|reproduce --week YYYY-Www [--date YYYY-MM-DD] [--json]
python -m devops_coach publish --date YYYY-MM-DD --kind primary|carryover --dry-run|--apply [--json]
python -m devops_coach publish --recover [--date YYYY-MM-DD] [--kind primary|carryover] [--json]
python -m devops_coach review [--week YYYY-Www]
python -m devops_coach status
python -m devops_coach validate
```

记录检查点示例：

```powershell
python -m devops_coach record `
  --task TASK-ID `
  --checkpoint briefing `
  --status done `
  --hint-level 1 `
  --evidence "已核验学习者自己写出的概念解释和预测" `
  --artifact evidence/week-05/git/briefing.md
```

仅刷新教学文案时，使用[教学刷新维护流程](docs/teaching-refresh.md)：先预演，正式运行前备份原始状态；保留已完成记录、进行中证据、成绩、提示等级和复习日期。维护变更不能借用每日学习发布授权。

## 认知学徒制训练

- **讲解与示范**：新概念先讲用途、对象关系和例子，陌生命令直接完整拆解；每个概念块最多一个有实际判断价值的问题，也可通过操作后的解释检查理解，不评分。
- **引导练习**：先看示范，再实际操作并自主解释真实结果；已教过的内容才逐渐减少提示。只在结果差异、范围选择或故障假设处要求预测，不猜具体版本号。错误预测通过安全观察修正，不能与编造实际结果混淆。教练解释不能记为学习者解释。普通查询不重复问配置变化；具体副作用由教练先说明。不懂时返回讲解，示范和带练不评分。
- **独立迁移与交付**：更换条件且不提供完整命令，由学习者独立完成并解释证据，最后写 2–4 句真实英文 PR 评论或交接；只有这一阶段计 0–5 分。

每周项目位于被忽略的 `private/labs/YYYY-Www/`。周一至周四共享一个工作副本，周五从本地裸远程创建全新副本独立复现。GitHub 训练本地优先、默认只读，绝不把学习系统仓库当作练习仓库。

## 工作日任务契约

| 日期 | 必做定量 | 可选遗留 | 必做检查点 |
|---|---:|---:|---|
| 周一至周五 | 1 个当天计划任务 | 明确要求继续后最多 1 个 | 讲解与示范、引导练习、独立迁移与交付 |
| 周六、周日 | 完全休息 | 无 | 不生成、不补排、不回填例行任务 |

启动总览会列出全部遗留项，但遗留不得抢占当天计划任务。当天任务完成后教练默认停止；学习者明确要求继续时，才通过 `python -m devops_coach today --continue-carryover` 启动最早遗留的一项。同日完成两项仍只计一个连胜工作日。

项目包含六个阶段：基础、系统自动化、容器与 CI/CD、AWS 与 Terraform、Kubernetes 与 SRE、生产级综合项目与海外求职。每阶段结束都必须通过证据门禁；证据不足时延长路线，不为保持名义日期降低门槛。

## 成本与隐私红线

任何可能收费的 AWS 实验都必须先给出成本估算、验证预算告警、获得明确确认并准备销毁命令。20 美元月预算下不持续运行 EKS；Kubernetes 默认使用本地集群。

`private/` 整体被忽略。公开记录不得包含凭据、私钥、私人邮箱、雇主数据、内部域名、私有仓库名或未脱敏的本机路径。发布前运行：

```powershell
python scripts/privacy_scan.py
```

## Codex 定时教练

个人环境只保留一条北京时间工作日 09:00 的本地定时任务；周末没有自动化，也不自动补课。任务可以评价英语阅读和写作，但不追踪通用口语、发音或录音练习。配置见 [Codex 自动化说明](docs/codex-automation.md)。

## 参与贡献

欢迎提交课程纠错、适合初学者的解释、确定性测试和隐私安全的实验。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 和 [PRIVACY.md](PRIVACY.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
