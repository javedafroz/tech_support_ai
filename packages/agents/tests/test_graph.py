import httpx
import pytest
import respx
from tech_support_agents.graph import compile_support_graph
from tech_support_agents.runner import SupportGraphRunner
from tech_support_orchestration.models import IntentName


def test_support_graph_compiles():
    graph = compile_support_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_mock_turn_clarifies_short_message():
    runner = SupportGraphRunner.compile()
    result = await runner.invoke_turn(
        session_id=__import__("uuid").uuid4(),
        user_id="user@test.com",
        user_input="Hello",
        user_email="user@test.com",
    )
    assert "Hi" in result.assistant_content
    assert result.detected_intent is None


@pytest.mark.asyncio
async def test_mock_turn_create_ticket_with_zammad_mock(monkeypatch):
    runner = SupportGraphRunner.compile()
    session_id = __import__("uuid").uuid4()
    user_email = "graph-test@company.com"

    monkeypatch.setenv("ZAMMAD_BASE_URL", "https://zammad.test")
    monkeypatch.setenv("ZAMMAD_API_TOKEN", "test-token")

    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 42, "number": "22042", "title": "VPN problem"},
            )
        )

        result = await runner.invoke_turn(
            session_id=session_id,
            user_id=user_email,
            user_input=(
                "My VPN authentication has been failing since this morning "
                "with error code 403 on corporate network."
            ),
            user_email=user_email,
            message_count=1,
        )

    assert result.detected_intent == IntentName.CREATE_TICKET.value
    assert result.active_ticket_number == "22042"
    assert "22042" in result.assistant_content
    assert result.card is not None
    assert result.card["card_type"] == "ticket_created"


@pytest.mark.asyncio
async def test_checkpoint_resume_memory_saver():
    from langgraph.checkpoint.memory import MemorySaver

    session_id = __import__("uuid").uuid4()
    runner = SupportGraphRunner.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": str(session_id)}}

    state1 = await runner._graph.ainvoke(
        {
            "session_id": str(session_id),
            "user_id": "u@test.com",
            "user_email": "u@test.com",
            "user_input": "Hello",
            "system_statuses": [],
        },
        config=config,
    )
    assert state1.get("needs_clarification") is True

    state2 = await runner._graph.ainvoke(
        {
            "session_id": str(session_id),
            "user_id": "u@test.com",
            "user_email": "u@test.com",
            "user_input": "follow up",
            "system_statuses": [],
        },
        config=config,
    )
    assert state2 is not None
