import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_graph_invoke_returns_canned_reply(api_client: AsyncClient, auth_headers):
    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    response = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/graph/invoke",
        json={"content": "Hello"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "Hi" in body["assistant_content"]
    assert body["detected_intent"] == "ChitChat"
    assert len(body["system_statuses"]) >= 1


@pytest.mark.asyncio
async def test_send_message_uses_mock_graph(api_client: AsyncClient, auth_headers):
    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    send = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "My VPN is broken"},
        headers=auth_headers,
    )
    assert send.status_code == 201
    body = send.json()
    assert body["detected_intent"] == "CreateTicket"
    assistant_text = body["assistant_message"]["content"].lower()
    assert "vpn" in assistant_text or "help" in assistant_text

    listed = await api_client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=auth_headers,
    )
    roles = [m["role"] for m in listed.json()["messages"]]
    assert "system" in roles
    assert "assistant" in roles
