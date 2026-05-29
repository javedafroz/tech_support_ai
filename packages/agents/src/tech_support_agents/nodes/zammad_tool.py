from __future__ import annotations

import os

from tech_support_agents.state import SupportGraphState
from tech_support_orchestration.mapping import normalize_customer_id
from tech_support_orchestration.models import ZammadCommandType
from tech_support_zammad import CreateTicketRequest, ZammadClient, ZammadError


def _build_client() -> ZammadClient:
    base_url = os.environ["ZAMMAD_BASE_URL"]
    token = os.environ["ZAMMAD_API_TOKEN"]
    scheme = os.environ.get("ZAMMAD_AUTH_SCHEME", "Bearer")
    return ZammadClient(base_url, token, auth_scheme=scheme)


async def zammad_tool_node(state: SupportGraphState) -> dict:
    command = state.get("approved_command")
    if command is None:
        return {"error": "No approved command for Zammad execution"}

    if command.type != ZammadCommandType.CREATE_TICKET:
        return {"error": f"Unsupported Zammad command in Sprint 5: {command.type}"}

    statuses = list(state.get("system_statuses", []))
    statuses.append("Creating ticket…")

    if not os.environ.get("ZAMMAD_BASE_URL") or not os.environ.get("ZAMMAD_API_TOKEN"):
        return {
            "error": "Zammad is not configured",
            "system_statuses": statuses,
            "assistant_reply": (
                "Ticket creation is not available because Zammad is not configured. "
                "Set ZAMMAD_BASE_URL and ZAMMAD_API_TOKEN."
            ),
            "needs_clarification": True,
        }

    try:
        client = _build_client()
        payload = dict(command.payload)
        if raw_customer_id := payload.get("customer_id"):
            payload["customer_id"] = normalize_customer_id(str(raw_customer_id))
        request = CreateTicketRequest.model_validate(payload)
        ticket = await client.create_ticket(request, idempotency_key=command.idempotency_key)
        response = ticket.model_dump()
        return {
            "zammad_response": response,
            "active_ticket_number": ticket.number,
            "system_statuses": statuses,
            "ui_card": {
                "card_type": "ticket_created",
                "ticket_number": ticket.number,
                "ticket_id": ticket.id,
                "group": command.payload.get("group", ""),
                "priority": command.payload.get("priority", ""),
                "state": "open",
            },
        }
    except ZammadError as exc:
        return {
            "error": str(exc),
            "system_statuses": statuses,
            "assistant_reply": f"Could not create the ticket: {exc.message}",
            "needs_clarification": True,
        }
