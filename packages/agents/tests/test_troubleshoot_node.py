from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from tech_support_agents.graph import _route_after_conversation, _route_after_troubleshoot
from tech_support_agents.kb import RetrievedContext, RunbookMatch, configure_runbook_retriever
from tech_support_agents.llm import LLMSettings, configure_llm
from tech_support_agents.nodes.troubleshoot import (
    _classify,
    _empathy_opener,
    _validate_guidance,
    troubleshoot_node,
)
from tech_support_agents.providers.mock import MockConversationLLM
from tech_support_agents.rag_guidance import TroubleshootGuidance, TroubleshootStepGuidance
from tech_support_orchestration.models import IntentName, StructuredIntent


@pytest.fixture(autouse=True)
def _mock_llm():
    configure_llm(LLMSettings(graph_llm_mode="mock"))
    yield


def test_empathy_opener_normalizes_third_person_summary():
    opener = _empathy_opener("user is unable to print anything from their computer.")
    assert "I'm sorry you're dealing with" in opener
    assert "unable to print anything from your computer" in opener
    assert "user is" not in opener.lower()
    assert "their" not in opener.lower()
    assert ".." not in opener


def test_empathy_opener_strips_trailing_punctuation():
    opener = _empathy_opener("Printer offline.")
    assert "dealing with printer offline." in opener
    assert "offline.." not in opener


def test_empathy_opener_falls_back_when_summary_unusable():
    opener = _empathy_opener("They are stuck.")
    assert "I'm sorry you're running into this" in opener


@pytest.mark.parametrize(
    "text,expected",
    [
        ("yes", "resolved"),
        ("Yes it worked", "resolved"),
        ("yeah that fixed it", "resolved"),
        ("that worked, thanks", "resolved"),
        ("it's no longer disconnecting", "resolved"),
        ("no", "failed"),
        ("nope", "failed"),
        ("no it's not fixed", "failed"),
        ("its not fixed", "failed"),
        ("i tried that already", "failed"),
        ("still not working", "failed"),
        ("same problem", "failed"),
        ("please just create a ticket", "escalate"),
        ("can I talk to a human", "escalate"),
        ("what does DPD mean?", "unclear"),
    ],
)
def test_classify(text, expected):
    assert _classify(text) == expected


class _FakeRetriever:
    def __init__(self, match: RunbookMatch | None) -> None:
        self._match = match
        self.last_problem: str | None = None

    def get_runbook(self, problem: str) -> RunbookMatch | None:
        self.last_problem = problem
        return self._match


def _contexts(doc_id: str, *bodies: str) -> list[RetrievedContext]:
    return [
        RetrievedContext(
            source_id=f"src{idx}",
            chunk_id=f"chunk-{idx}",
            document_id=doc_id,
            title="VPN AnyConnect DPD",
            section_title=f"Section {idx}",
            score=0.9 - (idx * 0.05),
            body=body,
            chunk_index=idx - 1,
        )
        for idx, body in enumerate(bodies, start=1)
    ]


def _two_step_match(*, with_contexts: bool = True) -> RunbookMatch:
    doc_id = str(uuid4())
    steps = [
        {"title": "Step 1 — Reconnect", "instruction": "Disconnect and reconnect the VPN."},
        {"title": "Step 2 — Reset adapter", "instruction": "Restart the network adapter."},
    ]
    contexts = (
        _contexts(
            doc_id,
            "Disconnect and reconnect the VPN client.",
            "Restart the network adapter if reconnect fails.",
        )
        if with_contexts
        else []
    )
    return RunbookMatch(
        document_id=doc_id,
        title="VPN AnyConnect DPD",
        score=0.9,
        contexts=contexts,
        steps=steps,
    )


def _create_ticket_intent() -> StructuredIntent:
    return StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.9,
        session_id=uuid4(),
        user_id="user@company.com",
        payload={"title": "VPN drops", "description": "VPN keeps disconnecting"},
        timestamp=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def _clear_retriever():
    yield
    configure_runbook_retriever(None)


def _state(
    intent: StructuredIntent | None = None,
    *,
    troubleshoot=None,
    user_input="",
    messages=None,
    is_support_issue: bool = False,
    problem_summary: str | None = None,
    active_ticket_number: str | None = None,
    user_email: str | None = "user@company.com",
    session_id: str | None = None,
) -> dict:
    sid = session_id or (str(intent.session_id) if intent else str(uuid4()))
    uid = intent.user_id if intent else "user@company.com"
    state: dict = {
        "session_id": sid,
        "user_id": uid,
        "user_email": user_email,
        "user_input": user_input,
        "system_statuses": [],
        "messages": messages or [],
        "troubleshoot": troubleshoot or {},
        "is_support_issue": is_support_issue,
        "problem_summary": problem_summary,
    }
    if intent is not None:
        state["structured_intent"] = intent
    if active_ticket_number:
        state["active_ticket_number"] = active_ticket_number
    return state


def test_validate_guidance_rejects_unknown_source():
    guidance = TroubleshootGuidance(
        supported=True,
        intro="Hi",
        steps=[TroubleshootStepGuidance(instruction="Try this", source_ids=["src99"])],
    )
    assert _validate_guidance(guidance, allowed_source_ids={"src1"}, max_steps=5) == (
        "unknown_source_src99"
    )


def test_repair_guidance_sources_maps_invented_ids():
    from tech_support_agents.nodes.troubleshoot import _repair_guidance_sources

    doc_id = str(uuid4())
    contexts = _contexts(doc_id, "Check printer cables and Wi-Fi.", "Restart the spooler.")
    guidance = TroubleshootGuidance(
        supported=True,
        intro="Hi",
        steps=[
            TroubleshootStepGuidance(
                instruction="Check the printer cables carefully.",
                source_ids=["src13"],
            )
        ],
    )
    repaired = _repair_guidance_sources(guidance, contexts)
    assert repaired.steps[0].source_ids == ["src1"]
    assert (
        _validate_guidance(
            repaired, allowed_source_ids={c.source_id for c in contexts}, max_steps=5
        )
        is None
    )


def test_validate_guidance_rejects_too_many_steps():
    guidance = TroubleshootGuidance(
        supported=True,
        intro="Hi",
        steps=[
            TroubleshootStepGuidance(instruction="A", source_ids=["src1"]),
            TroubleshootStepGuidance(instruction="B", source_ids=["src1"]),
        ],
    )
    assert _validate_guidance(guidance, allowed_source_ids={"src1"}, max_steps=1) == (
        "too_many_steps"
    )


@pytest.mark.asyncio
async def test_begin_presents_rag_adaptive_steps():
    configure_runbook_retriever(_FakeRetriever(_two_step_match()))
    intent = _create_ticket_intent()
    out = await troubleshoot_node(_state(intent, user_input="VPN keeps disconnecting"))

    assert out["troubleshoot"]["status"] == "guiding"
    assert out["troubleshoot"]["generation_mode"] == "rag"
    assert 1 <= len(out["troubleshoot"]["steps"]) <= 2
    assert out["troubleshoot"]["source_citations"]
    assert out["needs_clarification"] is True
    reply = out["assistant_reply"]
    assert "I'm sorry" in reply
    assert "guide" not in reply.lower()
    assert "handbook" not in reply.lower()
    assert "VPN AnyConnect" not in reply  # do not reveal runbook title
    assert "open a ticket" in reply
    assert "structured_intent" not in out  # intent untouched while guiding


@pytest.mark.asyncio
async def test_begin_extractive_fallback_when_no_contexts():
    configure_runbook_retriever(_FakeRetriever(_two_step_match(with_contexts=False)))
    intent = _create_ticket_intent()
    out = await troubleshoot_node(_state(intent, user_input="VPN keeps disconnecting"))

    assert out["troubleshoot"]["status"] == "guiding"
    assert out["troubleshoot"]["generation_mode"] == "extractive_fallback"
    assert len(out["troubleshoot"]["steps"]) == 1
    assert "Reconnect" in out["assistant_reply"] or "Disconnect" in out["assistant_reply"]


@pytest.mark.asyncio
async def test_begin_unsupported_falls_back_then_skips_without_steps(monkeypatch):
    match = _two_step_match()
    match.steps = []  # no extractive fallback
    configure_runbook_retriever(_FakeRetriever(match))

    async def _unsupported(*_a, **_k):
        return TroubleshootGuidance(supported=False, intro="", steps=[])

    monkeypatch.setattr(MockConversationLLM, "generate_troubleshoot_guidance", _unsupported)
    out = await troubleshoot_node(
        _state(_create_ticket_intent(), user_input="weird issue")
    )
    assert out["troubleshoot"]["status"] == "skipped"
    assert "assistant_reply" not in out


@pytest.mark.asyncio
async def test_begin_generation_exception_falls_back(monkeypatch):
    configure_runbook_retriever(_FakeRetriever(_two_step_match()))

    async def _boom(*_a, **_k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(MockConversationLLM, "generate_troubleshoot_guidance", _boom)
    out = await troubleshoot_node(
        _state(_create_ticket_intent(), user_input="VPN keeps disconnecting")
    )
    assert out["troubleshoot"]["status"] == "guiding"
    assert out["troubleshoot"]["generation_mode"] == "extractive_fallback"
    assert out["troubleshoot"]["rag_failure_reason"] == "generation_error"


@pytest.mark.asyncio
async def test_first_turn_support_issue_begins_without_create_ticket_intent():
    retriever = _FakeRetriever(_two_step_match())
    configure_runbook_retriever(retriever)
    out = await troubleshoot_node(
        _state(
            None,
            user_input="VPN keeps disconnecting with DPD timeout",
            is_support_issue=True,
            problem_summary="Cisco AnyConnect VPN disconnects with DPD timeout",
        )
    )

    assert out["troubleshoot"]["status"] == "guiding"
    assert out["troubleshoot"]["problem"] == (
        "Cisco AnyConnect VPN disconnects with DPD timeout"
    )
    assert retriever.last_problem == "Cisco AnyConnect VPN disconnects with DPD timeout"
    assert out["troubleshoot"]["steps"]
    reply = out["assistant_reply"]
    assert "I'm sorry you're dealing with" in reply
    assert "cisco AnyConnect VPN disconnects with DPD timeout" in reply.lower() or (
        "VPN" in reply
    )
    assert "guide" not in reply.lower()
    assert "handbook" not in reply.lower()
    assert "structured_intent" not in out


@pytest.mark.asyncio
async def test_first_turn_no_handbook_skips_without_clobbering_reply():
    configure_runbook_retriever(_FakeRetriever(None))
    out = await troubleshoot_node(
        _state(
            None,
            user_input="My computer is running very slow",
            is_support_issue=True,
            problem_summary="Computer running very slow",
        )
    )

    assert out["troubleshoot"]["status"] == "skipped"
    assert "assistant_reply" not in out
    assert "structured_intent" not in out


@pytest.mark.asyncio
async def test_guiding_failed_escalates_without_ready_intent():
    match = _two_step_match()
    configure_runbook_retriever(_FakeRetriever(match))
    ts = {
        "status": "guiding",
        "document_id": "doc-1",
        "runbook_title": match.title,
        "steps": [{"instruction": "Reconnect VPN", "source_ids": ["src1"]}],
        "step_index": 1,
        "attempts": [],
        "problem": "VPN DPD timeout",
        "source_citations": [{"source_id": "src1", "chunk_id": "c1"}],
    }
    out = await troubleshoot_node(
        _state(None, troubleshoot=ts, user_input="no", is_support_issue=True)
    )

    assert out["troubleshoot"]["status"] == "escalated"
    assert out["needs_clarification"] is False
    assert out["structured_intent"].intent == IntentName.CREATE_TICKET


@pytest.mark.asyncio
async def test_escalate_synthesizes_create_ticket_when_intent_absent():
    match = _two_step_match()
    configure_runbook_retriever(_FakeRetriever(match))
    ts = {
        "status": "guiding",
        "document_id": "doc-1",
        "runbook_title": match.title,
        "steps": [{"instruction": "Reconnect VPN", "source_ids": ["src1"]}],
        "step_index": 1,
        "attempts": [],
        "problem": "VPN keeps disconnecting with DPD timeout",
        "source_citations": [
            {"source_id": "src1", "chunk_id": "c1", "section_title": "Reconnect"}
        ],
    }
    out = await troubleshoot_node(
        _state(
            None,
            troubleshoot=ts,
            user_input="still not working",
            is_support_issue=True,
            user_email="user@company.com",
        )
    )

    assert out["troubleshoot"]["status"] == "escalated"
    assert out["needs_clarification"] is False
    intent = out["structured_intent"]
    assert intent.intent == IntentName.CREATE_TICKET
    assert intent.payload["customer_email"] == "user@company.com"
    assert "VPN keeps disconnecting" in intent.payload["description"]
    assert "Troubleshooting performed by Tech Support AI" in intent.payload["description"]
    assert "src1" in intent.payload["description"]


@pytest.mark.asyncio
async def test_active_ticket_skips_troubleshoot():
    configure_runbook_retriever(_FakeRetriever(_two_step_match()))
    intent = _create_ticket_intent()
    out = await troubleshoot_node(
        _state(intent, user_input="VPN issue", active_ticket_number="12345")
    )
    assert out == {}


@pytest.mark.asyncio
async def test_resolved_deflects_without_ticket():
    configure_runbook_retriever(_FakeRetriever(_two_step_match()))
    intent = _create_ticket_intent()
    ts = {
        "status": "guiding",
        "document_id": "doc-1",
        "runbook_title": "VPN AnyConnect DPD",
        "steps": [
            {"instruction": "Reconnect VPN", "source_ids": ["src1"]},
            {"instruction": "Reset adapter", "source_ids": ["src2"]},
        ],
        "step_index": 2,
        "attempts": [],
    }
    out = await troubleshoot_node(
        _state(intent, troubleshoot=ts, user_input="that worked, thanks!")
    )

    assert out["troubleshoot"]["status"] == "resolved"
    assert out["troubleshoot_deflection"]["outcome"] == "resolved"
    assert out["troubleshoot_deflection"]["steps_count"] == 2
    assert "structured_intent" not in out  # no ticket enrichment on resolve


@pytest.mark.asyncio
async def test_failed_escalates_immediately():
    match = _two_step_match()
    configure_runbook_retriever(_FakeRetriever(match))
    intent = _create_ticket_intent()
    ts = {
        "status": "guiding",
        "document_id": "doc-1",
        "runbook_title": match.title,
        "steps": [
            {"instruction": "Reconnect VPN", "source_ids": ["src1"]},
            {"instruction": "Reset adapter", "source_ids": ["src2"]},
        ],
        "step_index": 2,
        "attempts": [],
    }
    out = await troubleshoot_node(
        _state(intent, troubleshoot=ts, user_input="i tried that and its not working")
    )

    assert out["troubleshoot"]["status"] == "escalated"
    assert out["needs_clarification"] is False
    assert out["assistant_reply"] is None  # do not keep a stale clarify reply
    assert out["troubleshoot_deflection"]["outcome"] == "escalated"
    assert len(out["troubleshoot"]["attempts"]) == 2
    assert "Troubleshooting performed by Tech Support AI" in (
        out["structured_intent"].payload["description"]
    )


@pytest.mark.asyncio
async def test_failed_escalates_with_transcript_and_steps():
    match = _two_step_match()
    configure_runbook_retriever(_FakeRetriever(match))
    intent = _create_ticket_intent()
    ts = {
        "status": "guiding",
        "document_id": "doc-1",
        "runbook_title": match.title,
        "steps": [{"instruction": "Reconnect VPN", "source_ids": ["src1"]}],
        "step_index": 1,
        "attempts": [],
        "source_citations": [{"source_id": "src1", "chunk_id": "c1"}],
    }
    messages = [
        HumanMessage(content="VPN keeps disconnecting"),
        AIMessage(content="Try this step"),
    ]
    out = await troubleshoot_node(
        _state(intent, troubleshoot=ts, user_input="still not working", messages=messages)
    )

    assert out["troubleshoot"]["status"] == "escalated"
    assert out["needs_clarification"] is False
    assert out["troubleshoot_deflection"]["outcome"] == "escalated"
    enriched = out["structured_intent"].payload["description"]
    assert "Troubleshooting performed by Tech Support AI" in enriched
    assert match.title in enriched
    assert "Full chat transcript" in enriched
    assert "VPN keeps disconnecting" in enriched


@pytest.mark.asyncio
async def test_explicit_ticket_request_escalates_immediately():
    configure_runbook_retriever(_FakeRetriever(_two_step_match()))
    intent = _create_ticket_intent()
    out = await troubleshoot_node(
        _state(intent, user_input="just create a ticket please", messages=[])
    )

    assert out["troubleshoot"]["status"] == "escalated"
    assert out["needs_clarification"] is False
    assert "structured_intent" in out


@pytest.mark.asyncio
async def test_no_matching_handbook_skips_to_ticket():
    configure_runbook_retriever(_FakeRetriever(None))
    intent = _create_ticket_intent()
    out = await troubleshoot_node(_state(intent, user_input="obscure problem"))

    assert out["troubleshoot"]["status"] == "skipped"
    assert "assistant_reply" not in out
    assert "structured_intent" not in out


@pytest.mark.asyncio
async def test_non_create_ticket_intent_passes_through():
    intent = StructuredIntent(
        intent=IntentName.CHECK_STATUS,
        confidence=0.9,
        session_id=uuid4(),
        user_id="user@company.com",
        payload={},
        timestamp=datetime.now(UTC),
    )
    out = await troubleshoot_node(_state(intent, user_input="what's my ticket status"))
    assert out == {}


def test_routing_flag_off_skips_troubleshoot():
    intent = _create_ticket_intent()
    state = {"structured_intent": intent, "kb_rag_enabled": False, "is_support_issue": True}
    assert _route_after_conversation(state) == "orchestrate"


def test_routing_flag_on_enters_troubleshoot():
    intent = _create_ticket_intent()
    state = {"structured_intent": intent, "kb_rag_enabled": True}
    assert _route_after_conversation(state) == "troubleshoot"


def test_routing_first_turn_support_issue_enters_troubleshoot():
    state = {
        "kb_rag_enabled": True,
        "is_support_issue": True,
        "needs_clarification": True,
        "structured_intent": None,
        "problem_summary": "VPN disconnects",
    }
    assert _route_after_conversation(state) == "troubleshoot"


def test_routing_guiding_continues_regardless_of_llm_readiness():
    state = {
        "kb_rag_enabled": True,
        "troubleshoot": {"status": "guiding"},
        "needs_clarification": True,
        "structured_intent": None,
        "is_support_issue": False,
    }
    assert _route_after_conversation(state) == "troubleshoot"


def test_routing_skipped_does_not_reenter_troubleshoot():
    state = {
        "kb_rag_enabled": True,
        "is_support_issue": True,
        "troubleshoot": {"status": "skipped"},
        "needs_clarification": True,
        "structured_intent": None,
    }
    assert _route_after_conversation(state) == "respond"


def test_routing_active_ticket_skips_troubleshoot():
    intent = _create_ticket_intent()
    state = {
        "structured_intent": intent,
        "kb_rag_enabled": True,
        "is_support_issue": True,
        "active_ticket_number": "12345",
    }
    assert _route_after_conversation(state) == "orchestrate"


def test_route_after_troubleshoot_guiding_to_respond():
    assert _route_after_troubleshoot({"troubleshoot": {"status": "guiding"}}) == "respond"


def test_route_after_troubleshoot_escalated_to_orchestrate():
    assert _route_after_troubleshoot({"troubleshoot": {"status": "escalated"}}) == "orchestrate"


def test_route_after_troubleshoot_skipped_with_intent_to_orchestrate():
    intent = _create_ticket_intent()
    assert (
        _route_after_troubleshoot(
            {"troubleshoot": {"status": "skipped"}, "structured_intent": intent}
        )
        == "orchestrate"
    )


def test_route_after_troubleshoot_skipped_without_intent_to_respond():
    assert (
        _route_after_troubleshoot(
            {
                "troubleshoot": {"status": "skipped"},
                "needs_clarification": True,
                "structured_intent": None,
            }
        )
        == "respond"
    )
