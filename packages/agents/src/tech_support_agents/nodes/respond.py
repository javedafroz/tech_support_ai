from __future__ import annotations

from langchain_core.messages import AIMessage

from tech_support_agents.state import SupportGraphState


async def respond_node(state: SupportGraphState) -> dict:
    ticket_number = state.get("active_ticket_number")
    ui_card = state.get("ui_card") or {}

    # Prefer the ticket-created confirmation over any leftover clarify reply from
    # the conversation node (e.g. after troubleshoot escalation).
    if ticket_number and ui_card.get("card_type") == "ticket_created":
        reply = _ticket_created_reply(ticket_number, state, ui_card)
        return {"assistant_reply": reply, "messages": [AIMessage(content=reply)]}

    if state.get("assistant_reply"):
        reply = state["assistant_reply"]
        return {
            "assistant_reply": reply,
            "messages": [AIMessage(content=reply)],
        }

    if ticket_number:
        reply = _ticket_status_reply(ticket_number, ui_card)
        return {"assistant_reply": reply, "messages": [AIMessage(content=reply)]}

    reply = "How can I help you next?"
    return {"assistant_reply": reply, "messages": [AIMessage(content=reply)]}


def _ticket_created_reply(
    ticket_number: str,
    state: SupportGraphState,
    ui_card: dict,
) -> str:
    group_name = ui_card.get("group") or ""
    if not group_name and state.get("approved_command"):
        group_name = state["approved_command"].payload.get("group", "")

    message = f"I've created your support ticket #{ticket_number}."
    if group_name:
        message += f" It's been assigned to {group_name}."
    message += " Our team will follow up with you soon."
    return message


def _ticket_status_reply(ticket_number: str, ui_card: dict) -> str:
    state_label = ui_card.get("state") or "open"
    group_name = ui_card.get("group") or ""
    message = f"Your ticket #{ticket_number} is currently {state_label}."
    if group_name:
        message += f" It's handled by {group_name}."
    return message
