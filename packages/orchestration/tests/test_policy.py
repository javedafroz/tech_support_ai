from datetime import UTC, datetime
from uuid import uuid4

from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext
from tech_support_orchestration.policy import PolicyValidator
from tech_support_shared.reason_codes import ReasonCode


def _intent(**payload):
    return StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.9,
        session_id=uuid4(),
        user_id="user-1",
        payload=payload,
        timestamp=datetime.now(UTC),
    )


def test_create_ticket_passes_with_required_fields():
    validator = PolicyValidator()
    result = validator.validate(
        _intent(
            title="VPN issue",
            description="Cannot connect",
            customer_email="john@company.com",
        ),
        UserContext(user_id="user-1", email="john@company.com"),
    )
    assert result.passed


def test_missing_description_rejected():
    validator = PolicyValidator()
    result = validator.validate(
        _intent(title="VPN issue", customer_email="john@company.com"),
        UserContext(user_id="user-1"),
    )
    assert not result.passed
    assert result.reason_code == ReasonCode.MISSING_DESCRIPTION


def test_low_confidence_rejected():
    validator = PolicyValidator()
    intent = _intent(
        title="VPN",
        description="down",
        customer_email="john@company.com",
    )
    intent.confidence = 0.2
    result = validator.validate(intent, UserContext(user_id="user-1"))
    assert result.reason_code == ReasonCode.LOW_CONFIDENCE
