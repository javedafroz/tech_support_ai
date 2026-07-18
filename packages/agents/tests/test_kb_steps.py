from __future__ import annotations

from uuid import uuid4

from tech_support_agents.kb import _extract_steps, _match_from_hits


class _Hit:
    def __init__(
        self,
        document_id,
        chunk_index,
        body,
        title="VPN Guide",
        section_title=None,
        score=0.9,
        chunk_id=None,
    ):
        self.document_id = document_id
        self.chunk_index = chunk_index
        self.body = body
        self.title = title
        self.section_title = section_title
        self.score = score
        self.chunk_id = chunk_id or uuid4()


_MARKDOWN = """# VPN AnyConnect DPD

Some intro text.

## Step 1 — Reconnect the VPN
Disconnect and reconnect the AnyConnect client.

## Step 2 — Reset the network adapter
Disable then re-enable the adapter.

## Step 3 — Create a support ticket
If the above fails, raise a ticket.
"""


def test_extract_steps_keeps_actionable_steps_and_drops_ticket_step():
    steps = _extract_steps(_MARKDOWN, max_steps=5)
    titles = [s["title"] for s in steps]
    assert "Step 1 — Reconnect the VPN" in titles
    assert "Step 2 — Reset the network adapter" in titles
    # The "Create a support ticket" step is the escalation fallback, not a user action.
    assert all("ticket" not in t.lower() for t in titles)
    assert len(steps) == 2


def test_extract_steps_respects_max():
    steps = _extract_steps(_MARKDOWN, max_steps=1)
    assert len(steps) == 1


def test_match_from_hits_uses_top_document():
    doc_a = uuid4()
    doc_b = uuid4()
    hits = [
        _Hit(
            doc_a,
            0,
            "# Guide A\n\n## Step 1 — Try this\nDo the thing.",
            title="Guide A",
            score=0.95,
        ),
        _Hit(doc_a, 1, "## Step 2 — Try that\nDo the other thing.", title="Guide A", score=0.7),
        _Hit(doc_b, 0, "## Step 1 — Unrelated\nNope.", title="Guide B", score=0.6),
    ]
    match = _match_from_hits(hits, max_steps=5)
    assert match is not None
    assert match.title == "Guide A"
    assert len(match.steps) == 2
    assert len(match.contexts) == 2
    assert [c.source_id for c in match.contexts] == ["src1", "src2"]
    assert match.contexts[0].chunk_index == 0
    assert match.contexts[1].chunk_index == 1
    assert all(c.document_id == str(doc_a) for c in match.contexts)


def test_match_from_hits_empty():
    assert _match_from_hits([], max_steps=5) is None


def test_match_from_hits_fallback_to_chunk_when_no_step_headings():
    doc = uuid4()
    hits = [_Hit(doc, 0, "Just some prose with no headings at all.", title="Prose")]
    match = _match_from_hits(hits, max_steps=5, problem="anything")
    assert match is not None
    assert len(match.steps) == 1
    assert "prose" in match.steps[0]["instruction"].lower()
    assert len(match.contexts) == 1
    assert match.contexts[0].source_id == "src1"


_FAQ_PAGE = """## 11. An application refuses to install on my computer.

- The Cause: Your security software blocked it.
- The Solution: Delete the installation file and download it again.

## 12. My computer is running incredibly slowly and lagging.

- The Cause: A background process is hogging resources.
- The Solution: Open Task Manager and End Task.

## 13. I cannot print anything from my Windows computer.

- The Cause: A loose cable, a disconnect from the office Wi-Fi, or incorrect print settings.
- The Solution: Check all physical connection cables and verify your computer is connected to the right network.
"""


def test_match_from_hits_faq_selects_relevant_section_only():
    doc = uuid4()
    hits = [
        _Hit(
            doc,
            0,
            _FAQ_PAGE,
            title="L1 Handbook",
            section_title="11. An application refuses to install on my computer.",
            score=0.88,
        )
    ]
    match = _match_from_hits(
        hits,
        max_steps=5,
        problem="I am not able to print anything from my computer",
    )
    assert match is not None
    assert len(match.steps) == 1
    step = match.steps[0]
    assert "print" in step["title"].lower()
    assert "13." in step["title"]
    assert "install" not in step["instruction"].lower()
    assert "slowly" not in step["instruction"].lower()
    assert "print" in step["instruction"].lower()
    assert match.contexts[0].body  # full page retained for RAG; extractive picks section


def test_match_from_hits_truncates_no_heading_fallback():
    doc = uuid4()
    long_body = "word " * 500
    hits = [_Hit(doc, 0, long_body, title="Blob")]
    match = _match_from_hits(hits, max_steps=5, problem="print")
    assert match is not None
    assert len(match.steps[0]["instruction"]) <= 1200


def test_match_from_hits_caps_prompt_context_size():
    doc = uuid4()
    hits = [
        _Hit(doc, 0, "A" * 100, title="Doc", score=0.9),
        _Hit(doc, 1, "B" * 100, title="Doc", score=0.8),
        _Hit(doc, 2, "C" * 100, title="Doc", score=0.7),
    ]
    match = _match_from_hits(hits, max_steps=5, max_context_chars=150)
    assert match is not None
    total = sum(len(c.body) for c in match.contexts)
    assert total <= 150
    assert match.contexts[0].source_id == "src1"
    assert len(match.contexts) >= 1
