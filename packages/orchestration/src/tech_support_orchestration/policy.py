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
        return ValidationResult(passed=True, rule_id="create_ticket_ok")
