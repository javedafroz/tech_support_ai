import pytest
from tech_support_agents.nodes.orchestrate import orchestrate_node
from tech_support_orchestration.models import IntentName, PolicyOutcome, StructuredIntent
from datetime import UTC, datetime
from uuid import uuid4


@pytest.mark.asyncio
async def test_orchestrate_rejects_low_confidence():
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.1,
        session_id=uuid4(),
        user_id="user@test.com",
        payload={
            "title": "Test",
            "description": "Test issue",
            "customer_email": "user@test.com",
        },
        timestamp=datetime.now(UTC),
    )
    result = await orchestrate_node(
        {
            "session_id": str(uuid4()),
            "user_id": "user@test.com",
            "structured_intent": intent,
            "system_statuses": [],
        }
    )
    assert result["orchestration_result"].outcome == PolicyOutcome.REJECTED
    assert result.get("assistant_reply")
