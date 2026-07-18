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


@pytest.mark.asyncio
async def test_message_list_keeps_user_before_assistant_in_same_turn(
    api_client: AsyncClient, auth_headers
):
    """Messages in one turn share a created_at; seq must keep user before assistant."""
    create = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = create.json()["id"]

    send = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Restart worked"},
        headers=auth_headers,
    )
    assert send.status_code == 201
    user_id = send.json()["user_message"]["id"]
    assistant_id = send.json()["assistant_message"]["id"]

    listed = await api_client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    messages = listed.json()["messages"]
    ids = [m["id"] for m in messages]
    assert ids.index(user_id) < ids.index(assistant_id)

    # Within the turn, every system status must also sit between user and assistant
    # or after user (inserted before assistant in finalize).
    user_idx = ids.index(user_id)
    assistant_idx = ids.index(assistant_id)
    between = messages[user_idx + 1 : assistant_idx]
    assert all(m["role"] == "system" for m in between)
