"""Live integration via browser — watch the AI User Sim chat in Chromium."""

from __future__ import annotations

import os

import pytest
from tech_support_zammad import ZammadClient

from tests.integration.scenarios import LIVE_TICKET_SCENARIOS, LiveTicketScenario
from tests.integration.simulated_conversation import run_simulated_conversation
from tests.integration.test_helpers import assert_live_ticket_outcome
from tests.integration.transport import BrowserChatTransport
from tests.integration.user_sim import OpenAIUserSimulator


@pytest.mark.live_ui
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    LIVE_TICKET_SCENARIOS,
    ids=[scenario.id for scenario in LIVE_TICKET_SCENARIOS],
)
async def test_live_create_ticket_in_browser(
    browser_page,
    live_stack,
    live_auth_headers: dict[str, str],
    live_user_email: str,
    user_simulator: OpenAIUserSimulator,
    zammad_client: ZammadClient,
    scenario: LiveTicketScenario,
) -> None:
    transport = BrowserChatTransport(
        browser_page,
        web_url=live_stack.web_url,
        user_email=live_user_email,
        api_base_url=live_stack.api_url,
        api_headers=live_auth_headers,
    )
    result = await run_simulated_conversation(
        transport,
        user_simulator,
        scenario=scenario,
        user_email=live_user_email,
        mode="browser",
    )

    # Pause briefly so the ticket card is visible in the browser window
    pause_ms = int(os.environ.get("INTEGRATION_UI_PAUSE_MS", "2000"))
    if pause_ms > 0 and result.success:
        await browser_page.wait_for_timeout(pause_ms)

    await assert_live_ticket_outcome(
        result=result,
        scenario=scenario,
        zammad_client=zammad_client,
        api_base_url=live_stack.api_url,
        session_headers=live_auth_headers,
        session_id=result.session_id,
    )
