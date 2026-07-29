# 海外远程 DevOps 工程师转行路线

[English](README.md)

这是一个开源、证据驱动的 Codex 转行教练，目标是帮助 IT 和英语基础较弱的学习者，在 18 个月内达到海外远程 DevOps 岗位的投递和面试水平。

它不是链接清单，也不承诺必然入职。项目把 78 周能力路线、每日时间盒、作业证据、周复盘、自适应减载、技术英语、作品集门槛和真实经验桥梁放进同一个可运行系统。

## 当前个人目标

- IT 起点：初学者。
- 英语起点：约 A2，阅读略有基础，口语较弱。
- 时间：工作日每天 75 分钟、周六 180 分钟、周日 120 分钟，每周约 11.25 小时。
- 技术主线：Linux、Python/Bash、Docker、GitHub Actions、AWS、Terraform、Kubernetes、可观测性和 SRE。
- 职业目标：海外远程正式雇员或长期合同工。
- 经验桥梁：初级运维、云支持、实习和开源贡献。
- 预算：每月不超过 20 美元，作品集优先，第 12 个月再决定是否准备 AWS Associate 认证。

18 个月的成功标准是具备真实竞争力、开始稳定投递并获得面试或合作机会，不是降低门槛制造“已学完”的状态。

## 教练能做什么

- 每个日期只生成一份计划；重复启动会恢复原计划，不覆盖证据。
- 用一个结构化状态文件持续记录周次、任务、掌握度、复习日期、阻塞和作品集。
- 只有提供命令输出、代码、测试、Runbook 或演示后，任务才能标记完成。
- 掌握度 0–2 的内容在 48 小时内重学，3 分内容在 7 天后复习。
- 完成率低于 70% 时下周减载 20%；高于 90%、平均掌握度至少 4 且无阻塞时最多加速 10%。
- 英语至少占学习时间的 25%，并逐步从单词、短句过渡到英文 README、Issue、事故复盘、演示和面试。
- 公司名单、联系方式、收入和投递记录只进入被 Git 忽略的 `private/`。
- 没有明确收到“完成并发布今日记录”，不得提交或推送每日进度。

## 开始使用

需要 Python 3.11 以上版本和 Git。在 PowerShell 中运行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m devops_coach validate
python -m devops_coach today
```

然后打开 `plans/` 中当天的计划，或者在 Codex 中说：

```text
开始今天学习
```

教练的长期行为约束位于 [`AGENTS.md`](AGENTS.md)，公开且脱敏的个人配置位于 [`config/learner.yml`](config/learner.yml)。其他学习者复用时应复制 [`config/learner.example.yml`](config/learner.example.yml)。

## 命令接口

```text
python -m devops_coach today [--date YYYY-MM-DD]
python -m devops_coach record --task ID --status done|partial|blocked --score 0..5 --minutes N --evidence PATH
python -m devops_coach review [--week YYYY-Www]
python -m devops_coach status
python -m devops_coach validate
```

记录已验证作业的示例：

```powershell
python -m devops_coach record `
  --task 2026-07-29-practice `
  --status done `
  --score 4 `
  --minutes 25 `
  --evidence evidence/week-01/wsl-environment.md
```

## 78 周主路线

1. 第 1–13 周：计算机、WSL/Linux、Git/GitHub、权限、网络与 A2 英语。
2. 第 14–26 周：Linux 管理、SSH、Bash、Python、Nginx 和系统排障。
3. 第 27–39 周：Docker、Compose、测试、GitHub Actions、发布和回滚。
4. 第 40–52 周：AWS IAM、VPC、EC2、S3、RDS/ECS、CloudWatch 和 Terraform。
5. 第 53–65 周：Kubernetes、Helm、GitOps、Prometheus/Grafana/Loki 和 SRE。
6. 第 66–78 周：生产级综合项目、开源贡献、英文简历、模拟面试和海外投递。

每个阶段都必须交付一个能运行的公开项目、中英双语说明和英文演示。完整周主题和前四周逐日任务位于 [`curriculum/roadmap.yml`](curriculum/roadmap.yml)。

## 成本与隐私红线

任何可能收费的 AWS 实验都必须先给出成本估算、设置预算告警、获得明确确认并准备销毁命令。20 美元月预算下不持续运行 EKS；Kubernetes 默认使用本地集群。

`private/` 整体被忽略。公开记录不得包含凭据、私钥、私人邮箱、雇主数据、内部域名、私有仓库名或未脱敏的本机路径。发布前运行：

```powershell
python scripts/privacy_scan.py
```

## Codex 定时教练

个人环境使用两条互斥的本地定时任务：北京时间工作日 09:00、周末 10:00。电脑未开导致错过时手动运行，不需要 OpenAI API Key。配置和手动试跑方法见 [Codex 自动化说明](docs/codex-automation.md)。

## 参与贡献

欢迎提交课程纠错、适合初学者的解释、确定性测试和隐私安全的实验。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md) 和 [PRIVACY.md](PRIVACY.md)。

## 许可证

MIT，见 [LICENSE](LICENSE)。
