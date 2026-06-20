import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_config_reports_thought_streaming_flag(
    api_client: AsyncClient,
    monkeypatch,
):
    monkeypatch.setenv("THOUGHT_STREAMING_ENABLED", "true")
    from tech_support_api.config import get_settings

    get_settings.cache_clear()

    response = await api_client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json()["thought_streaming_enabled"] is True

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_message_stream_disabled_returns_404(api_client: AsyncClient, auth_headers, monkeypatch):
    monkeypatch.setenv("THOUGHT_STREAMING_ENABLED", "false")
    from tech_support_api.config import get_settings

    get_settings.cache_clear()

    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    response = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": "Hello"},
        headers=auth_headers,
    )
    assert response.status_code == 404

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_message_stream_emits_thoughts_and_done(
    api_client: AsyncClient,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setenv("THOUGHT_STREAMING_ENABLED", "true")
    monkeypatch.setenv("GRAPH_ENABLED", "false")
    from tech_support_api.config import get_settings

    get_settings.cache_clear()

    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    response = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": "Hello"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = []
    for block in response.text.split("\n\n"):
        if not block.startswith("data: "):
            continue
        events.append(json.loads(block.removeprefix("data: ")))

    assert any(event["type"] == "thought" for event in events)
    done_events = [event for event in events if event["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["assistant_message"]["content"]

    get_settings.cache_clear()
