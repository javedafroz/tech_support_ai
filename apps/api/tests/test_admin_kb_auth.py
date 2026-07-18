from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tech_support_api.dependencies.keycloak_auth import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    AdminPrincipal,
    require_admin_principal,
    require_kb_admin,
    require_kb_editor,
)


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/admin/kb/me",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_admin_rejects_x_user_id() -> None:
    request = _request({"X-User-Id": "dev@company.com"})
    with pytest.raises(HTTPException) as exc:
        await require_admin_principal(request)
    assert exc.value.status_code == 401
    assert "Keycloak" in exc.value.detail


@pytest.mark.asyncio
async def test_admin_requires_bearer() -> None:
    request = _request({})
    with pytest.raises(HTTPException) as exc:
        await require_admin_principal(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_kb_editor_role_gate() -> None:
    principal = AdminPrincipal(
        subject="u1",
        username="user",
        email=None,
        roles=frozenset({"offline_access"}),
    )
    with pytest.raises(HTTPException) as exc:
        await require_kb_editor(principal)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_kb_admin_allows_publish_role() -> None:
    principal = AdminPrincipal(
        subject="u1",
        username="admin",
        email=None,
        roles=frozenset({ROLE_EDITOR, ROLE_ADMIN}),
    )
    result = await require_kb_admin(principal)
    assert result is principal
