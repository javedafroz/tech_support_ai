import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_session_messages_persist_after_reload(api_client: AsyncClient, auth_headers):
    create = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    assert create.status_code == 201
    session_id = create.json()["id"]

    send = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "My VPN is down"},
        headers=auth_headers,
    )
    assert send.status_code == 201
    body = send.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"

    listed = await api_client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] >= 3  # welcome + user + system + assistant
    assert len(payload["messages"]) >= 2
    roles = {m["role"] for m in payload["messages"]}
    assert "user" in roles
    assert "assistant" in roles

    resumed = await api_client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert resumed.status_code == 200

    context = await api_client.get(
        f"/api/v1/chat/sessions/{session_id}/context",
        headers=auth_headers,
    )
    assert context.status_code == 200
    assert context.json()["context"]["message_count"] >= 2


@pytest.mark.asyncio
async def test_list_sessions_for_user(api_client: AsyncClient, auth_headers):
    await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    listed = await api_client.get("/api/v1/chat/sessions", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["sessions"]) >= 1
