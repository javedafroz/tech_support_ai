from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_api.db.session import get_db
from tech_support_api.services.attachment_service import AttachmentService
from tech_support_api.services.chat_service import ChatService
from tech_support_api.services.redis_store import RedisSessionStore, get_redis_store


async def get_chat_service(
    db: AsyncSession = Depends(get_db),
    redis_store: RedisSessionStore = Depends(get_redis_store),
) -> AsyncGenerator[ChatService, None]:
    yield ChatService(db, redis_store, AttachmentService(db))


async def get_attachment_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AttachmentService, None]:
    yield AttachmentService(db)
