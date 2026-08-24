# DevOps 转行总规划

## 目标定义

- 目标岗位：海外远程 DevOps 工程师（正式雇员或长期合同工）。
- 路线起点：2026-07-29；第 78 周预计能力门槛日：2028-01-21。
- 达标含义：具备稳定投递和参加面试的证据门槛，不承诺具体录用日期。
- 总进度同时看规划周次、证据任务、阶段门禁和职业成果，不合成为单一百分比。

## 执行规则

- 周一至周五每天定量完成一个完整运维任务；周六、周日完全休息。
- 每个标准任务固定包含事件简报、实战处理、英文书面交接三个检查点。
- 每个工作日先完成当天计划任务；旧任务不得抢占当天主任务。
- 当天主任务完成后默认停止；用户明确要求继续时，最多再处理一个最早遗留任务。
- 完整任务取得全部证据后自动通过 Ready PR、CI 和 squash merge 发布；可选遗留单独发布。
- 日历主题每周前进；跨阶段时，未通过的先修门禁会改派重教或复测任务。
- 日常英语只评价阅读和写作；通用口语与发音由 Duolingo 负责。
- 路线明确安排的技术演示和模拟面试仍是职业门槛证据。

## 六阶段与门禁

| 阶段 | 周次 | 核心成果 | 阶段门禁 |
|---|---:|---|---|
| 计算机、Linux 与英语基础 | 1–13 | 能在 WSL2 Ubuntu 中安全完成文件、权限、进程、包与网络操作。；能用 Git/GitHub 保存可审查的学习证据，并解释基础 Web 请求链路。 | 独立完成一次 Linux 权限、进程和网络组合排障，掌握度不低于 4/5。 |
| Linux 管理、脚本与系统自动化 | 14–26 | 能用 Bash 与 Python 自动化重复任务并为关键逻辑编写测试。；能配置 SSH、Nginx、计划任务和基础安全控制，并进行系统级排障。 | 从空白环境部署服务、制造故障、定位根因并用脚本恢复。 |
| 容器与持续交付 | 27–39 | 能构建、调试并安全运行容器镜像与 Compose 应用。；能设计带测试、制品、Secret 和回滚说明的 GitHub Actions 流水线。 | 从 Git 提交到可验证部署全流程自动化，失败时能定位阶段和恢复。 |
| AWS 云平台与基础设施即代码 | 40–52 | 能在成本保护下设计并操作安全、可恢复的 AWS 基础环境。；能用 Terraform 创建、变更和销毁环境，并解释状态与模块边界。 | 经成本确认后从零创建环境、验证服务、展示监控并完整销毁。 |
| Kubernetes、可观测性与 SRE | 53–65 | 能在本地集群部署、升级、调试和恢复 Kubernetes 工作负载。；能定义 SLI/SLO、监控、日志和告警，并主持一次事故复盘。 | 在本地集群完成一次受控故障、告警、定位、恢复和无责复盘。 |
| 生产级综合项目与海外求职 | 66–78 | 能展示端到端平台、权衡、安全、可靠性、成本与恢复能力。；能用英语完成异步协作、技术面试、行为面试和远程岗位申请。 | 六个作品、三次有效开源贡献、双语简历和三轮模拟面试达到 4/5。 |

## 78 周主题

| 周次 | 阶段 | 主题 |
|---:|---|---|
| 1 | 计算机、Linux 与英语基础 | 学习系统、WSL2 与终端 / Learning System, WSL2, and Terminal |
| 2 | 计算机、Linux 与英语基础 | Linux 文件、目录与路径 / Linux Files, Directories, and Paths |
| 3 | 计算机、Linux 与英语基础 | 用户、组与文件权限 / Users, Groups, and Permissions |
| 4 | 计算机、Linux 与英语基础 | 进程、服务与软件包 / Processes, Services, and Packages |
| 5 | 计算机、Linux 与英语基础 | Git 本地工作流 / Local Git Workflow |
| 6 | 计算机、Linux 与英语基础 | GitHub 协作与 Markdown / GitHub Collaboration and Markdown |
| 7 | 计算机、Linux 与英语基础 | 计算机硬件、操作系统与虚拟化 / Hardware, Operating Systems, and Virtualization |
| 8 | 计算机、Linux 与英语基础 | IP、子网与路由基础 / IP, Subnets, and Routing Basics |
| 9 | 计算机、Linux 与英语基础 | DNS、端口与常见协议 / DNS, Ports, and Common Protocols |
| 10 | 计算机、Linux 与英语基础 | HTTP、HTTPS 与 TLS / HTTP, HTTPS, and TLS |
| 11 | 计算机、Linux 与英语基础 | 日志、退出码与基础排障 / Logs, Exit Codes, and Basic Troubleshooting |
| 12 | 计算机、Linux 与英语基础 | Linux 排障手册项目 / Linux Troubleshooting Runbook Project |
| 13 | 计算机、Linux 与英语基础 | 基础阶段复测与英文演示 / Foundation Gate and English Demo |
| 14 | Linux 管理、脚本与系统自动化 | Bash 变量、管道与退出码 / Bash Variables, Pipes, and Exit Codes |
| 15 | Linux 管理、脚本与系统自动化 | Bash 条件、循环与函数 / Bash Conditions, Loops, and Functions |
| 16 | Linux 管理、脚本与系统自动化 | Python 基础与虚拟环境 / Python Basics and Virtual Environments |
| 17 | Linux 管理、脚本与系统自动化 | Python 文件、JSON 与命令行 / Python Files, JSON, and CLI Tools |
| 18 | Linux 管理、脚本与系统自动化 | 自动化测试与错误处理 / Automated Tests and Error Handling |
| 19 | Linux 管理、脚本与系统自动化 | SSH、密钥与远程管理 / SSH, Keys, and Remote Administration |
| 20 | Linux 管理、脚本与系统自动化 | systemd、日志与计划任务 / systemd, Logs, and Scheduled Jobs |
| 21 | Linux 管理、脚本与系统自动化 | 存储、挂载与备份 / Storage, Mounts, and Backups |
| 22 | Linux 管理、脚本与系统自动化 | Nginx 与反向代理 / Nginx and Reverse Proxying |
| 23 | Linux 管理、脚本与系统自动化 | DNS、HTTP 与 TLS 深入排障 / DNS, HTTP, and TLS Troubleshooting |
| 24 | Linux 管理、脚本与系统自动化 | 最小权限、补丁与基础加固 / Least Privilege, Patching, and Hardening |
| 25 | Linux 管理、脚本与系统自动化 | 自动化工具箱项目 / Automation Toolkit Project |
| 26 | Linux 管理、脚本与系统自动化 | 系统自动化阶段复测 / Systems Automation Gate |
| 27 | 容器与持续交付 | 容器原理与 Docker CLI / Container Fundamentals and Docker CLI |
| 28 | 容器与持续交付 | Dockerfile 与镜像分层 / Dockerfiles and Image Layers |
| 29 | 容器与持续交付 | 网络、卷与运行时配置 / Networks, Volumes, and Runtime Configuration |
| 30 | 容器与持续交付 | Docker Compose 多服务应用 / Multi-Service Apps with Docker Compose |
| 31 | 容器与持续交付 | 容器调试、性能与安全 / Container Debugging, Performance, and Security |
| 32 | 容器与持续交付 | CI/CD 原理与质量门禁 / CI/CD Principles and Quality Gates |
| 33 | 容器与持续交付 | GitHub Actions 工作流 / GitHub Actions Workflows |
| 34 | 容器与持续交付 | 测试、缓存与构建制品 / Tests, Caching, and Build Artifacts |
| 35 | 容器与持续交付 | Secrets、OIDC 与供应链基础 / Secrets, OIDC, and Supply Chain Basics |
| 36 | 容器与持续交付 | 版本、发布与回滚 / Versioning, Releases, and Rollbacks |
| 37 | 容器与持续交付 | 容器化服务项目实现 / Containerized Service Implementation |
| 38 | 容器与持续交付 | 流水线故障演练与 Runbook / Pipeline Failure Drills and Runbooks |
| 39 | 容器与持续交付 | 容器与交付阶段复测 / Containers and Delivery Gate |
| 40 | AWS 云平台与基础设施即代码 | 云模型、AWS 账号与成本保护 / Cloud Models, AWS Accounts, and Cost Guardrails |
| 41 | AWS 云平台与基础设施即代码 | IAM、身份与最小权限 / IAM, Identity, and Least Privilege |
| 42 | AWS 云平台与基础设施即代码 | VPC、子网、路由与安全组 / VPCs, Subnets, Routes, and Security Groups |
| 43 | AWS 云平台与基础设施即代码 | EC2、负载均衡与自动伸缩 / EC2, Load Balancing, and Auto Scaling |
| 44 | AWS 云平台与基础设施即代码 | S3、生命周期与静态内容 / S3, Lifecycles, and Static Content |
| 45 | AWS 云平台与基础设施即代码 | RDS、备份与恢复 / RDS, Backups, and Recovery |
| 46 | AWS 云平台与基础设施即代码 | ECR、ECS 与容器部署 / ECR, ECS, and Container Deployment |
| 47 | AWS 云平台与基础设施即代码 | CloudWatch、日志、指标与告警 / CloudWatch Logs, Metrics, and Alarms |
| 48 | AWS 云平台与基础设施即代码 | Terraform 资源、状态与计划 / Terraform Resources, State, and Plans |
| 49 | AWS 云平台与基础设施即代码 | Terraform 模块与远程状态 / Terraform Modules and Remote State |
| 50 | AWS 云平台与基础设施即代码 | CI 中的 IaC 与策略检查 / IaC and Policy Checks in CI |
| 51 | AWS 云平台与基础设施即代码 | AWS Terraform 作品项目 / AWS Terraform Portfolio Project |
| 52 | AWS 云平台与基础设施即代码 | 云与 IaC 阶段复测及认证决策 / Cloud and IaC Gate with Certification Decision |
| 53 | Kubernetes、可观测性与 SRE | Kubernetes 架构与 kubectl / Kubernetes Architecture and kubectl |
| 54 | Kubernetes、可观测性与 SRE | Pod、Deployment 与 Service / Pods, Deployments, and Services |
| 55 | Kubernetes、可观测性与 SRE | ConfigMap、Secret 与存储 / ConfigMaps, Secrets, and Storage |
| 56 | Kubernetes、可观测性与 SRE | 调度、资源、探针与伸缩 / Scheduling, Resources, Probes, and Scaling |
| 57 | Kubernetes、可观测性与 SRE | 网络、Ingress 与 TLS / Networking, Ingress, and TLS |
| 58 | Kubernetes、可观测性与 SRE | Helm 包管理 / Package Management with Helm |
| 59 | Kubernetes、可观测性与 SRE | GitOps 与 Argo CD / GitOps with Argo CD |
| 60 | Kubernetes、可观测性与 SRE | Prometheus 指标与 PromQL / Prometheus Metrics and PromQL |
| 61 | Kubernetes、可观测性与 SRE | Grafana 仪表盘与告警 / Grafana Dashboards and Alerting |
| 62 | Kubernetes、可观测性与 SRE | Loki 日志与故障关联 / Loki Logs and Incident Correlation |
| 63 | Kubernetes、可观测性与 SRE | SLI、SLO、错误预算与值班 / SLIs, SLOs, Error Budgets, and On-Call |
| 64 | Kubernetes、可观测性与 SRE | Kubernetes 事故演练项目 / Kubernetes Incident Drill Project |
| 65 | Kubernetes、可观测性与 SRE | Kubernetes 与 SRE 阶段复测 / Kubernetes and SRE Gate |
| 66 | 生产级综合项目与海外求职 | 综合项目需求与成功指标 / Capstone Requirements and Success Metrics |
| 67 | 生产级综合项目与海外求职 | 架构决策与威胁建模 / Architecture Decisions and Threat Modeling |
| 68 | 生产级综合项目与海外求职 | IaC、CI/CD 与环境交付 / IaC, CI/CD, and Environment Delivery |
| 69 | 生产级综合项目与海外求职 | 可观测性、SLO 与告警 / Observability, SLOs, and Alerts |
| 70 | 生产级综合项目与海外求职 | 备份、灾难恢复与演练 / Backup, Disaster Recovery, and Drills |
| 71 | 生产级综合项目与海外求职 | 安全、成本与性能审查 / Security, Cost, and Performance Review |
| 72 | 生产级综合项目与海外求职 | 英文文档与项目演示 / English Documentation and Project Demo |
| 73 | 生产级综合项目与海外求职 | 开源贡献冲刺 / Open Source Contribution Sprint |
| 74 | 生产级综合项目与海外求职 | 英文简历、GitHub 与职业主页 / English Resume, GitHub, and Professional Profile |
| 75 | 生产级综合项目与海外求职 | Linux、网络与云技术面试 / Linux, Networking, and Cloud Interviews |
| 76 | 生产级综合项目与海外求职 | 系统设计、事故与行为面试 / System Design, Incident, and Behavioral Interviews |
| 77 | 生产级综合项目与海外求职 | 海外岗位定制投递与复盘 / Tailored Global Applications and Review |
| 78 | 生产级综合项目与海外求职 | 最终能力门槛与后续路线 / Final Readiness Gate and Next Roadmap |

## 门禁规则

- 六个阶段门禁都必须有可复核证据且达到 4/5；不得为维持名义日期降低门槛。
- 0–2 分安排优先重教和变化题；3 分安排后续检索；4–5 分仍需成功证据与独立解释或变化。
- 门禁未通过时保留日历周次，但下一阶段任务保持锁定。

## 英语进阶

- 第 1–13 周：读懂基础命令和工单，用简单英文写事实、结果与下一步。
- 第 14–26 周：编写脚本 README、故障报告和异步状态更新。
- 第 27–39 周：编写 Issue、PR、发布说明，并保留路线规定的技术演示。
- 第 40–65 周：编写架构、成本、变更、告警、事故时间线和复盘文档。
- 第 66–78 周：完成全英文 README、简历、求职信、书面面试回答、技术演示和模拟面试。

## 作品集与求职里程碑

- 作品集目标：6 个，每个阶段至少形成一个可运行、可验证、可解释的成果。
- 开源贡献目标：3 次被接受的有效贡献，公开部分不得包含私人求职信息。
- 模拟面试目标：3 轮，技术演示和路线规定的面试环节保留。
- 求职里程碑：综合项目、英文文档、简历与职业主页、定制投递、最终能力门禁。

## 遗留优先与内容适应

- 每周仍生成五个新任务，并把它们固定为当周五个必做执行名额。
- 遗留任务按最早创建顺序排列，只能在当天主任务完成且用户明确要求后处理一项。
- 完成率低或出现 0–2 分项：下一周重教、拆小并加入变化题。
- 完成率高、平均分至少 4 且无阻塞：任务数量不变，增加独立变化要求。
- 周复盘只调整内容，不调整每日任务数量，也不使用历史时间数据。
