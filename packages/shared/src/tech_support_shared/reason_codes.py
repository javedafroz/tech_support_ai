"""Stable orchestration reason codes (v1). User-facing copy lives in reason_code_messages."""

from enum import StrEnum


class ReasonCode(StrEnum):
    MISSING_TITLE = "MISSING_TITLE"
    MISSING_DESCRIPTION = "MISSING_DESCRIPTION"
    MISSING_CUSTOMER_EMAIL = "MISSING_CUSTOMER_EMAIL"
    INVALID_INTENT_SCHEMA = "INVALID_INTENT_SCHEMA"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TICKET_ACCESS_DENIED = "TICKET_ACCESS_DENIED"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    TICKET_STATE_INVALID = "TICKET_STATE_INVALID"
    ATTACHMENT_TYPE_BLOCKED = "ATTACHMENT_TYPE_BLOCKED"
    ATTACHMENT_SIZE_EXCEEDED = "ATTACHMENT_SIZE_EXCEEDED"
    ATTACHMENT_COUNT_EXCEEDED = "ATTACHMENT_COUNT_EXCEEDED"
    ESCALATION_NOT_ALLOWED = "ESCALATION_NOT_ALLOWED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    DUPLICATE_TICKET_SUSPECTED = "DUPLICATE_TICKET_SUSPECTED"
    ZAMMAD_UNAVAILABLE = "ZAMMAD_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


DEFAULT_USER_MESSAGES: dict[ReasonCode, str] = {
    ReasonCode.MISSING_TITLE: "Please provide a short summary of your issue.",
    ReasonCode.MISSING_DESCRIPTION: "Please describe what happened so we can create a ticket.",
    ReasonCode.MISSING_CUSTOMER_EMAIL: "We need your email to link this ticket to your account.",
    ReasonCode.INVALID_INTENT_SCHEMA: "We couldn't process that request. Please try rephrasing.",
    ReasonCode.LOW_CONFIDENCE: "I'm not sure I understood. Could you clarify what you need?",
    ReasonCode.TICKET_ACCESS_DENIED: "You don't have access to that ticket.",
    ReasonCode.TICKET_NOT_FOUND: "I couldn't find a matching ticket on your account.",
    ReasonCode.TICKET_STATE_INVALID: "That ticket can't be updated in its current state.",
    ReasonCode.ATTACHMENT_TYPE_BLOCKED: "That file type isn't allowed.",
    ReasonCode.ATTACHMENT_SIZE_EXCEEDED: "That file is too large.",
    ReasonCode.ATTACHMENT_COUNT_EXCEEDED: "Too many attachments for this ticket.",
    ReasonCode.ESCALATION_NOT_ALLOWED: "This ticket can't be escalated further in chat.",
    ReasonCode.RATE_LIMIT_EXCEEDED: "Please wait a moment before sending another message.",
    ReasonCode.DUPLICATE_TICKET_SUSPECTED: "You may already have an open ticket for this issue.",
    ReasonCode.ZAMMAD_UNAVAILABLE: (
        "Support ticketing is temporarily unavailable. Your request may be queued."
    ),
    ReasonCode.INTERNAL_ERROR: (
        "Something went wrong. Please try again or use your usual support channel."
    ),
}
