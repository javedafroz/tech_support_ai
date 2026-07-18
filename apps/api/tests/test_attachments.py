import io

import pytest
from httpx import AsyncClient
from tech_support_storage import get_object_storage


@pytest.mark.asyncio
async def test_upload_attachment(api_client: AsyncClient, auth_headers):
    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    files = {"file": ("notes.txt", io.BytesIO(b"vpn error log"), "text/plain")}
    upload = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/attachments",
        files=files,
        headers=auth_headers,
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["filename"] == "notes.txt"
    assert body["mime_type"] == "text/plain"
    assert body["size_bytes"] == 13

    storage = get_object_storage()
    assert len(storage.get_object(f"sessions/{session_id}/{body['id']}/notes.txt")) == 13


@pytest.mark.asyncio
async def test_send_message_with_attachment_ids(api_client: AsyncClient, auth_headers):
    session = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    session_id = session.json()["id"]

    files = {"file": ("screenshot.png", io.BytesIO(b"\x89PNG\r\n"), "image/png")}
    upload = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/attachments",
        files=files,
        headers=auth_headers,
    )
    attachment_id = upload.json()["id"]

    send = await api_client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Please see the attached screenshot", "attachment_ids": [attachment_id]},
        headers=auth_headers,
    )
    assert send.status_code == 201
    payload = send.json()
    assert payload["user_message"]["attachments"]
    assert payload["user_message"]["attachments"][0]["filename"] == "screenshot.png"
