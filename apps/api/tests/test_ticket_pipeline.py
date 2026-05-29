from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx
from tech_support_api.services.ticket_pipeline import TicketPipeline
from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext
from tech_support_zammad import ZammadClient


@pytest.fixture
def mapping_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "zammad-field-mapping.yaml"


@pytest.mark.asyncio
@respx.mock
async def test_pipeline_create_ticket_e2e(mapping_path: Path):
    base = "https://zammad.test"
    respx.post(f"{base}/api/v1/tickets").mock(
        return_value=httpx.Response(
            201,
            json={"id": 19, "number": "22019", "title": "VPN issue"},
        )
    )
    pipeline = TicketPipeline(
        mapping_path=mapping_path,
        zammad=ZammadClient(base, "token"),
    )
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.9,
        session_id=uuid4(),
        user_id="user@test.com",
        payload={
            "title": "VPN issue",
            "description": "Cannot connect",
            "customer_email": "user@test.com",
            "suggested_category": "network",
            "suggested_priority": "high",
        },
        timestamp=datetime.now(UTC),
    )
    result = await pipeline.create_ticket_from_intent(
        intent, UserContext(user_id="user@test.com", email="user@test.com")
    )
    assert result.success
    assert result.ticket is not None
    assert result.ticket.number == "22019"


@pytest.mark.asyncio
async def test_pipeline_rejects_missing_description(mapping_path: Path):
    pipeline = TicketPipeline(
        mapping_path=mapping_path,
        zammad=ZammadClient("https://zammad.test", "token"),
    )
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.9,
        session_id=uuid4(),
        user_id="user@test.com",
        payload={"title": "VPN", "customer_email": "user@test.com"},
        timestamp=datetime.now(UTC),
    )
    result = await pipeline.create_ticket_from_intent(
        intent, UserContext(user_id="user@test.com", email="user@test.com")
    )
    assert not result.success
    assert result.orchestration.reason_code == "MISSING_DESCRIPTION"
