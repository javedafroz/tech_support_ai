from __future__ import annotations

import os
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TicketingSettings:
    provider: str = "zammad"
    zammad_base_url: str | None = None
    zammad_api_token: str | None = None
    zammad_auth_scheme: str = "Bearer"

    @classmethod
    def from_env(cls) -> TicketingSettings:
        return cls(
            provider=os.environ.get("TICKETING_PROVIDER", "zammad").strip().lower(),
            zammad_base_url=os.environ.get("ZAMMAD_BASE_URL"),
            zammad_api_token=os.environ.get("ZAMMAD_API_TOKEN"),
            zammad_auth_scheme=os.environ.get("ZAMMAD_AUTH_SCHEME", "Bearer"),
        )

    def is_configured(self) -> bool:
        if self.provider == "zammad":
            return bool(self.zammad_base_url and self.zammad_api_token)
        if self.provider == "servicenow":
            return True
        return False

    def configuration_error(self) -> str | None:
        if self.is_configured():
            return None
        if self.provider == "zammad":
            return "ZAMMAD_BASE_URL and ZAMMAD_API_TOKEN must be set for provider zammad"
        return f"Ticketing provider '{self.provider}' is not configured"


_settings: TicketingSettings = TicketingSettings.from_env()


def configure_ticketing(settings: TicketingSettings) -> None:
    """Apply settings to the ticketing package and sync env for adapters."""
    global _settings
    _settings = settings
    os.environ["TICKETING_PROVIDER"] = settings.provider
    if settings.zammad_base_url:
        os.environ["ZAMMAD_BASE_URL"] = settings.zammad_base_url
    if settings.zammad_api_token:
        os.environ["ZAMMAD_API_TOKEN"] = settings.zammad_api_token
    os.environ["ZAMMAD_AUTH_SCHEME"] = settings.zammad_auth_scheme


def get_ticketing_settings() -> TicketingSettings:
    return _settings


def merge_ticketing_settings(*, provider: str | None = None) -> TicketingSettings:
    """Merge explicit overrides with current env-backed settings."""
    current = TicketingSettings.from_env()
    if provider is None:
        return current
    return replace(current, provider=provider.strip().lower())
