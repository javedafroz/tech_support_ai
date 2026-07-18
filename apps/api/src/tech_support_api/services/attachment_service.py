from __future__ import annotations

import mimetypes
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_storage import get_object_storage

from tech_support_api.config import get_settings
from tech_support_api.db.models import SessionAttachment

BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi", ".dll", ".scr"}
ALLOWED_MIME_PREFIXES = ("image/", "text/", "application/pdf", "application/json")
ALLOWED_MIME_EXACT = {
    "application/pdf",
    "application/json",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "application/x-zip-compressed",
}


class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()
        self._storage = get_object_storage()

    async def upload(
        self,
        *,
        session_id: UUID,
        user_id: str,
        file: UploadFile,
    ) -> SessionAttachment:
        filename = (file.filename or "attachment").strip()
        if not filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in BLOCKED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That file type isn't allowed.",
            )

        data = await file.read()
        size = len(data)
        if size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
        if size > self._settings.attachment_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That file is too large.",
            )

        mime_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        if not self._mime_allowed(mime_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That file type isn't allowed.",
            )

        attachment_id = uuid.uuid4()
        storage_key = f"sessions/{session_id}/{attachment_id}/{filename}"
        self._storage.put_object(key=storage_key, data=data, content_type=mime_type)

        row = SessionAttachment(
            id=attachment_id,
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size,
            storage_key=storage_key,
            status="pending",
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def link_to_message(
        self,
        *,
        session_id: UUID,
        user_id: str,
        message_id: UUID,
        attachment_ids: list[UUID],
    ) -> list[SessionAttachment]:
        if len(attachment_ids) > self._settings.attachment_max_per_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many attachments for this message.",
            )
        if not attachment_ids:
            return []

        result = await self._db.execute(
            select(SessionAttachment).where(
                SessionAttachment.session_id == session_id,
                SessionAttachment.user_id == user_id,
                SessionAttachment.id.in_(attachment_ids),
            )
        )
        rows = list(result.scalars().all())
        if len(rows) != len(set(attachment_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more attachments were not found.",
            )

        for row in rows:
            row.message_id = message_id
            row.status = "linked"
        await self._db.commit()
        return rows

    async def get_linked_rows(
        self,
        *,
        session_id: UUID,
        user_id: str,
        attachment_ids: list[UUID],
    ) -> list[SessionAttachment]:
        if not attachment_ids:
            return []
        result = await self._db.execute(
            select(SessionAttachment).where(
                SessionAttachment.session_id == session_id,
                SessionAttachment.user_id == user_id,
                SessionAttachment.id.in_(attachment_ids),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def to_graph_payload(rows: list[SessionAttachment]) -> list[dict]:
        return [
            {
                "attachment_id": str(row.id),
                "filename": row.filename,
                "mime_type": row.mime_type,
                "storage_key": row.storage_key,
                "size_bytes": row.size_bytes,
            }
            for row in rows
        ]

    @staticmethod
    def to_message_refs(rows: list[SessionAttachment]) -> list[dict]:
        return [
            {
                "id": str(row.id),
                "filename": row.filename,
                "mime_type": row.mime_type,
                "size_bytes": row.size_bytes,
            }
            for row in rows
        ]

    async def list_for_session(self, *, session_id: UUID, user_id: str) -> list[SessionAttachment]:
        result = await self._db.execute(
            select(SessionAttachment)
            .where(
                SessionAttachment.session_id == session_id,
                SessionAttachment.user_id == user_id,
            )
            .order_by(SessionAttachment.created_at.desc())
        )
        return list(result.scalars().all())

    def _mime_allowed(self, mime_type: str) -> bool:
        lowered = mime_type.lower()
        if lowered in ALLOWED_MIME_EXACT:
            return True
        return any(lowered.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES)
