import pytest
from tech_support_ticketing.factory import build_ticket_gateway
from tech_support_ticketing.providers.zammad_adapter import ZammadAdapter
from tech_support_ticketing.settings import TicketingSettings, configure_ticketing


def test_build_ticket_gateway_returns_zammad_adapter(monkeypatch):
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://zammad.test",
            zammad_api_token="token",
        )
    )
    gateway = build_ticket_gateway()
    assert isinstance(gateway, ZammadAdapter)


def test_build_ticket_gateway_rejects_unconfigured(monkeypatch):
    configure_ticketing(TicketingSettings(provider="zammad"))
    with pytest.raises(ValueError, match="ZAMMAD_BASE_URL"):
        build_ticket_gateway()


def test_build_ticket_gateway_returns_servicenow_stub(monkeypatch):
    configure_ticketing(TicketingSettings(provider="servicenow"))
    from tech_support_ticketing.providers.servicenow_adapter import ServiceNowAdapter

    gateway = build_ticket_gateway()
    assert isinstance(gateway, ServiceNowAdapter)


def test_build_ticket_gateway_rejects_unknown_provider(monkeypatch):
    configure_ticketing(TicketingSettings(provider="jira_sm"))
    with pytest.raises(ValueError, match="Unsupported ticketing provider"):
        build_ticket_gateway()
