from tech_support_api.services.mock_graph import MockSupportGraph


def test_greeting_intent():
    result = MockSupportGraph().invoke("Hello")
    assert "Hi" in result.assistant_content
    assert result.detected_intent == "ChitChat"


def test_create_ticket_intake():
    result = MockSupportGraph().invoke("My VPN is not working", message_count=0)
    assert result.detected_intent == "CreateTicket"
    assert len(result.system_statuses) >= 2


def test_create_ticket_summary_card_after_follow_up():
    result = MockSupportGraph().invoke(
        "VPN authentication failed since this morning",
        message_count=3,
    )
    assert result.detected_intent == "CreateTicket"
    assert result.card is not None
    assert result.card["card_type"] == "ticket_summary"
