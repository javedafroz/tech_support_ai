from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from tech_support_api import __version__
from tech_support_api.db.session import engine
from tech_support_api.schemas.chat import HealthResponse
from tech_support_api.services.redis_store import get_redis_store

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/health/ready", response_model=HealthResponse)
async def readiness() -> HealthResponse:
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {exc}",
        ) from exc

    try:
        store = await get_redis_store()
        if not await store.ping():
            raise RuntimeError("Redis ping failed")
        checks["redis"] = "ok"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis not ready: {exc}",
        ) from exc

    return HealthResponse(status="ok", version=__version__, checks=checks)
