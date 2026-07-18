from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from tech_support_shared.reason_codes import DEFAULT_USER_MESSAGES, ReasonCode
from tech_support_shared.schemas import schema_path

from tech_support_orchestration.mapping import normalize_customer_email
from tech_support_orchestration.models import (
    IntentName,
    StructuredIntent,
    UserContext,
    ValidationResult,
)


class PolicyValidator:
    MIN_CONFIDENCE = 0.6
    MAX_ATTACHMENTS = 5

    def __init__(self, schema_path_override: Path | None = None) -> None:
        path = schema_path_override or schema_path("intent.json")
        with path.open(encoding="utf-8") as handle:
            self._schema = json.load(handle)

    def validate(self, intent: StructuredIntent, user: UserContext) -> ValidationResult:
        document = intent.model_dump(mode="json")
        try:
            jsonschema.validate(instance=document, schema=self._schema)
        except jsonschema.ValidationError:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.INVALID_INTENT_SCHEMA,
                message=DEFAULT_USER_MESSAGES[ReasonCode.INVALID_INTENT_SCHEMA],
                rule_id="schema_v1",
            )

        if intent.confidence < self.MIN_CONFIDENCE:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.LOW_CONFIDENCE,
                message=DEFAULT_USER_MESSAGES[ReasonCode.LOW_CONFIDENCE],
                rule_id="confidence_threshold",
            )

        if intent.intent == IntentName.CREATE_TICKET:
            return self._validate_create_ticket(intent, user)

        if intent.intent == IntentName.ADD_ATTACHMENT:
            return self._validate_add_attachment(intent, user)

        return ValidationResult(passed=True, rule_id="default_allow")

    def _validate_create_ticket(
        self, intent: StructuredIntent, user: UserContext
    ) -> ValidationResult:
        payload = intent.payload
        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        email = normalize_customer_email(
            (user.email or payload.get("customer_email") or "").strip()
        )

        if not title:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.MISSING_TITLE,
                message=DEFAULT_USER_MESSAGES[ReasonCode.MISSING_TITLE],
                rule_id="create_required_title",
            )
        if not description:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.MISSING_DESCRIPTION,
                message=DEFAULT_USER_MESSAGES[ReasonCode.MISSING_DESCRIPTION],
                rule_id="create_required_description",
            )
        if not email or "@" not in email:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.MISSING_CUSTOMER_EMAIL,
                message=DEFAULT_USER_MESSAGES[ReasonCode.MISSING_CUSTOMER_EMAIL],
                rule_id="create_required_customer_email",
            )
        attachment_result = self._validate_attachment_list(payload.get("attachments") or [])
        if not attachment_result.passed:
            return attachment_result
        return ValidationResult(passed=True, rule_id="create_ticket_ok")

    def _validate_add_attachment(
        self, intent: StructuredIntent, user: UserContext
    ) -> ValidationResult:
        del user
        payload = intent.payload
        ticket_number = str(payload.get("ticket_number") or "").strip()
        if not ticket_number:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.TICKET_NOT_FOUND,
                message="Please specify which ticket to attach the file to.",
                rule_id="add_attachment_ticket_number",
            )
        return self._validate_attachment_list(payload.get("attachments") or [])

    def _validate_attachment_list(self, attachments: list) -> ValidationResult:
        if len(attachments) > self.MAX_ATTACHMENTS:
            return ValidationResult(
                passed=False,
                reason_code=ReasonCode.ATTACHMENT_COUNT_EXCEEDED,
                message=DEFAULT_USER_MESSAGES[ReasonCode.ATTACHMENT_COUNT_EXCEEDED],
                rule_id="attachment_count",
            )
        return ValidationResult(passed=True, rule_id="attachments_ok")
