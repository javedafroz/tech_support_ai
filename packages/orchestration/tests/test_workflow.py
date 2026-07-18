from datetime import UTC, datetime
from uuid import uuid4

from tech_support_orchestration.mapping import FieldMappingConfig, resolve_mapping_path
from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext
from tech_support_orchestration.workflow import WorkflowEngine


def test_create_ticket_maps_network_category():
    mapping = FieldMappingConfig(
        groups={"network": "Network Support"},
        categories={"network": "Network"},
        priorities={"high": "3 high", "normal": "2 normal"},
        default_group="Software Support",
        default_priority="2 normal",
    )
    engine = WorkflowEngine(mapping)
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.95,
        session_id=uuid4(),
        user_id="u1",
        payload={
            "title": "VPN down",
            "description": "Since morning",
            "customer_email": "john@company.com",
            "suggested_category": "network",
            "suggested_priority": "high",
        },
        timestamp=datetime.now(UTC),
    )
    cmd = engine.build_command(intent, UserContext(user_id="u1", email="john@company.com"))
    assert cmd.payload["group"] == "Network Support"
    assert cmd.payload["priority"] == "3 high"
    assert cmd.payload["customer_id"] == "guess:john@company.com"


def test_create_ticket_strips_llm_email_prefix():
    mapping = FieldMappingConfig(default_group="Software Support", default_priority="2 normal")
    engine = WorkflowEngine(mapping)
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.95,
        session_id=uuid4(),
        user_id="u1",
        payload={
            "title": "VPN down",
            "description": "Since morning",
            "customer_email": "email:paul.rivera@msbc.test",
            "suggested_category": "network",
        },
        timestamp=datetime.now(UTC),
    )
    cmd = engine.build_command(
        intent,
        UserContext(user_id="u1", email="paul.rivera@msbc.test"),
    )
    assert cmd.payload["customer_id"] == "guess:paul.rivera@msbc.test"


def test_normalize_customer_email():
    from tech_support_orchestration.mapping import normalize_customer_email, normalize_customer_id

    assert normalize_customer_email("email:user@test.com") == "user@test.com"
    assert normalize_customer_email("guess:email:user@test.com") == "user@test.com"
    assert normalize_customer_email("user@test.com") == "user@test.com"
    assert normalize_customer_id("guess:email:user@test.com") == "guess:user@test.com"


def test_load_mapping_from_repo_config():
    mapping_path = resolve_mapping_path("zammad")
    engine = WorkflowEngine.from_config_path(mapping_path)
    assert engine._mapping.default_group == "Software Support"


def test_resolve_mapping_path_for_servicenow_stub():
    mapping_path = resolve_mapping_path("servicenow")
    assert mapping_path.name == "mapping.yaml"
    assert "servicenow" in str(mapping_path)
