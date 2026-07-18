from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError, PyJWTError
from jwt import decode as jwt_decode
from tech_support_api.config import get_settings


def _user_from_bearer(token: str) -> str:
    settings = get_settings()
    if not settings.auth_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT authentication is not configured",
        )
    try:
        payload = jwt_decode(
            token,
            settings.auth_jwt_secret,
            algorithms=settings.auth_jwt_algorithms,
            audience=settings.auth_jwt_audience,
            options={"verify_aud": bool(settings.auth_jwt_audience)},
        )
    except (PyJWTError, InvalidTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub)",
        )
    return str(user_id).strip()


async def require_user_id(request: Request) -> str:
    settings = get_settings()
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        return _user_from_bearer(authorization.removeprefix("Bearer ").strip())

    if settings.auth_mode == "jwt":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )

    header_name = settings.auth_dev_header_user_id
    user_id = request.headers.get(header_name)
    if not user_id or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing identity header ({header_name})",
        )
    return user_id.strip()
