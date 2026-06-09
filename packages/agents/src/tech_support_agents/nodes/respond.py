from __future__ import annotations

from langchain_core.messages import AIMessage

from tech_support_agents.state import SupportGraphState


async def respond_node(state: SupportGraphState) -> dict:
    if state.get("assistant_reply"):
        return {"messages": [AIMessage(content=state["assistant_reply"])]}

    ticket_number = state.get("active_ticket_number")

    if ticket_number:
        group_name = ""
        if state.get("approved_command"):
            group_name = state["approved_command"].payload.get("group", "")
        reply = (
            f"Your support ticket **#{ticket_number}** has been created successfully"
            + (f" and assigned to **{group_name}**." if group_name else ".")
        )
        return {"assistant_reply": reply, "messages": [AIMessage(content=reply)]}

    return {
        "assistant_reply": "How can I help you next?",
        "messages": [AIMessage(content="How can I help you next?")],
    }
