from __future__ import annotations

from uuid import UUID

from tech_support_ticketing.models import (
    ProviderCapabilities,
    ProviderTicket,
    TicketCommand,
    TicketCommandType,
    TicketOperationResult,
)
from tech_support_zammad import CreateTicketRequest, ZammadClient, ZammadError
from tech_support_zammad.errors import ZammadErrorCode


class ZammadAdapter:
    provider_name = "zammad"

    def __init__(self, client: ZammadClient) -> None:
        self._client = client

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_attachments=False,
            supports_escalation=False,
            supports_close=False,
            supports_status_search=True,
        )

    async def execute(self, command: TicketCommand) -> TicketOperationResult:
        command_type = command.type
        if command_type == TicketCommandType.CREATE_TICKET:
            return await self._create_ticket(command)
        if command_type == TicketCommandType.SEARCH_TICKETS:
            return await self._search_tickets(command)
        return TicketOperationResult(
            success=False,
            provider=self.provider_name,
            operation=command_type,
            error_code="UNSUPPORTED_COMMAND",
            error_message=f"Unsupported command for Zammad adapter: {command_type}",
        )

    async def _create_ticket(self, command: TicketCommand) -> TicketOperationResult:
        request = CreateTicketRequest.model_validate(command.payload)
        key = UUID(command.idempotency_key) if command.idempotency_key else None
        try:
            ticket = await self._client.create_ticket(request, idempotency_key=key)
            raw = ticket.model_dump()
            normalized = ProviderTicket(
                provider=self.provider_name,
                external_id=str(ticket.id),
                display_number=ticket.number,
                raw=raw,
            )
            return TicketOperationResult(
                success=True,
                provider=self.provider_name,
                operation=command.type,
                ticket=normalized,
                raw_response=raw,
            )
        except ZammadError as exc:
            return TicketOperationResult(
                success=False,
                provider=self.provider_name,
                operation=command.type,
                error_code=exc.code.value,
                error_message=exc.message,
                retryable=exc.code in {ZammadErrorCode.UNAVAILABLE, ZammadErrorCode.TIMEOUT},
            )

    async def _search_tickets(self, command: TicketCommand) -> TicketOperationResult:
        query = str(command.payload.get("query", "")).strip()
        limit = int(command.payload.get("limit", 10))
        try:
            result = await self._client.search_tickets(query=query, limit=limit)
            items = [
                ProviderTicket(
                    provider=self.provider_name,
                    external_id=str(ticket.id),
                    display_number=ticket.number,
                    raw=ticket.model_dump(),
                )
                for ticket in result.tickets
            ]
            return TicketOperationResult(
                success=True,
                provider=self.provider_name,
                operation=command.type,
                items=items,
                raw_response={"count": result.count},
            )
        except ZammadError as exc:
            return TicketOperationResult(
                success=False,
                provider=self.provider_name,
                operation=command.type,
                error_code=exc.code.value,
                error_message=exc.message,
                retryable=exc.code in {ZammadErrorCode.UNAVAILABLE, ZammadErrorCode.TIMEOUT},
            )
