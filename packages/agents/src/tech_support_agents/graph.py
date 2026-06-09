from __future__ import annotations

from langgraph.graph import END, StateGraph
from tech_support_orchestration.models import PolicyOutcome, TicketCommandType

from tech_support_agents.nodes.conversation import conversation_node
from tech_support_agents.nodes.orchestrate import orchestrate_node
from tech_support_agents.nodes.respond import respond_node
from tech_support_agents.nodes.ticket_tool import ticket_tool_node
from tech_support_agents.state import SupportGraphState


def _route_after_conversation(state: SupportGraphState) -> str:
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
    }:
        return "ticket_tool"
    return "respond"


def build_support_graph():
    builder = StateGraph(SupportGraphState)
    builder.add_node("conversation", conversation_node)
    builder.add_node("orchestrate", orchestrate_node)
    builder.add_node("ticket_tool", ticket_tool_node)
    builder.add_node("respond", respond_node)

    builder.set_entry_point("conversation")
    builder.add_conditional_edges(
        "conversation",
        _route_after_conversation,
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
