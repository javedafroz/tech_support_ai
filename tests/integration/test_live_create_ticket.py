"""Live integration via HTTP API (headless, fast)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from tech_support_zammad import ZammadClient

from tests.integration.scenarios import LIVE_TICKET_SCENARIOS, LiveTicketScenario
from tests.integration.simulated_conversation import run_simulated_conversation
from tests.integration.test_helpers import assert_live_ticket_outcome
from tests.integration.transport import ApiChatTransport
from tests.integration.user_sim import OpenAIUserSimulator


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    LIVE_TICKET_SCENARIOS,
    ids=[scenario.id for scenario in LIVE_TICKET_SCENARIOS],
)
async def test_live_create_ticket_for_issue_scenario(
    live_api_client: AsyncClient,
    live_auth_headers: dict[str, str],
    live_user_email: str,
    user_simulator: OpenAIUserSimulator,
    zammad_client: ZammadClient,
    scenario: LiveTicketScenario,
) -> None:
    transport = ApiChatTransport(live_api_client, headers=live_auth_headers)
    result = await run_simulated_conversation(
        transport,
        user_simulator,
        scenario=scenario,
        user_email=live_user_email,
        mode="api",
    )
    await assert_live_ticket_outcome(
        result=result,
        scenario=scenario,
        zammad_client=zammad_client,
        session_client=live_api_client,
        session_headers=live_auth_headers,
    )
