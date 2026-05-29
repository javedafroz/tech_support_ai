import httpx
import pytest
import respx
from tech_support_zammad import (
    CreateTicketRequest,
    TicketArticleInput,
    ZammadClient,
    ZammadError,
    ZammadErrorCode,
)


@pytest.fixture
def zammad_base() -> str:
    return "https://zammad.test"


@pytest.fixture
def client(zammad_base: str) -> ZammadClient:
    return ZammadClient(zammad_base, "test-token")


@respx.mock
@pytest.mark.asyncio
async def test_create_ticket_success(client: ZammadClient, zammad_base: str):
    respx.post(f"{zammad_base}/api/v1/tickets").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": 19,
                "number": "22019",
                "title": "VPN connection issue",
                "group_id": 2,
                "state_id": 1,
            },
        )
    )
    ticket = await client.create_ticket(
        CreateTicketRequest(
            title="VPN connection issue",
            group="Network Support",
            customer_id="guess:email:john@company.com",
            priority="3 high",
            article=TicketArticleInput(body="User unable to connect since morning"),
        )
    )
    assert ticket.number == "22019"
    assert ticket.id == 19


@respx.mock
@pytest.mark.asyncio
async def test_get_ticket_success(client: ZammadClient, zammad_base: str):
    respx.get(f"{zammad_base}/api/v1/tickets/19").mock(
        return_value=httpx.Response(
            200,
            json={"id": 19, "number": "22019", "title": "VPN connection issue"},
        )
    )
    ticket = await client.get_ticket(19)
    assert ticket.number == "22019"


@respx.mock
@pytest.mark.asyncio
async def test_search_tickets_list_response(client: ZammadClient, zammad_base: str):
    respx.get(f"{zammad_base}/api/v1/tickets/search").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 19, "number": "22019", "title": "VPN"},
                {"id": 20, "number": "22020", "title": "Email"},
            ],
        )
    )
    result = await client.search_tickets("customer.email:john@company.com")
    assert result.count == 2
    assert result.tickets[0].number == "22019"


@respx.mock
@pytest.mark.asyncio
async def test_create_ticket_retries_on_503(client: ZammadClient, zammad_base: str):
    route = respx.post(f"{zammad_base}/api/v1/tickets")
    route.side_effect = [
        httpx.Response(503, json={"error": "unavailable"}),
        httpx.Response(
            201,
            json={"id": 21, "number": "22021", "title": "Retry ok"},
        ),
    ]
    ticket = await client.create_ticket(
        CreateTicketRequest(
            title="Retry ok",
            group="Software Support",
            customer_id="guess:email:jane@company.com",
            article=TicketArticleInput(body="test"),
        )
    )
    assert ticket.number == "22021"
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_auth_failure_maps_error(client: ZammadClient, zammad_base: str):
    respx.post(f"{zammad_base}/api/v1/tickets").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    with pytest.raises(ZammadError) as exc:
        await client.create_ticket(
            CreateTicketRequest(
                title="x",
                group="Software Support",
                customer_id="guess:email:a@b.com",
                article=TicketArticleInput(body="x"),
            )
        )
    assert exc.value.code == ZammadErrorCode.AUTH_FAILED
