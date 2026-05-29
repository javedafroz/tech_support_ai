import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_uses_langgraph_when_enabled(api_client: AsyncClient, auth_headers, monkeypatch):
    monkeypatch.setenv("GRAPH_ENABLED", "true")
    monkeypatch.setenv("GRAPH_LLM_MODE", "mock")
    from tech_support_api.config import get_settings

    get_settings.cache_clear()

    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    send = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Hello"},
        headers=auth_headers,
    )
    assert send.status_code == 201
    body = send.json()
    assert "Hi" in body["assistant_message"]["content"]

    get_settings.cache_clear()
