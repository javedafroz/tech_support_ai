from uuid import uuid4

import httpx
import pytest
import respx
from tech_support_agents.nodes.ticket_tool import ticket_tool_node
from tech_support_orchestration.models import TicketCommand, TicketCommandType
from tech_support_ticketing.settings import TicketingSettings, configure_ticketing


def _approved_command(command_type: TicketCommandType, payload: dict) -> TicketCommand:
    return TicketCommand(
        type=command_type,
        session_id=uuid4(),
        user_id="user@test.com",
        payload=payload,
    )


@pytest.mark.asyncio
async def test_ticket_tool_search_single_match():
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://zammad.test",
            zammad_api_token="token",
        )
    )
    with respx.mock:
        respx.get("https://zammad.test/api/v1/tickets/search").mock(
            return_value=httpx.Response(
                200,
                json=[{"id": 42, "number": "22042", "title": "VPN issue"}],
            )
        )
        result = await ticket_tool_node(
            {
                "approved_command": _approved_command(
                    TicketCommandType.SEARCH_TICKETS,
                    {"query": "number:22042", "limit": 5},
                ),
                "system_statuses": [],
            }
        )

    assert result["active_ticket_number"] == "22042"
    assert result["provider_response"]["count"] == 1
    assert result["ui_card"]["card_type"] == "ticket_status"
    assert "22042" in result["assistant_reply"]


@pytest.mark.asyncio
async def test_ticket_tool_search_multiple_matches_requests_clarification():
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://zammad.test",
            zammad_api_token="token",
        )
    )
    with respx.mock:
        respx.get("https://zammad.test/api/v1/tickets/search").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 42, "number": "22042", "title": "VPN issue"},
                    {"id": 43, "number": "22043", "title": "Email issue"},
                ],
            )
        )
        result = await ticket_tool_node(
            {
                "approved_command": _approved_command(
                    TicketCommandType.SEARCH_TICKETS,
                    {"query": "customer.email:user@test.com", "limit": 5},
                ),
                "system_statuses": [],
            }
        )

    assert result["needs_clarification"] is True
    assert "22042" in result["assistant_reply"]
    assert "22043" in result["assistant_reply"]


@pytest.mark.asyncio
async def test_ticket_tool_create_sets_provider_response():
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://zammad.test",
            zammad_api_token="token",
        )
    )
    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 99, "number": "22099", "title": "Printer issue"},
            )
        )
        result = await ticket_tool_node(
            {
                "approved_command": _approved_command(
                    TicketCommandType.CREATE_TICKET,
                    {
                        "title": "Printer issue",
                        "group": "Hardware Support",
                        "customer_id": "guess:user@test.com",
                        "priority": "2 normal",
                        "article": {"body": "Printer offline", "subject": "Printer issue"},
                    },
                ),
                "system_statuses": [],
            }
        )

    assert result["provider_response"]["number"] == "22099"
    assert result["ui_card"]["card_type"] == "ticket_created"
