import pytest
from httpx import ASGITransport, AsyncClient
from jwt import encode as jwt_encode
from tech_support_api.config import get_settings
from tech_support_api.dependencies.auth import _user_from_bearer
from tech_support_api.main import app


@pytest.mark.asyncio
async def test_missing_identity_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat/sessions", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dev_header_allows_session_create(api_client: AsyncClient, auth_headers):
    response = await api_client.post("/api/v1/chat/sessions", json={}, headers=auth_headers)
    assert response.status_code == 201


def test_jwt_bearer_extracts_subject(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-for-jwt-auth-tests-only-32")
    get_settings.cache_clear()

    token = jwt_encode(
        {"sub": "jwt-user@company.com"},
        "test-secret-for-jwt-auth-tests-only-32",
        algorithm="HS256",
    )
    assert _user_from_bearer(token) == "jwt-user@company.com"
    get_settings.cache_clear()
