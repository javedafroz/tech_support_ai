"""Schemas and prompts for classic RAG troubleshooting generation."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class TroubleshootStepGuidance(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1)


class TroubleshootGuidance(BaseModel):
    """Structured grounded guidance produced from retrieved handbook chunks."""

    model_config = {"extra": "forbid"}

    supported: bool = Field(
        description="False when retrieved sources cannot answer the problem.",
    )
    intro: str = Field(
        default="",
        max_length=500,
        description="Short empathetic opener; never mention handbooks or sources.",
    )
    steps: list[TroubleshootStepGuidance] = Field(default_factory=list)
    follow_up: str = Field(
        default=(
            "Give that a try and let me know if it worked. "
            "If it's still not resolved, say so and I'll open a ticket for you."
        ),
        max_length=500,
    )


class TroubleshootOutcomeAnalysis(BaseModel):
    """LLM classification of an ambiguous troubleshooting reply."""

    model_config = {"extra": "forbid"}

    outcome: Literal["resolved", "failed", "escalate", "unclear"] = Field(
        description=(
            "resolved if fixed; failed if still broken; escalate if they want a ticket/human; "
            "unclear otherwise."
        ),
    )


RAG_SYSTEM_PROMPT = """\
You are Tech Support AI's grounded troubleshooting assistant.

You MUST follow these rules:
1. Use ONLY the supplied SOURCE blocks. Do not invent fixes from general knowledge.
2. Never claim you performed an action on the user's behalf. Guide the user only.
3. Never mention handbooks, knowledge bases, document titles, or source IDs in user-facing text.
4. If the sources cannot answer the problem, set supported=false and leave steps empty.
5. If supported=true, produce 1 to {max_steps} concise actionable steps. Choose how many steps \
are needed based on the sources (adaptive).
6. Each step.instruction must be user-facing guidance. Each step must cite at least one \
allowed SOURCE id in source_ids. Allowed ids look like src1, src2, src3 — never invent \
ids from FAQ numbers (e.g. do not use src13 because a heading says "13.").
7. Keep intro empathetic and short. Prefer second person ("you're dealing with…").
"""

OUTCOME_SYSTEM_PROMPT = """\
You classify a user's reply after troubleshooting steps were suggested.
Return exactly one outcome:
- resolved: the issue is fixed / working now
- failed: the issue is still broken / steps did not help
- escalate: the user wants a ticket or a human agent
- unclear: cannot tell
Do not invent facts beyond the user's message.
"""


def build_rag_prompt_messages(
    *,
    problem: str,
    contexts: list[dict[str, str]],
    max_steps: int,
) -> list:
    system = RAG_SYSTEM_PROMPT.format(max_steps=max_steps)
    allowed = [c["source_id"] for c in contexts if c.get("source_id")]
    blocks: list[str] = [
        f"Problem:\n{problem.strip()}\n",
        f"Max steps: {max_steps}\n",
        f"Allowed source_ids (use only these exact values): {', '.join(allowed)}\n",
        "SOURCES:",
    ]
    for ctx in contexts:
        source_id = ctx["source_id"]
        section = ctx.get("section_title") or ""
        body = ctx.get("body") or ""
        header = f"[SOURCE id={source_id}]"
        if section:
            header += f" section={section}"
        blocks.append(f"{header}\n{body}")
    blocks.append(
        "\nReturn grounded troubleshooting guidance. "
        f"Every step.source_ids value MUST be one of: {', '.join(allowed)}."
    )
    return [SystemMessage(content=system), HumanMessage(content="\n\n".join(blocks))]


def build_outcome_prompt_messages(*, user_text: str) -> list:
    return [
        SystemMessage(content=OUTCOME_SYSTEM_PROMPT),
        HumanMessage(content=f"User reply:\n{user_text.strip()}"),
    ]
