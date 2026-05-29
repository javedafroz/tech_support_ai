from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tech_support_orchestration import (
    OrchestrationEngine,
    OrchestrationResult,
    StructuredIntent,
    UserContext,
)
from tech_support_orchestration.models import PolicyOutcome, ZammadCommandType
from tech_support_zammad import CreateTicketRequest, ZammadClient, ZammadError
from tech_support_zammad.models import Ticket


class TicketPipelineResult:
    def __init__(
        self,
        *,
        orchestration: OrchestrationResult,
        ticket: Ticket | None = None,
        error: str | None = None,
    ) -> None:
        self.orchestration = orchestration
        self.ticket = ticket
        self.error = error

    @property
    def success(self) -> bool:
        return (
            self.orchestration.outcome == PolicyOutcome.APPROVED
            and self.ticket is not None
            and self.error is None
        )


class TicketPipeline:
    def __init__(
        self,
        *,
        orchestration: OrchestrationEngine | None = None,
        zammad: ZammadClient | None = None,
        mapping_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[5]
        mapping = mapping_path or root / "config" / "zammad-field-mapping.yaml"
        self._orchestration = orchestration or OrchestrationEngine.from_mapping_path(mapping)
        self._zammad = zammad

    def _get_zammad(self) -> ZammadClient:
        if self._zammad is None:
            self._zammad = self._build_zammad_client()
        return self._zammad

    @staticmethod
    def _build_zammad_client() -> ZammadClient:
        base_url = os.environ.get("ZAMMAD_BASE_URL", "")
        token = os.environ.get("ZAMMAD_API_TOKEN", "")
        if not base_url or not token:
            raise ValueError("ZAMMAD_BASE_URL and ZAMMAD_API_TOKEN must be set")
        auth_scheme = os.environ.get("ZAMMAD_AUTH_SCHEME", "Bearer")
        return ZammadClient(base_url, token, auth_scheme=auth_scheme)

    async def create_ticket_from_intent(
        self,
        intent: StructuredIntent,
        user: UserContext,
    ) -> TicketPipelineResult:
        result = self._orchestration.process(intent, user)
        if result.outcome != PolicyOutcome.APPROVED or not result.approved_command:
            return TicketPipelineResult(orchestration=result)

        command = result.approved_command
        if command.type != ZammadCommandType.CREATE_TICKET:
            return TicketPipelineResult(
                orchestration=result,
                error=f"Unsupported command type: {command.type}",
            )

        try:
            request = CreateTicketRequest.model_validate(command.payload)
            ticket = await self._get_zammad().create_ticket(
                request,
                idempotency_key=command.idempotency_key,
            )
            return TicketPipelineResult(orchestration=result, ticket=ticket)
        except ZammadError as exc:
            return TicketPipelineResult(orchestration=result, error=f"{exc.code}: {exc.message}")

    async def execute_command(self, command: Any) -> Ticket | dict[str, Any]:
        if command.type == ZammadCommandType.CREATE_TICKET:
            request = CreateTicketRequest.model_validate(command.payload)
            return await self._get_zammad().create_ticket(
                request,
                idempotency_key=command.idempotency_key,
            )
        if command.type == ZammadCommandType.SEARCH_TICKETS:
            return (
                await self._get_zammad().search_tickets(
                    command.payload["query"],
                    limit=int(command.payload.get("limit", 10)),
                )
            ).model_dump()
        if command.type == ZammadCommandType.GET_TICKET:
            ticket_id = int(command.payload["ticket_id"])
            return await self._get_zammad().get_ticket(ticket_id)
        raise ValueError(f"Unsupported command: {command.type}")
