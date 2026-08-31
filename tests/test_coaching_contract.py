from __future__ import annotations

from pathlib import Path


def test_coach_contract_forbids_questionnaire_and_copy_chain() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = (root / "AGENTS.md").read_text(encoding="utf-8")

    assert "never require the fixed four-part" in contract
    assert "Pasted output or an exit code by itself never completes" in contract
    assert "A command supplied in full is guided practice, not mastery evidence" in contract
    assert "Ask one question" in contract
    assert "When the learner says they do not understand a command" in contract
    assert "Never give the complete answer or a complete command" in contract
    assert "require a different condition" in contract


def test_automation_prompt_carries_cognitive_apprenticeship_rules() -> None:
    root = Path(__file__).resolve().parents[1]
    automation = (root / "docs" / "codex-automation.md").read_text(encoding="utf-8")

    assert "认知学徒制任务按概念与预测、引导练习、独立迁移与交付推进" in automation
    assert "不得固定要求“事实、风险、缺失信息、假设”四项" in automation
    assert "复制命令、只贴输出或只报退出码不能证明" in automation
    assert "学习者说“不懂命令”时必须暂停执行" in automation
    assert "当前独立变化题不得直接给完整答案或完整命令" in automation
    assert "另出" in automation and "无提示变化题" in automation
    assert "周五从本地" in automation and "裸远程新建副本" in automation
