from __future__ import annotations

from uuid import UUID

from tech_support_ticketing.attachments import encode_attachments_for_zammad
from tech_support_ticketing.models import (
    ProviderCapabilities,
    ProviderTicket,
    TicketCommand,
    TicketCommandType,
    TicketOperationResult,
)
from tech_support_zammad import CreateArticleRequest, CreateTicketRequest, ZammadClient, ZammadError
from tech_support_zammad.errors import ZammadErrorCode
from tech_support_zammad.models import TicketArticleInput, ZammadAttachmentInput


class ZammadAdapter:
    provider_name = "zammad"

    def __init__(self, client: ZammadClient) -> None:
        self._client = client

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_attachments=True,
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
        if command_type == TicketCommandType.ADD_ATTACHMENT:
            return await self._add_attachment(command)
        return TicketOperationResult(
            success=False,
            provider=self.provider_name,
            operation=command_type,
            error_code="UNSUPPORTED_COMMAND",
            error_message=f"Unsupported command for Zammad adapter: {command_type}",
        )

    async def _create_ticket(self, command: TicketCommand) -> TicketOperationResult:
        payload = dict(command.payload)
        attachment_specs = payload.pop("attachments", []) or []
        article_payload = dict(payload.pop("article", {}))
        if attachment_specs:
            article_payload["attachments"] = [
                ZammadAttachmentInput.model_validate(item)
                for item in encode_attachments_for_zammad(attachment_specs)
            ]

        request = CreateTicketRequest.model_validate(
            {**payload, "article": TicketArticleInput.model_validate(article_payload)}
        )
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

    async def _add_attachment(self, command: TicketCommand) -> TicketOperationResult:
        ticket_number = str(command.payload.get("ticket_number", "")).strip()
        attachment_specs = command.payload.get("attachments") or []
        article_payload = dict(command.payload.get("article") or {})
        try:
            search = await self._client.search_tickets(f"number:{ticket_number}", limit=1)
            if not search.tickets:
                return TicketOperationResult(
                    success=False,
                    provider=self.provider_name,
                    operation=command.type,
                    error_code=ZammadErrorCode.NOT_FOUND.value,
                    error_message=f"Ticket #{ticket_number} was not found.",
                )
            ticket = search.tickets[0]
            attachments = [
                ZammadAttachmentInput.model_validate(item)
                for item in encode_attachments_for_zammad(attachment_specs)
            ]
            request = CreateArticleRequest(
                ticket_id=ticket.id,
                body=article_payload.get("body", "Attachment added via Tech Support AI chat."),
                type=article_payload.get("type", "note"),
                internal=bool(article_payload.get("internal", False)),
                content_type=article_payload.get("content_type", "text/plain"),
                attachments=attachments,
            )
            key = UUID(command.idempotency_key) if command.idempotency_key else None
            article = await self._client.add_article(request, idempotency_key=key)
            return TicketOperationResult(
                success=True,
                provider=self.provider_name,
                operation=command.type,
                ticket=ProviderTicket(
                    provider=self.provider_name,
                    external_id=str(ticket.id),
                    display_number=ticket.number,
                    raw=ticket.model_dump(),
                ),
                raw_response=article.model_dump(),
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
