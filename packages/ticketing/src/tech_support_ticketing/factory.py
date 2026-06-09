from __future__ import annotations

from tech_support_zammad import ZammadClient

from tech_support_ticketing.networking import resolve_zammad_base_url
from tech_support_ticketing.providers.servicenow_adapter import ServiceNowAdapter
from tech_support_ticketing.providers.zammad_adapter import ZammadAdapter
from tech_support_ticketing.settings import get_ticketing_settings


def build_ticket_gateway():
    settings = get_ticketing_settings()
    provider = settings.provider

    if provider == "servicenow":
        return ServiceNowAdapter()

    if provider != "zammad":
        raise ValueError(f"Unsupported ticketing provider: {provider}")

    error = settings.configuration_error()
    if error:
        raise ValueError(error)

    base_url = resolve_zammad_base_url(settings.zammad_base_url or "")
    client = ZammadClient(
        base_url,
        settings.zammad_api_token or "",
        auth_scheme=settings.zammad_auth_scheme,
    )
    return ZammadAdapter(client)
