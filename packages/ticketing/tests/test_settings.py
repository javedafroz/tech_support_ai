import os

from tech_support_ticketing.settings import (
    TicketingSettings,
    configure_ticketing,
    get_ticketing_settings,
    merge_ticketing_settings,
)


def test_ticketing_settings_configured(monkeypatch):
    monkeypatch.setenv("TICKETING_PROVIDER", "zammad")
    monkeypatch.setenv("ZAMMAD_BASE_URL", "https://zammad.test")
    monkeypatch.setenv("ZAMMAD_API_TOKEN", "token")
    settings = TicketingSettings.from_env()
    assert settings.is_configured() is True
    assert settings.configuration_error() is None


def test_ticketing_settings_missing_credentials(monkeypatch):
    monkeypatch.delenv("ZAMMAD_BASE_URL", raising=False)
    monkeypatch.delenv("ZAMMAD_API_TOKEN", raising=False)
    settings = TicketingSettings(provider="zammad")
    assert settings.is_configured() is False
    assert "ZAMMAD_BASE_URL" in (settings.configuration_error() or "")


def test_configure_ticketing_syncs_env(monkeypatch):
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://configured.test",
            zammad_api_token="abc",
            zammad_auth_scheme="Token",
        )
    )
    assert get_ticketing_settings().zammad_base_url == "https://configured.test"
    assert os.environ.get("ZAMMAD_BASE_URL") == "https://configured.test"
    assert os.environ.get("ZAMMAD_API_TOKEN") == "abc"


def test_merge_ticketing_settings_overrides_provider(monkeypatch):
    monkeypatch.setenv("TICKETING_PROVIDER", "zammad")
    merged = merge_ticketing_settings(provider="zammad")
    assert merged.provider == "zammad"
