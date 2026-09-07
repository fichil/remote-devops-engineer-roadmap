"""Shared learner-facing text; deliberately contains no progress/evidence mutation."""

from __future__ import annotations

from typing import Any

CHECKPOINT_TITLES = {
    "briefing": "讲解与示范",
    "lab": "引导练习",
    "written_handoff": "独立迁移与交付",
}
TEACHING_FIELDS = frozenset(
    {"title", "instruction", "success_criteria", "coach_action", "learner_action", "hint_policy"}
)
ADAPTATION_SUFFIXES = {
    "reteach": " 先重教最弱点，拆成可验证的小步，再完成变化题。",
    "stretch": " 完成基础要求后，再独立处理一个未给步骤的变化条件。",
}
FORMATIVE_HINT_POLICY = (
    "新概念和陌生命令先完整讲解示范；已教过的内容再逐渐减少提示。"
    "示范和带练不评分；完整命令不能作为独立掌握证据。"
)
FORMATIVE_COACH_ACTION = (
    "先用中文讲用途、对象关系和例子；陌生命令直接完整拆解命令、选项、参数、"
    "引号、目标、预期输出类型及退出状态，再带领学习者操作。"
    "每个概念块最多一个有实际判断价值的问题，也可用操作后的解释检查理解；"
    "不要求复述题目、连续填空或猜具体版本号。"
    "普通只读查询不重复询问配置会不会变化；若会启动进程等具体副作用，先解释。"
    "预测只用于结果差异、范围选择或故障假设，允许不确定和错误，随后用安全观察纠正；"
    "错误预测不是编造证据，实际结果必须真实，教练解释不能记成学习者解释。"
    "学习者说不懂时返回讲解与示范，不继续猜参数。"
)


def adapt_instruction(instruction: str, mode: str) -> str:
    return instruction + ADAPTATION_SUFFIXES.get(mode, "")


def existing_adaptation(instruction: str) -> str:
    """Keep a task's original adaptation, not today's possibly different review mode."""
    return next(
        (mode for mode, suffix in ADAPTATION_SUFFIXES.items() if instruction.endswith(suffix)),
        "standard",
    )


def teaching_metadata(checkpoint_id: str) -> dict[str, str]:
    """Only mutable teaching fields, never assessment or evidence defaults."""
    result = {"title": CHECKPOINT_TITLES[checkpoint_id]}
    if checkpoint_id == "written_handoff":
        result.update(
            success_criteria=(
                "在变化条件下独立提交有判断价值的预测、学习者动作、实际结果、解释，以及 "
                "2–4 句真实英文 PR 评论或交接。预测不要求猜精确值，观察不能编造。"
            ),
            coach_action="提供变化条件但不给完整命令；只验证真实证据并按 0–5 分总结评价。",
            learner_action="独立选择或编写命令，预测、执行、解释，并完成英文书面交付。",
            hint_policy="不提供完整命令；若需要完整提示，本次转回引导练习并更换变化题。",
        )
    else:
        result.update(
            success_criteria=(
                "讲解示范后，通过一个有实际判断价值的问题或操作后的自主解释展示理解；"
                "不评分，不能仅因看过示范而标记掌握。"
                if checkpoint_id == "briefing"
                else "在讲解示范后实际操作，提交真实结果并自主解释；该阶段不计分。"
            ),
            coach_action=FORMATIVE_COACH_ACTION,
            learner_action=(
                "看完讲解示范后表达理解或指出具体不懂之处，不复述题目充当答案。"
                if checkpoint_id == "briefing"
                else "在带领下执行已讲清的操作，观察并用自己的话解释；不懂时先请求讲解。"
            ),
            hint_policy=FORMATIVE_HINT_POLICY,
        )
    return result


def checkpoint_teaching(
    checkpoint_id: str, mission: dict[str, Any], adaptation_mode: str = "standard"
) -> dict[str, str]:
    """Used by new tasks, historical conversion, and non-destructive text refresh."""
    result = teaching_metadata(checkpoint_id)
    if checkpoint_id == "briefing":
        instruction = (
            "先讲解本任务的用途、对象关系和一个例子，并示范有关命令；"
            "讲解后最多选一个有判断价值的问题，也可通过操作后的解释检查理解："
            + str(mission.get("concept_prompt", mission.get("objective", "")))
        )
    elif checkpoint_id == "lab":
        instruction = str(mission.get("guided_practice", mission.get("lab", "")))
        if "guided_practice" not in mission:
            instruction = "先讲解用途、对象关系并完整示范陌生命令，再带领实际操作：" + instruction
    else:
        instruction = str(mission.get("independent_delivery", mission.get("english_output", "")))
        if "independent_delivery" not in mission:
            instruction = (
                "在不同于带练的条件下独立操作，提交有意义的预测、真实结果和自主解释，"
                "完成 2–4 句英文交付；不提供完整命令：" + instruction
            )
    if not instruction.strip():
        raise ValueError(f"Missing teaching instruction for {checkpoint_id}")
    result["instruction"] = adapt_instruction(instruction, adaptation_mode)
    return result
