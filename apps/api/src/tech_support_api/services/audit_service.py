from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_orchestration.models import OrchestrationResult, StructuredIntent, TicketCommand

from tech_support_api.db.models import PolicyAuditLog, ZammadOperation


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_policy(self, intent: StructuredIntent, result: OrchestrationResult) -> None:
        row = PolicyAuditLog(
            session_id=intent.session_id,
            intent=str(intent.intent),
            payload=intent.payload,
            outcome=result.outcome.value,
            reason_code=result.reason_code,
            rule_id=result.rule_id,
        )
        self._db.add(row)
        await self._db.commit()

    async def record_zammad(
        self,
        *,
        session_id: uuid.UUID,
        command: TicketCommand,
        response: dict[str, Any] | None,
        status: str,
        duration_ms: int,
    ) -> None:
        row = ZammadOperation(
            session_id=session_id,
            command_type=str(command.type),
            command=command.model_dump(mode="json"),
            response=response,
            status=status,
            duration_ms=duration_ms,
        )
        self._db.add(row)
        await self._db.commit()


class ZammadOperationTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
