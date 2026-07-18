from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from tech_support_api.dependencies.auth import require_user_id
from tech_support_api.dependencies.services import get_attachment_service, get_chat_service
from tech_support_api.schemas.attachments import AttachmentListResponse, AttachmentUploadResponse
from tech_support_api.services.attachment_service import AttachmentService
from tech_support_api.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["attachments"])


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    session_id: UUID,
    file: UploadFile = File(...),
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
    attachments: AttachmentService = Depends(get_attachment_service),
) -> AttachmentUploadResponse:
    await chat.get_session(session_id, user_id)
    row = await attachments.upload(session_id=session_id, user_id=user_id, file=file)
    return AttachmentUploadResponse.model_validate(row)


@router.get(
    "/sessions/{session_id}/attachments",
    response_model=AttachmentListResponse,
)
async def list_attachments(
    session_id: UUID,
    user_id: str = Depends(require_user_id),
    chat: ChatService = Depends(get_chat_service),
    attachments: AttachmentService = Depends(get_attachment_service),
) -> AttachmentListResponse:
    await chat.get_session(session_id, user_id)
    rows = await attachments.list_for_session(session_id=session_id, user_id=user_id)
    return AttachmentListResponse(
        attachments=[AttachmentUploadResponse.model_validate(row) for row in rows]
    )
