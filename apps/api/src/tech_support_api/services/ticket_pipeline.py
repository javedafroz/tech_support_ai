from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tech_support_orchestration import (
    OrchestrationEngine,
    OrchestrationResult,
    StructuredIntent,
    UserContext,
)
from tech_support_orchestration.mapping import resolve_mapping_path
from tech_support_orchestration.models import PolicyOutcome, TicketCommandType
from tech_support_ticketing import TicketCommand, build_ticket_gateway, get_ticketing_settings
from tech_support_ticketing.gateway import TicketGateway
from tech_support_ticketing.models import ProviderTicket


@dataclass
class PipelineTicket:
    """Backward-compatible ticket view for CLI and audit callers."""

    id: str
    number: str
    title: str
    raw: dict[str, Any]

    @classmethod
    def from_provider(cls, ticket: ProviderTicket) -> PipelineTicket:
        return cls(
            id=ticket.external_id,
            number=ticket.display_number,
            title=str(ticket.raw.get("title", "")),
            raw=ticket.raw,
        )

    def model_dump(self) -> dict[str, Any]:
        return dict(self.raw)


class TicketPipelineResult:
    def __init__(
        self,
        *,
        orchestration: OrchestrationResult,
        ticket: PipelineTicket | None = None,
        provider_response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.orchestration = orchestration
        self.ticket = ticket
        self.provider_response = provider_response
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
        gateway: TicketGateway | None = None,
        mapping_path: Path | None = None,
        # Backward-compatible alias for tests that still pass a Zammad adapter.
        zammad: TicketGateway | None = None,
    ) -> None:
        mapping = mapping_path or resolve_mapping_path(get_ticketing_settings().provider)
        self._orchestration = orchestration or OrchestrationEngine.from_mapping_path(mapping)
        self._gateway = gateway or zammad

    def _get_gateway(self) -> TicketGateway:
        if self._gateway is None:
            self._gateway = build_ticket_gateway()
        return self._gateway

    async def create_ticket_from_intent(
        self,
        intent: StructuredIntent,
        user: UserContext,
    ) -> TicketPipelineResult:
        result = self._orchestration.process(intent, user)
        if result.outcome != PolicyOutcome.APPROVED or not result.approved_command:
            return TicketPipelineResult(orchestration=result)

        command = result.approved_command
        if command.type != TicketCommandType.CREATE_TICKET:
            return TicketPipelineResult(
                orchestration=result,
                error=f"Unsupported command type: {command.type}",
            )

        config_error = get_ticketing_settings().configuration_error()
        if config_error:
            return TicketPipelineResult(orchestration=result, error=config_error)

        try:
            operation = await self._get_gateway().execute(
                TicketCommand(
                    type=str(command.type),
                    payload=command.payload,
                    idempotency_key=str(command.idempotency_key),
                )
            )
            if not operation.success or operation.ticket is None:
                return TicketPipelineResult(
                    orchestration=result,
                    error=operation.error_message or "Ticket provider request failed",
                    provider_response=operation.raw_response,
                )
            return TicketPipelineResult(
                orchestration=result,
                ticket=PipelineTicket.from_provider(operation.ticket),
                provider_response=operation.raw_response,
            )
        except Exception as exc:
            return TicketPipelineResult(orchestration=result, error=str(exc))

    async def execute_command(self, command: Any) -> PipelineTicket | dict[str, Any]:
        operation = await self._get_gateway().execute(
            TicketCommand(
                type=str(command.type),
                payload=command.payload,
                idempotency_key=str(command.idempotency_key),
            )
        )
        if not operation.success:
            raise ValueError(operation.error_message or "Ticket provider request failed")

        if command.type == TicketCommandType.CREATE_TICKET:
            if operation.ticket is None:
                raise ValueError("Ticket provider response missing created ticket")
            return PipelineTicket.from_provider(operation.ticket)
        if command.type == TicketCommandType.SEARCH_TICKETS:
            return {
                "count": len(operation.items),
                "items": [item.model_dump() for item in operation.items],
            }
        if command.type == TicketCommandType.GET_TICKET:
            if operation.ticket is None:
                raise ValueError("Ticket provider response missing ticket")
            return PipelineTicket.from_provider(operation.ticket)
        raise ValueError(f"Unsupported command: {command.type}")
