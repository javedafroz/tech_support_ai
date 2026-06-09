from __future__ import annotations

from pathlib import Path

from tech_support_orchestration.mapping import (
    FieldMappingConfig,
    load_field_mapping,
    normalize_customer_email,
)
from tech_support_orchestration.models import (
    IntentName,
    StructuredIntent,
    TicketCommand,
    TicketCommandType,
    UserContext,
)


class WorkflowEngine:
    def __init__(self, mapping: FieldMappingConfig | None = None) -> None:
        self._mapping = mapping or load_field_mapping()

    @classmethod
    def from_config_path(cls, path: Path) -> WorkflowEngine:
        return cls(load_field_mapping(path))

    def build_command(self, intent: StructuredIntent, user: UserContext) -> TicketCommand:
        if intent.intent == IntentName.CREATE_TICKET:
            return self._create_ticket_command(intent, user)
        if intent.intent == IntentName.CHECK_STATUS:
            return self._check_status_command(intent, user)
        raise ValueError(f"Workflow not implemented for intent: {intent.intent}")

    def _create_ticket_command(self, intent: StructuredIntent, user: UserContext) -> TicketCommand:
        payload = intent.payload
        email = normalize_customer_email(
            (user.email or payload.get("customer_email") or "").strip()
        )
        category_key = (payload.get("suggested_category") or "").strip().lower().replace(" ", "_")
        group = self._mapping.resolve_group(category_key or None)
        priority = self._mapping.resolve_priority(
            payload.get("suggested_priority"),
            payload.get("impact"),
        )
        title = payload["title"].strip()
        description = payload["description"].strip()
        customer_id = self._mapping.customer_id_for_email(email)

        return TicketCommand(
            type=TicketCommandType.CREATE_TICKET,
            session_id=intent.session_id,
            user_id=intent.user_id,
            payload={
                "title": title,
                "group": group,
                "customer_id": customer_id,
                "priority": priority,
                "article": {
                    "subject": title,
                    "body": description,
                    "type": "note",
                    "internal": False,
                    "content_type": "text/plain",
                },
            },
        )

    def _check_status_command(self, intent: StructuredIntent, user: UserContext) -> TicketCommand:
        email = (user.email or intent.payload.get("customer_email") or "").strip()
        query_parts = [f"customer.email:{email}"] if email else []
        if ticket_number := intent.payload.get("ticket_number"):
            query_parts.append(f"number:{ticket_number}")
        if hint := intent.payload.get("search_hint"):
            query_parts.append(hint)
        query = " AND ".join(query_parts) if query_parts else "state.open"

        return TicketCommand(
            type=TicketCommandType.SEARCH_TICKETS,
            session_id=intent.session_id,
            user_id=intent.user_id,
            payload={"query": query, "limit": 5},
        )
