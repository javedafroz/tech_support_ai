from fastapi import APIRouter

from tech_support_api.config import get_settings
from tech_support_api.schemas.chat import PublicConfigResponse

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/public", response_model=PublicConfigResponse)
async def get_public_config() -> PublicConfigResponse:
    settings = get_settings()
    return PublicConfigResponse(thought_streaming_enabled=settings.thought_streaming_enabled)
