from __future__ import annotations

from tech_support_orchestration.mapping import normalize_customer_id
from tech_support_orchestration.models import TicketCommandType
from tech_support_ticketing import TicketCommand, build_ticket_gateway, get_ticketing_settings

from tech_support_agents.state import SupportGraphState


async def ticket_tool_node(state: SupportGraphState) -> dict:
    command = state.get("approved_command")
    if command is None:
        return {"error": "No approved command for ticket provider execution"}

    statuses = list(state.get("system_statuses", []))
    if command.type == TicketCommandType.CREATE_TICKET:
        statuses.append("Creating ticket…")
    elif command.type == TicketCommandType.SEARCH_TICKETS:
        statuses.append("Checking ticket status…")
    else:
        return {"error": f"Unsupported ticket command in Sprint 5: {command.type}"}

    config_error = get_ticketing_settings().configuration_error()
    if config_error:
        return {
            "error": "Ticket provider is not configured",
            "system_statuses": statuses,
            "assistant_reply": (
                "Ticket actions are not available because the ticket provider is not configured. "
                "Set the required provider credentials."
            ),
            "needs_clarification": True,
        }

    try:
        payload = dict(command.payload)
        if raw_customer_id := payload.get("customer_id"):
            payload["customer_id"] = normalize_customer_id(str(raw_customer_id))
        gateway = build_ticket_gateway()
        result = await gateway.execute(
            TicketCommand(
                type=str(command.type),
                payload=payload,
                idempotency_key=str(command.idempotency_key),
            )
        )
        if not result.success:
            return {
                "error": result.error_message or "Ticket provider request failed",
                "system_statuses": statuses,
                "assistant_reply": (
                    "Could not complete the ticket action: "
                    f"{result.error_message or 'provider request failed'}"
                ),
                "needs_clarification": True,
            }
        response = result.raw_response

        if command.type == TicketCommandType.CREATE_TICKET:
            if result.ticket is None:
                return {
                    "error": "Ticket provider response missing created ticket",
                    "system_statuses": statuses,
                    "assistant_reply": (
                        "Could not create the ticket due to an invalid provider response."
                    ),
                    "needs_clarification": True,
                }
            ticket_number = result.ticket.display_number
            ticket_id = result.ticket.external_id
            return {
                "provider_response": response,
                "active_ticket_number": ticket_number,
                "system_statuses": statuses,
                "ui_card": {
                    "card_type": "ticket_created",
                    "ticket_number": ticket_number,
                    "ticket_id": ticket_id,
                    "group": command.payload.get("group", ""),
                    "priority": command.payload.get("priority", ""),
                    "state": "open",
                },
            }

        tickets = result.items
        tickets_dump = [t.model_dump() for t in tickets]
        if len(tickets) == 1:
            match = tickets[0]
            return {
                "provider_response": {"count": len(tickets), "items": tickets_dump},
                "active_ticket_number": match.display_number,
                "system_statuses": statuses,
                "ui_card": {
                    "card_type": "ticket_status",
                    "ticket_number": match.display_number,
                    "group": match.group_or_queue or "",
                    "state": match.state or "open",
                },
                "assistant_reply": (
                    f"Your ticket **#{match.display_number}** was found. "
                    f"Current status: **{match.state or 'open'}**."
                ),
            }

        if len(tickets) > 1:
            options = ", ".join(f"#{t.display_number}" for t in tickets[:5])
            return {
                "provider_response": {"count": len(tickets), "items": tickets_dump},
                "system_statuses": statuses,
                "assistant_reply": (
                    "I found multiple matching tickets. "
                    f"Please confirm which one you want: {options}."
                ),
                "needs_clarification": True,
            }

        return {
            "provider_response": {"count": 0, "items": []},
            "system_statuses": statuses,
            "assistant_reply": (
                "I could not find a matching ticket. Please share the ticket number."
            ),
            "needs_clarification": True,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "system_statuses": statuses,
            "assistant_reply": f"Could not create the ticket: {exc}",
            "needs_clarification": True,
        }
