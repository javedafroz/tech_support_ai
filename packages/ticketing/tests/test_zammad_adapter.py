import httpx
import pytest
import respx
from tech_support_ticketing.models import TicketCommand, TicketCommandType
from tech_support_ticketing.providers.zammad_adapter import ZammadAdapter
from tech_support_zammad import ZammadClient


@pytest.mark.asyncio
async def test_create_ticket_success():
    adapter = ZammadAdapter(ZammadClient("https://zammad.test", "token"))
    cmd = TicketCommand(
        type=TicketCommandType.CREATE_TICKET,
        payload={
            "title": "VPN issue",
            "group": "Network Support",
            "customer_id": "guess:user@company.com",
            "priority": "2 normal",
            "article": {"body": "VPN fails with timeout", "subject": "VPN issue"},
        },
        idempotency_key="11111111-1111-1111-1111-111111111111",
    )
    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 123, "number": "22042", "title": "VPN issue"},
            )
        )
        result = await adapter.execute(cmd)

    assert result.success is True
    assert result.ticket is not None
    assert result.ticket.display_number == "22042"
    assert result.provider == "zammad"


@pytest.mark.asyncio
async def test_search_tickets_success():
    adapter = ZammadAdapter(ZammadClient("https://zammad.test", "token"))
    cmd = TicketCommand(
        type=TicketCommandType.SEARCH_TICKETS,
        payload={"query": "number:22042", "limit": 5},
    )
    with respx.mock:
        respx.get("https://zammad.test/api/v1/tickets/search").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": 42, "number": "22042", "title": "VPN issue"},
                    {"id": 43, "number": "22043", "title": "Email sync issue"},
                ],
            )
        )
        result = await adapter.execute(cmd)

    assert result.success is True
    assert len(result.items) == 2
    assert result.items[0].display_number == "22042"


@pytest.mark.asyncio
async def test_create_ticket_maps_error():
    adapter = ZammadAdapter(ZammadClient("https://zammad.test", "token"))
    cmd = TicketCommand(
        type=TicketCommandType.CREATE_TICKET,
        payload={
            "title": "VPN issue",
            "group": "Network Support",
            "customer_id": "guess:user@company.com",
            "article": {"body": "VPN fails"},
        },
    )
    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(503, text="unavailable")
        )
        result = await adapter.execute(cmd)

    assert result.success is False
    assert result.error_code == "UNAVAILABLE"
    assert result.retryable is True
