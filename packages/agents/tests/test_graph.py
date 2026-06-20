import httpx
import pytest
import respx
from langchain_core.messages import AIMessage, HumanMessage
from tech_support_agents.graph import compile_support_graph
from tech_support_agents.runner import SupportGraphRunner
from tech_support_orchestration.models import IntentName
from tech_support_ticketing.settings import TicketingSettings, configure_ticketing


def _configure_zammad_test():
    configure_ticketing(
        TicketingSettings(
            provider="zammad",
            zammad_base_url="https://zammad.test",
            zammad_api_token="test-token",
        )
    )


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

    _configure_zammad_test()

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
    assert result.provider_response is not None
    assert result.provider_response["number"] == "22042"


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


@pytest.mark.asyncio
async def test_multi_turn_blue_screen_create_ticket():
    runner = SupportGraphRunner.compile()
    session_id = __import__("uuid").uuid4()
    user_email = "bluescreen@company.com"

    _configure_zammad_test()

    history: list = []

    turn1 = await runner.invoke_turn(
        session_id=session_id,
        user_id=user_email,
        user_input="I am see blue screen on my laptop",
        user_email=user_email,
        message_count=1,
        history=history,
    )
    assert turn1.detected_intent is None
    history.extend(
        [
            HumanMessage(content="I am see blue screen on my laptop"),
            AIMessage(content=turn1.assistant_content),
        ]
    )

    turn2 = await runner.invoke_turn(
        session_id=session_id,
        user_id=user_email,
        user_input="It keeps happening",
        user_email=user_email,
        message_count=3,
        history=history,
    )
    assert turn2.detected_intent is None
    history.extend(
        [
            HumanMessage(content="It keeps happening"),
            AIMessage(content=turn2.assistant_content),
        ]
    )

    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 99, "number": "33001", "title": "Blue screen on laptop"},
            )
        )
        turn3 = await runner.invoke_turn(
            session_id=session_id,
            user_id=user_email,
            user_input=(
                'It starting helping in the morning today. I see error "Your PC ran into a problem"'
            ),
            user_email=user_email,
            message_count=5,
            history=history,
        )

    assert turn3.detected_intent == IntentName.CREATE_TICKET.value
    assert turn3.active_ticket_number == "33001"
    assert turn3.card is not None
    assert turn3.card["card_type"] == "ticket_created"


@pytest.mark.asyncio
async def test_astream_turn_emits_thoughts_before_complete():
    runner = SupportGraphRunner.compile()
    session_id = __import__("uuid").uuid4()

    thoughts = []
    result = None
    async for event_type, payload in runner.astream_turn(
        session_id=session_id,
        user_id="user@test.com",
        user_input="Hello",
        user_email="user@test.com",
        message_count=0,
    ):
        if event_type == "thought":
            thoughts.append(payload)
        elif event_type == "complete":
            result = payload

    assert thoughts
    assert result is not None
    assert result.detected_intent is None


@pytest.mark.asyncio
async def test_invoke_turn_seeds_history_into_conversation_node():
    runner = SupportGraphRunner.compile()
    session_id = __import__("uuid").uuid4()
    history = [
        HumanMessage(content="Blue screen on laptop"),
        AIMessage(content="When did it start?"),
    ]

    _configure_zammad_test()

    with respx.mock:
        respx.post("https://zammad.test/api/v1/tickets").mock(
            return_value=httpx.Response(
                201,
                json={"id": 55, "number": "44001", "title": "Blue screen"},
            )
        )
        result = await runner.invoke_turn(
            session_id=session_id,
            user_id="user@test.com",
            user_input="Started this morning with error code",
            user_email="user@test.com",
            message_count=2,
            history=history,
        )

    assert result.detected_intent == IntentName.CREATE_TICKET.value
    assert result.active_ticket_number == "44001"
