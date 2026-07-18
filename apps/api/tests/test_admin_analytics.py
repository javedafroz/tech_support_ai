from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tech_support_api.db.models import (
    ChatMessage,
    ChatSession,
    KbDeflectionEvent,
    KbDocument,
)
from tech_support_api.dependencies.keycloak_auth import (
    ROLE_EDITOR,
    AdminPrincipal,
    require_kb_editor,
)
from tech_support_api.main import app


def _editor_principal() -> AdminPrincipal:
    return AdminPrincipal(
        subject="admin-1",
        username="kb-editor",
        email="editor@example.com",
        roles=frozenset({ROLE_EDITOR}),
    )


@pytest.fixture
async def analytics_client(api_client: AsyncClient):
    async def _override_editor() -> AdminPrincipal:
        return _editor_principal()

    app.dependency_overrides[require_kb_editor] = _override_editor
    yield api_client
    app.dependency_overrides.pop(require_kb_editor, None)


@pytest.mark.asyncio
async def test_analytics_requires_auth(api_client: AsyncClient) -> None:
    res = await api_client.get("/api/v1/admin/analytics/summary")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_analytics_rejects_x_user_id(api_client: AsyncClient) -> None:
    res = await api_client.get(
        "/api/v1/admin/analytics/summary",
        headers={"X-User-Id": "dev@company.com"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_summary_and_sessions_with_deflections(
    analytics_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    doc_id = uuid.uuid4()
    session_resolved = uuid.uuid4()
    session_escalated = uuid.uuid4()
    session_plain = uuid.uuid4()
    now = datetime.now(UTC)

    db_session.add(
        KbDocument(
            id=doc_id,
            title="VPN AnyConnect DPD",
            slug=f"vpn-anyconnect-dpd-{doc_id.hex[:8]}",
            status="published",
            source_content_type="text/markdown",
            object_key=f"kb/{doc_id}.md",
            version=1,
        )
    )
    await db_session.flush()

    db_session.add_all(
        [
            ChatSession(
                id=session_resolved,
                user_id="alice@company.com",
                status="active",
                active_ticket_number=None,
                created_at=now,
                updated_at=now,
            ),
            ChatSession(
                id=session_escalated,
                user_id="bob@company.com",
                status="active",
                active_ticket_number="ZAM-1001",
                created_at=now,
                updated_at=now,
            ),
            ChatSession(
                id=session_plain,
                user_id="carol@company.com",
                status="active",
                active_ticket_number=None,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    await db_session.flush()

    db_session.add_all(
        [
            ChatMessage(
                id=uuid.uuid4(),
                session_id=session_resolved,
                role="user",
                content="VPN keeps dropping",
            ),
            ChatMessage(
                id=uuid.uuid4(),
                session_id=session_resolved,
                role="assistant",
                content="Try reconnecting after 30s",
            ),
            ChatMessage(
                id=uuid.uuid4(),
                session_id=session_escalated,
                role="user",
                content="Still broken",
            ),
            KbDeflectionEvent(
                id=uuid.uuid4(),
                session_id=session_resolved,
                document_id=doc_id,
                outcome="resolved",
                steps_count=1,
            ),
            KbDeflectionEvent(
                id=uuid.uuid4(),
                session_id=session_escalated,
                document_id=doc_id,
                outcome="escalated",
                steps_count=2,
            ),
        ]
    )
    await db_session.commit()

    summary = await analytics_client.get("/api/v1/admin/analytics/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_conversations"] >= 3
    assert body["total_messages"] >= 3
    assert body["tickets_created"] >= 1
    assert body["deflections_resolved"] >= 1
    assert body["deflections_escalated"] >= 1
    assert 0 < body["deflection_rate"] <= 1
    titles = {item["title"] for item in body["by_handbook"]}
    assert "VPN AnyConnect DPD" in titles

    sessions = await analytics_client.get("/api/v1/admin/analytics/sessions?limit=50&offset=0")
    assert sessions.status_code == 200
    items = {item["id"]: item for item in sessions.json()["items"]}
    assert items[str(session_resolved)]["deflection_outcome"] == "resolved"
    assert items[str(session_resolved)]["handbook_title"] == "VPN AnyConnect DPD"
    assert items[str(session_resolved)]["message_count"] == 2
    assert items[str(session_escalated)]["deflection_outcome"] == "escalated"
    assert items[str(session_escalated)]["active_ticket_number"] == "ZAM-1001"
    assert items[str(session_plain)]["deflection_outcome"] is None

    transcript = await analytics_client.get(
        f"/api/v1/admin/analytics/sessions/{session_resolved}/messages"
    )
    assert transcript.status_code == 200
    messages = transcript.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "VPN" in (messages[0]["content"] or "")


@pytest.mark.asyncio
async def test_transcript_not_found(analytics_client: AsyncClient) -> None:
    res = await analytics_client.get(
        f"/api/v1/admin/analytics/sessions/{uuid.uuid4()}/messages"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_trends_returns_daily_series(
    analytics_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    session_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    db_session.add(
        KbDocument(
            id=doc_id,
            title="Trends handbook",
            slug=f"trends-{doc_id.hex[:8]}",
            status="published",
            source_content_type="text/markdown",
            object_key=f"kb/{doc_id}.md",
            version=1,
        )
    )
    await db_session.flush()
    db_session.add(
        ChatSession(
            id=session_id,
            user_id="trends@company.com",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()
    db_session.add(
        KbDeflectionEvent(
            id=uuid.uuid4(),
            session_id=session_id,
            document_id=doc_id,
            outcome="resolved",
            steps_count=1,
            created_at=now,
        )
    )
    await db_session.commit()

    res = await analytics_client.get("/api/v1/admin/analytics/trends?days=7")
    assert res.status_code == 200
    body = res.json()
    assert body["days"] == 7
    assert len(body["items"]) == 7
    assert all("date" in item for item in body["items"])
    today = now.date().isoformat()
    today_row = next(item for item in body["items"] if item["date"] == today)
    assert today_row["conversations"] >= 1
    assert today_row["resolved"] >= 1


@pytest.mark.asyncio
async def test_summary_filters_by_date_range(
    analytics_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=45)
    recent_id = uuid.uuid4()
    old_id = uuid.uuid4()

    db_session.add_all(
        [
            ChatSession(
                id=recent_id,
                user_id="recent@company.com",
                status="active",
                created_at=now,
                updated_at=now,
            ),
            ChatSession(
                id=old_id,
                user_id="old@company.com",
                status="active",
                created_at=old,
                updated_at=old,
            ),
        ]
    )
    await db_session.commit()

    start = (now.date() - timedelta(days=6)).isoformat()
    end = now.date().isoformat()
    res = await analytics_client.get(
        f"/api/v1/admin/analytics/summary?start_date={start}&end_date={end}"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_conversations"] >= 1

    sessions = await analytics_client.get(
        f"/api/v1/admin/analytics/sessions?start_date={start}&end_date={end}&limit=100"
    )
    assert sessions.status_code == 200
    ids = {item["id"] for item in sessions.json()["items"]}
    assert str(recent_id) in ids
    assert str(old_id) not in ids

    bad = await analytics_client.get(
        f"/api/v1/admin/analytics/summary?start_date={end}&end_date={start}"
    )
    assert bad.status_code == 422

