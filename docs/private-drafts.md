# 私有草稿与单任务发布

Git 中的 `state/progress.json` 和周计划表示已发布进度。启用草稿后，未完成及待发布记录存放于被忽略的 `private/devops-coach/drafts/`，不会随 Git 推送同步；需要跨机器继续学习时，应另外备份整个私有目录。

教练照常运行 `today`、`record`、`status`、`review` 和 lab 命令。它们读取已发布状态与私有草稿合并后的有效进度；写入草稿不会把其他任务的证据混入下次发布。当前周计划预览位于私有草稿的 `preview/plans/weeks/`，命令返回实际预览路径。周末普通 `today` 不创建文件、任务或草稿。

## 迁移已有工作记录

教练先运行以下预演；命令在主机环境使用项目 Python，Windows 必须加 `-X utf8`：

```powershell
.venv\Scripts\python.exe -X utf8 -m devops_coach drafts import --dry-run --json
.venv\Scripts\python.exe -X utf8 -m devops_coach drafts import --apply --json
```

预演零写入，列出任务和路径。正式迁移将原始文件字节、Git 基线、任务和附件保存为带 SHA256 的原子备份，核验后逐文件恢复公开状态。未知文件、手工编辑周计划、任务定义变化、历史完成记录修改均阻止迁移。中断后重复执行同一命令恢复，不使用 stash 或整库重置。干净仓库也可运行此命令启用草稿；没有启用草稿的旧仓库保留原行为。

## 发布和恢复

最终 `record` 仍自动发布；`publish --recover --json` 仍是恢复入口。发布器从 Git 基线构建目标任务快照，只包含必要的周初始化、该任务完成记录、相关周计划和该任务登记的附件。其他任务留在私有草稿，发布范围校验不放宽。快照、附件原始字节及 publication key 在改动公开文件前冻结，提交内容再次通过范围校验。Windows 文本内容同时遵循 Git 的换行规范化规则。

通过质量检查后创建 Ready PR，等待 CI，squash merge 指定 head，同步 main 并清理发布分支。失败保持快照和证据供恢复；同一发布不重复生成身份或 PR。合并成功后只移除该任务的未发布差异，其他任务从私有草稿继续。代码维护独立走维护 PR，不能混入学习发布。

草稿采用字段级三方合并、校验值、写锁和读取版本检查。不同字段的基线更新可以合并，同字段冲突、未记录的附件改动、共享草稿附件和未知工作区改动都停止操作并报告。不要手工编辑草稿信封或冻结快照。schema 和教学迁移在启用草稿时显式阻塞，需另行进行保留私有状态的维护，避免只更新公开进度。

## 检查两个视图

```powershell
.venv\Scripts\python.exe -X utf8 -m devops_coach validate
.venv\Scripts\python.exe -X utf8 -m devops_coach validate --drafts
```

默认验证公开状态，用于 CI 和发布；`--drafts` 验证教练实际看到的进度和私有周计划预览。实验周、评分、阶段门禁、工作日配额、真实完成日期及连胜规则均不改变。
