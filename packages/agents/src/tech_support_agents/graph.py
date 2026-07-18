from __future__ import annotations

from langgraph.graph import END, StateGraph
from tech_support_orchestration.models import IntentName, PolicyOutcome, TicketCommandType

from tech_support_agents.nodes.conversation import conversation_node
from tech_support_agents.nodes.orchestrate import orchestrate_node
from tech_support_agents.nodes.respond import respond_node
from tech_support_agents.nodes.ticket_tool import ticket_tool_node
from tech_support_agents.nodes.troubleshoot import troubleshoot_node
from tech_support_agents.state import SupportGraphState


def _route_after_conversation(state: SupportGraphState) -> str:
    kb_on = bool(state.get("kb_rag_enabled"))
    ts = state.get("troubleshoot") or {}
    intent = state.get("structured_intent")
    is_create_ticket = intent is not None and intent.intent == IntentName.CREATE_TICKET

    # Continue an in-progress guided session regardless of LLM readiness.
    if kb_on and ts.get("status") == "guiding":
        return "troubleshoot"

    # Troubleshoot-first: engage as soon as a support issue is detected, before
    # ticket slot-filling. Skip if we already tried (skipped/resolved/escalated)
    # or if the user is working an existing ticket.
    if (
        kb_on
        and not state.get("active_ticket_number")
        and ts.get("status") not in {"skipped", "resolved", "escalated"}
        and (state.get("is_support_issue") or is_create_ticket)
    ):
        return "troubleshoot"

    if state.get("needs_clarification") or intent is None:
        return "respond"
    return "orchestrate"


def _route_after_troubleshoot(state: SupportGraphState) -> str:
    ts = state.get("troubleshoot") or {}
    status = ts.get("status")
    if status in {"guiding", "resolved"}:
        return "respond"
    if status == "escalated":
        return "orchestrate"
    # skipped (no matching handbook) — defer to normal gating so the existing
    # clarify-then-ticket flow takes over.
    if state.get("needs_clarification") or state.get("structured_intent") is None:
        return "respond"
    return "orchestrate"


def _route_after_orchestrate(state: SupportGraphState) -> str:
    result = state.get("orchestration_result")
    if result is None or result.outcome != PolicyOutcome.APPROVED:
        return "respond"
    command = state.get("approved_command")
    if command and command.type in {
        TicketCommandType.CREATE_TICKET,
        TicketCommandType.SEARCH_TICKETS,
        TicketCommandType.ADD_ATTACHMENT,
    }:
        return "ticket_tool"
    return "respond"


def build_support_graph():
    builder = StateGraph(SupportGraphState)
    builder.add_node("conversation", conversation_node)
    builder.add_node("troubleshoot", troubleshoot_node)
    builder.add_node("orchestrate", orchestrate_node)
    builder.add_node("ticket_tool", ticket_tool_node)
    builder.add_node("respond", respond_node)

    builder.set_entry_point("conversation")
    builder.add_conditional_edges(
        "conversation",
        _route_after_conversation,
        {
            "troubleshoot": "troubleshoot",
            "orchestrate": "orchestrate",
            "respond": "respond",
        },
    )
    builder.add_conditional_edges(
        "troubleshoot",
        _route_after_troubleshoot,
        {"orchestrate": "orchestrate", "respond": "respond"},
    )
    builder.add_conditional_edges(
        "orchestrate",
        _route_after_orchestrate,
        {"ticket_tool": "ticket_tool", "respond": "respond"},
    )
    builder.add_edge("ticket_tool", "respond")
    builder.add_edge("respond", END)

    return builder


def compile_support_graph(checkpointer=None):
    return build_support_graph().compile(checkpointer=checkpointer)
