"""Shared assertions for live integration tests."""

from __future__ import annotations

from httpx import AsyncClient
from tech_support_zammad import ZammadClient

from tests.integration.evaluator.rules import assert_ticket_hard_gates
from tests.integration.scenarios import LiveTicketScenario
from tests.integration.user_sim.schema import ConversationResult


async def assert_live_ticket_outcome(
    *,
    result: ConversationResult,
    scenario: LiveTicketScenario,
    zammad_client: ZammadClient,
    session_client: AsyncClient | None = None,
    session_headers: dict[str, str] | None = None,
    api_base_url: str | None = None,
    session_id: str | None = None,
) -> None:
    assert result.success, (
        f"Scenario {scenario.id} failed: {result.failure_reason}. "
        f"See tests/integration/artifacts/ for transcript."
    )

    if result.ticket_id is not None:
        ticket = await zammad_client.get_ticket(result.ticket_id)
    else:
        search = await zammad_client.search_tickets(f"number:{result.ticket_number}", limit=5)
        assert search.tickets, f"Ticket #{result.ticket_number} not found in Zammad"
        ticket = search.tickets[0]

    active_ticket: str | None = None
    sid = session_id or result.session_id
    if session_client and session_headers:
        session = await session_client.get(
            f"/api/v1/chat/sessions/{sid}",
            headers=session_headers,
        )
        session.raise_for_status()
        active_ticket = session.json().get("active_ticket_number")
    elif api_base_url and session_headers:
        async with AsyncClient(base_url=api_base_url) as client:
            session = await client.get(
                f"/api/v1/chat/sessions/{sid}",
                headers=session_headers,
            )
            session.raise_for_status()
            active_ticket = session.json().get("active_ticket_number")

    assert_ticket_hard_gates(
        result=result,
        ticket=ticket,
        scenario=scenario,
        session_active_ticket=active_ticket,
    )
