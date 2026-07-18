"""Deterministic evaluation rules for live integration tests."""

from __future__ import annotations

from tech_support_zammad import Ticket

from tests.integration.scenarios import LiveTicketScenario
from tests.integration.user_sim.schema import ConversationResult


def title_matches_scenario(title: str, scenario: LiveTicketScenario) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in scenario.title_keywords)


def assert_ticket_hard_gates(
    *,
    result: ConversationResult,
    ticket: Ticket,
    scenario: LiveTicketScenario,
    session_active_ticket: str | None,
) -> None:
    assert result.success, result.failure_reason or "Conversation did not succeed"
    assert result.ticket_number, "Expected ticket number on success"
    assert str(result.ticket_number).isdigit(), (
        f"Expected numeric Zammad ticket number, got {result.ticket_number!r}"
    )
    assert str(ticket.number) == str(result.ticket_number), (
        f"API ticket {result.ticket_number} != Zammad {ticket.number}"
    )
    assert ticket.title.strip(), "Zammad ticket must have a title"
    assert title_matches_scenario(ticket.title, scenario), (
        f"Title {ticket.title!r} does not match scenario {scenario.id} keywords "
        f"{scenario.title_keywords}"
    )
    assert session_active_ticket == str(result.ticket_number), (
        f"Session active_ticket_number {session_active_ticket!r} != {result.ticket_number}"
    )
    assert result.turns_used >= 1
