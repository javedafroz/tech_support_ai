from __future__ import annotations

from tech_support_ticketing.models import (
    ProviderCapabilities,
    TicketCommand,
    TicketOperationResult,
)


class ServiceNowAdapter:
    """Stub adapter validating provider plug-in architecture."""

    provider_name = "servicenow"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_attachments=False,
            supports_escalation=False,
            supports_close=False,
            supports_status_search=False,
        )

    async def execute(self, command: TicketCommand) -> TicketOperationResult:
        return TicketOperationResult(
            success=False,
            provider=self.provider_name,
            operation=command.type,
            error_code="NOT_IMPLEMENTED",
            error_message=(
                "ServiceNow provider adapter is registered but not implemented yet. "
                "Use TICKETING_PROVIDER=zammad for live ticket operations."
            ),
        )
