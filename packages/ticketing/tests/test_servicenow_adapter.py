import pytest
from tech_support_ticketing.models import TicketCommand, TicketCommandType
from tech_support_ticketing.providers.servicenow_adapter import ServiceNowAdapter


@pytest.mark.asyncio
async def test_servicenow_adapter_returns_not_implemented():
    adapter = ServiceNowAdapter()
    result = await adapter.execute(
        TicketCommand(
            type=TicketCommandType.CREATE_TICKET,
            payload={"title": "VPN issue"},
        )
    )
    assert result.success is False
    assert result.provider == "servicenow"
    assert result.error_code == "NOT_IMPLEMENTED"
