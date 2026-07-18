"""Keycloak JWT validation for admin API routes. Rejects chat X-User-Id auth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from tech_support_api.config import Settings, get_settings

ROLE_EDITOR = "kb_editor"
ROLE_ADMIN = "kb_admin"
_ADMIN_ROLES = frozenset({ROLE_EDITOR, ROLE_ADMIN})


@dataclass(frozen=True)
class AdminPrincipal:
    subject: str
    username: str | None
    email: str | None
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles

    @property
    def can_edit(self) -> bool:
        return bool(self.roles & _ADMIN_ROLES)

    @property
    def can_publish(self) -> bool:
        return ROLE_ADMIN in self.roles


_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_url(settings: Settings) -> str:
    if settings.keycloak_jwks_url:
        return settings.keycloak_jwks_url
    base = settings.keycloak_url.rstrip("/")
    realm = settings.keycloak_realm
    return f"{base}/realms/{realm}/protocol/openid-connect/certs"


def _issuer(settings: Settings) -> str:
    return f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"


def _get_jwks_client(settings: Settings) -> PyJWKClient:
    url = _jwks_url(settings)
    if url not in _jwks_clients:
        _jwks_clients[url] = PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwks_clients[url]


def _roles_from_payload(payload: dict[str, Any]) -> frozenset[str]:
    roles: set[str] = set()
    realm = payload.get("realm_access") or {}
    for role in realm.get("roles") or []:
        roles.add(str(role))
    resource = payload.get("resource_access") or {}
    for client_roles in resource.values():
        for role in (client_roles or {}).get("roles") or []:
            roles.add(str(role))
    return frozenset(roles)


def decode_keycloak_token(token: str, settings: Settings | None = None) -> AdminPrincipal:
    settings = settings or get_settings()
    if not settings.keycloak_url or not settings.keycloak_realm:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak is not configured for admin authentication",
        )

    try:
        signing_key = _get_jwks_client(settings).get_signing_key_from_jwt(token)
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256"],
            "issuer": _issuer(settings),
            "options": {
                "verify_aud": bool(settings.keycloak_api_audience),
                "require": ["exp", "sub"],
            },
        }
        if settings.keycloak_api_audience:
            decode_kwargs["audience"] = settings.keycloak_api_audience
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Keycloak token",
        ) from exc

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub)",
        )

    return AdminPrincipal(
        subject=subject,
        username=(payload.get("preferred_username") or None),
        email=(payload.get("email") or None),
        roles=_roles_from_payload(payload),
    )


async def require_admin_principal(request: Request) -> AdminPrincipal:
    """Admin routes: Bearer Keycloak JWT only. Never accept X-User-Id."""
    if request.headers.get("X-User-Id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin routes require Keycloak Bearer token; X-User-Id is not accepted",
        )

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    return decode_keycloak_token(token)


async def require_kb_editor(
    principal: AdminPrincipal = Depends(require_admin_principal),
) -> AdminPrincipal:
    if not principal.can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires realm role {ROLE_EDITOR} or {ROLE_ADMIN}",
        )
    return principal


async def require_kb_admin(
    principal: AdminPrincipal = Depends(require_admin_principal),
) -> AdminPrincipal:
    if not principal.can_publish:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires realm role {ROLE_ADMIN}",
        )
    return principal


def reset_keycloak_cache() -> None:
    _jwks_clients.clear()
