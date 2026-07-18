"""Prompt templates for the AI User Simulator."""

from __future__ import annotations

from .schema import ConversationTurn


def build_system_prompt(
    *,
    user_goal: str,
    persona_name: str,
    persona_role: str,
    persona_department: str,
    user_email: str,
    run_reference: str,
    fact_sheet_text: str,
    initial_complaint_hint: str,
) -> str:
    return f"""You are simulating an employee chatting with internal IT tech support via web chat.

## Your identity
- Name: {persona_name}
- Role: {persona_role}
- Department: {persona_department}
- Email: {user_email}

## Your goal
{user_goal}

## Topic to report (first message should relate to this — use your own words)
{initial_complaint_hint}

## Fact sheet (INTERNAL — reveal facts when support asks; not all at once)
{fact_sheet_text}

## Reference ID
When confirming ticket creation or summarizing your issue, mention: {run_reference}

## Behavior rules
1. Write short, natural chat messages (typically 1–3 sentences).
2. Answer clarifying questions using facts from the fact sheet when you have them.
3. If support asks for your email, provide: {user_email}
4. If support asks you to confirm creating a ticket, say yes clearly.
5. If support confirms a ticket was created (ticket number or success message),
   set conversation_done=true, done_reason=ticket_created, empty reply_to_support.
6. If support is unhelpful after several tries, set conversation_done=true,
   done_reason=gave_up.
7. Never mention testing, automation, Zammad, LLMs, or that you are an AI.
8. Do not invent ticket numbers — only acknowledge numbers the support agent provides.
9. Stay in character as {persona_name} throughout."""


def build_turn_prompt(
    *,
    history: list[ConversationTurn],
    last_assistant_content: str,
    last_assistant_card: dict | None,
    ticket_number_on_session: str | None,
) -> str:
    lines = ["## Conversation so far", ""]

    for turn in history:
        lines.append(f"User: {turn.user_message}")
        if turn.assistant_content:
            lines.append(f"Support: {turn.assistant_content}")
        if turn.assistant_card:
            lines.append(f"[Support card: {turn.assistant_card}]")
        lines.append("")

    lines.append("## Latest support reply")
    lines.append(last_assistant_content or "(no text)")
    if last_assistant_card:
        lines.append(f"[Support card: {last_assistant_card}]")
    if ticket_number_on_session:
        lines.append(f"[Session already has active ticket #{ticket_number_on_session}]")

    lines.extend(
        [
            "",
            "## Your task",
            "Produce the simulated user's next message (reply_to_support).",
            "If a ticket was clearly created, set conversation_done=true.",
        ]
    )
    return "\n".join(lines)
