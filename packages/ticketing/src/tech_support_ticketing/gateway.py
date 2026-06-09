from __future__ import annotations

from typing import Protocol

from tech_support_ticketing.models import (
    ProviderCapabilities,
    TicketCommand,
    TicketOperationResult,
)


class TicketGateway(Protocol):
    async def execute(self, command: TicketCommand) -> TicketOperationResult:
        ...

    def capabilities(self) -> ProviderCapabilities:
        ...
