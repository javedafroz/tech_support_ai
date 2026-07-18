"""Troubleshoot node: classic RAG grounded guidance before creating a ticket.

Engages as soon as a support issue is detected (``is_support_issue`` or a ready
``CreateTicket`` intent) when KB/RAG is enabled — before ticket slot-filling.

Flow:
1. Retrieve handbook chunks (deterministic embeddings + vector search).
2. Ask the configured LLM to synthesize adaptive grounded guidance with source refs.
3. Validate citations / limits deterministically; fall back to one extractive section.
4. Present guidance once; on failure or ticket request, escalate immediately.

It never takes actions on the user's behalf. Handbook titles are never shown to
the end user. If no grounded guidance is available, status is ``skipped`` and the
normal clarify/ticket flow continues. If the user resolves the issue, the turn is
deflected (no ticket).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from tech_support_orchestration.models import IntentName, StructuredIntent

from tech_support_agents.kb import RetrievedContext, RunbookMatch, get_runbook
from tech_support_agents.llm import get_conversation_llm
from tech_support_agents.rag_guidance import TroubleshootGuidance
from tech_support_agents.state import SupportGraphState

logger = logging.getLogger(__name__)

_ESCALATE_PHRASES = (
    "create a ticket",
    "raise a ticket",
    "open a ticket",
    "log a ticket",
    "make a ticket",
    "just ticket",
    "escalate",
    "talk to a human",
    "human agent",
    "speak to someone",
    "speak to an agent",
    "real person",
)

# Phrases that mean "resolved" even though they contain a negation word — these
# must be checked before the generic negative matcher below.
_RESOLVED_NEGATION_PHRASES = (
    "no longer",
    "not happening",
    "doesn't happen anymore",
    "stopped happening",
    "stopped disconnecting",
    "problem gone",
    "issue gone",
    "gone now",
)

_POSITIVE_RE = re.compile(
    r"\b(yes|yep|yeah|yup|fixed|resolved|solved|sorted|worked|works|working|"
    r"success|successful|all\s+good|good\s+now|that\s+did\s+it|did\s+the\s+trick)\b"
)
_NEGATIVE_RE = re.compile(
    r"\b(no|nope|nah|not|isn'?t|doesn'?t|didn'?t|don'?t|can'?t|cannot|wont|won'?t|"
    r"still|already\s+tried|tried\s+(that|it|this)|no\s+luck|same|unchanged|"
    r"negative|not\s+yet)\b"
)


def _classify_deterministic(text: str) -> str:
    """Interpret a user reply during guided troubleshooting (regex only)."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in _ESCALATE_PHRASES):
        return "escalate"
    if any(phrase in lowered for phrase in _RESOLVED_NEGATION_PHRASES):
        return "resolved"
    if _NEGATIVE_RE.search(lowered):
        return "failed"
    if _POSITIVE_RE.search(lowered):
        return "resolved"
    return "unclear"


# Back-compat alias used by existing unit tests.
_classify = _classify_deterministic


async def _classify_reply(text: str, state: SupportGraphState) -> str:
    signal = _classify_deterministic(text)
    if signal != "unclear":
        return signal
    try:
        gateway = get_conversation_llm()
        outcome = await gateway.classify_troubleshoot_outcome(
            text,
            history=list(state.get("messages") or []),
        )
        if outcome in {"resolved", "failed", "escalate", "unclear"}:
            return outcome
    except Exception:
        logger.exception("Troubleshoot outcome classifier failed; treating as unclear")
    return "unclear"


def _problem_text(state: SupportGraphState, intent) -> str:
    summary = (state.get("problem_summary") or "").strip()
    if summary:
        return summary
    if intent is not None:
        payload = intent.payload or {}
        parts = [
            str(payload.get("title") or ""),
            str(payload.get("description") or ""),
            str(payload.get("summary") or ""),
        ]
        text = " ".join(part for part in parts if part).strip()
        if text:
            return text
    return state.get("user_input", "")


def _ensure_create_ticket_intent(state: SupportGraphState, ts: dict, intent):
    """Return a CreateTicket intent, synthesizing one when the LLM hasn't produced
    a ready intent yet (e.g. user escalated during guiding before slot-filling)."""
    if intent is not None and intent.intent == IntentName.CREATE_TICKET:
        return intent
    problem = (
        ts.get("problem")
        or state.get("problem_summary")
        or state.get("user_input")
        or "Support request"
    ).strip()
    payload: dict = {
        "title": problem[:80] or "Support request",
        "description": problem or "Support request",
    }
    if state.get("user_email"):
        payload["customer_email"] = state["user_email"]
    return StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.9,
        session_id=UUID(state["session_id"]),
        user_id=state["user_id"],
        payload=payload,
        timestamp=datetime.now(UTC),
    )


def _normalize_step_instruction(text: str) -> str:
    """Ensure numbered list items land on their own lines for Markdown rendering."""
    normalized = text.strip()
    if not normalized:
        return normalized
    normalized = re.sub(r"(?<!\n)(?<!^)\s+(\d{1,2}\.\s+)", r"\n\1", normalized)
    return normalized.strip()


_THIRD_PERSON_LEAD_RE = re.compile(
    r"^(?:the\s+)?(?:user|customer|employee)\s+(?:is|was|has|have|are|were)\s+",
    re.I,
)
_THEIR_RE = re.compile(r"\btheir\b", re.I)
_THEY_ARE_RE = re.compile(r"\bthey\s+are\b", re.I)
_TRAILING_PUNCT_RE = re.compile(r"[.!?…]+$")


def _normalize_problem_for_opener(problem: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", (problem or "").strip())
    if not cleaned:
        return None
    cleaned = _TRAILING_PUNCT_RE.sub("", cleaned).strip()
    if not cleaned:
        return None

    cleaned = _THIRD_PERSON_LEAD_RE.sub("", cleaned)
    cleaned = _THEY_ARE_RE.sub("you're", cleaned)
    cleaned = _THEIR_RE.sub("your", cleaned)
    cleaned = cleaned.strip(" ,;-")
    if not cleaned:
        return None

    if len(cleaned) > 120:
        cleaned = cleaned[:117].rstrip() + "…"

    lowered = cleaned.lower()
    if lowered.startswith(
        ("he ", "she ", "they ", "it ", "i ", "we ", "you're ", "you are ", "i'm ", "we're ")
    ):
        return None

    return cleaned[0].lower() + cleaned[1:] if cleaned else None


def _empathy_opener(problem: str) -> str:
    """Professional, empathetic opener — never mention handbooks or sources."""
    display = _normalize_problem_for_opener(problem)
    if display:
        return (
            f"I'm sorry you're dealing with {display}. "
            "That can be frustrating — let's try a quick step that often helps:"
        )
    return (
        "I'm sorry you're running into this — that can be frustrating. "
        "Let's try a quick step that often helps:"
    )


def _max_steps() -> int:
    try:
        from tech_support_knowledge.store import get_knowledge_settings

        return int(get_knowledge_settings().max_troubleshoot_steps)
    except Exception:
        return 5


def _contexts_as_dicts(contexts: list[RetrievedContext]) -> list[dict[str, str]]:
    return [
        {
            "source_id": ctx.source_id,
            "chunk_id": ctx.chunk_id,
            "document_id": ctx.document_id,
            "title": ctx.title,
            "section_title": ctx.section_title or "",
            "body": ctx.body,
        }
        for ctx in contexts
    ]


def _validate_guidance(
    guidance: TroubleshootGuidance,
    *,
    allowed_source_ids: set[str],
    max_steps: int,
) -> str | None:
    """Return a validation failure reason, or None if guidance is usable."""
    if not guidance.supported:
        return "unsupported"
    if not guidance.steps:
        return "empty_steps"
    if len(guidance.steps) > max_steps:
        return "too_many_steps"
    for idx, step in enumerate(guidance.steps, start=1):
        instruction = (step.instruction or "").strip()
        if not instruction:
            return f"empty_instruction_{idx}"
        if not step.source_ids:
            return f"missing_source_ids_{idx}"
        for source_id in step.source_ids:
            if source_id not in allowed_source_ids:
                return f"unknown_source_{source_id}"
    return None


def _best_source_for_instruction(
    instruction: str,
    contexts: list[RetrievedContext],
) -> str | None:
    """Pick the retrieved source whose body best overlaps the step instruction."""
    if not contexts:
        return None
    from tech_support_agents.kb import _tokens

    instr_tokens = _tokens(instruction)
    if not instr_tokens:
        return contexts[0].source_id
    best_id = contexts[0].source_id
    best_score = -1.0
    for ctx in contexts:
        overlap = len(instr_tokens & _tokens(ctx.body))
        # Prefer higher overlap; break ties with retrieval score.
        score = float(overlap) + (0.01 * ctx.score)
        if score > best_score:
            best_score = score
            best_id = ctx.source_id
    return best_id


def _repair_guidance_sources(
    guidance: TroubleshootGuidance,
    contexts: list[RetrievedContext],
) -> TroubleshootGuidance:
    """Replace invented source_ids (e.g. FAQ numbers) with retrieved ones."""
    allowed = {c.source_id for c in contexts}
    if not allowed:
        return guidance
    from tech_support_agents.rag_guidance import TroubleshootStepGuidance

    repaired = []
    for step in guidance.steps:
        valid = [sid for sid in step.source_ids if sid in allowed]
        if not valid:
            fallback_id = _best_source_for_instruction(step.instruction, contexts)
            valid = [fallback_id] if fallback_id else [contexts[0].source_id]
        repaired.append(
            TroubleshootStepGuidance(instruction=step.instruction, source_ids=valid)
        )
    return guidance.model_copy(update={"steps": repaired})


def _format_guidance_reply(
    *,
    intro: str,
    steps: list[dict[str, str]],
    follow_up: str,
    problem: str,
) -> str:
    intro_text = (intro or "").strip() or _empathy_opener(problem)
    body_parts: list[str] = []
    if len(steps) == 1:
        instruction = _normalize_step_instruction(steps[0].get("instruction") or "")
        body_parts.append(instruction)
    else:
        for idx, step in enumerate(steps, start=1):
            instruction = _normalize_step_instruction(step.get("instruction") or "")
            body_parts.append(f"{idx}. {instruction}")
    footer = (follow_up or "").strip() or (
        "Give that a try and let me know if it worked. "
        "If it's still not resolved, say so and I'll open a ticket for you."
    )
    return f"{intro_text}\n\n" + "\n\n".join(body_parts) + f"\n\n{footer}"


def _fallback_from_match(match: RunbookMatch, problem: str) -> tuple[list[dict[str, str]], str] | None:
    """Build a single extractive step reply when RAG generation is unavailable."""
    if not match.steps:
        return None
    step = match.steps[0]
    instruction = _normalize_step_instruction(
        step.get("instruction") or step.get("title") or ""
    )
    if not instruction:
        return None
    presented = [
        {
            "title": (step.get("title") or "").strip(),
            "instruction": instruction,
            "source_ids": [match.contexts[0].source_id] if match.contexts else [],
        }
    ]
    reply = _format_guidance_reply(
        intro=_empathy_opener(problem),
        steps=presented,
        follow_up=(
            "Give that a try and let me know if it worked. "
            "If it's still not resolved, say so and I'll open a ticket for you."
        ),
        problem=problem,
    )
    return presented, reply


def _transcript(messages: list) -> str:
    lines: list[str] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        else:
            continue
        content = message.content if isinstance(message.content, str) else str(message.content)
        content = content.strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_enrichment(state: SupportGraphState, ts: dict, reason: str) -> str:
    from tech_support_knowledge.store import get_knowledge_settings

    lines = ["--- Troubleshooting performed by Tech Support AI ---"]
    if ts.get("runbook_title"):
        lines.append(f"Handbook consulted: {ts['runbook_title']}")
    reason_label = {
        "requested": "customer asked to open a ticket",
        "exhausted": "guided steps did not resolve the issue",
        "failed": "guided steps did not resolve the issue",
    }.get(reason, reason)
    lines.append(f"Outcome: {reason_label}")

    attempts = ts.get("attempts") or []
    if attempts:
        lines.append("Steps attempted:")
        for idx, attempt in enumerate(attempts, start=1):
            outcome = attempt.get("outcome", "unknown")
            instruction = attempt.get("instruction") or attempt.get("title") or "step"
            source_ids = attempt.get("source_ids") or []
            cite = f" [{', '.join(source_ids)}]" if source_ids else ""
            lines.append(f"  {idx}. {instruction}{cite} — {outcome}")

    citations = ts.get("source_citations") or []
    if citations:
        lines.append("Internal source references:")
        for cite in citations:
            section = cite.get("section_title") or ""
            source_id = cite.get("source_id") or ""
            chunk_id = cite.get("chunk_id") or ""
            label = f"{source_id}"
            if section:
                label += f" ({section})"
            if chunk_id:
                label += f" chunk={chunk_id}"
            lines.append(f"  - {label}")

    summary = "\n".join(lines)

    include_transcript = True
    try:
        include_transcript = get_knowledge_settings().include_chat_transcript_in_ticket
    except Exception:
        logger.exception("Could not read knowledge settings; including transcript by default")
    if include_transcript:
        transcript = _transcript(state.get("messages", []))
        if transcript:
            summary += "\n\n--- Full chat transcript ---\n" + transcript
    return summary


def _escalate(
    state: SupportGraphState,
    ts: dict,
    statuses: list[str],
    intent,
    reason: str,
) -> dict:
    ts["status"] = "escalated"
    intent = _ensure_create_ticket_intent(state, ts, intent)
    enrichment = _build_enrichment(state, ts, reason)
    payload = dict(intent.payload or {})
    base_description = str(payload.get("description") or "").strip()
    payload["description"] = (
        f"{base_description}\n\n{enrichment}".strip() if base_description else enrichment
    )
    new_intent = intent.model_copy(update={"payload": payload})
    statuses.append("Preparing your ticket…")
    return {
        "troubleshoot": ts,
        "structured_intent": new_intent,
        "system_statuses": statuses,
        "needs_clarification": False,
        # Clear any leftover conversation clarify so respond shows the ticket message.
        "assistant_reply": None,
        "troubleshoot_deflection": {
            "outcome": "escalated",
            "document_id": ts.get("document_id"),
            "steps_count": len(ts.get("attempts") or []),
        },
    }


def _source_citations(contexts: list[RetrievedContext]) -> list[dict[str, str]]:
    return [
        {
            "source_id": ctx.source_id,
            "chunk_id": ctx.chunk_id,
            "document_id": ctx.document_id,
            "section_title": ctx.section_title or "",
            "score": str(ctx.score),
        }
        for ctx in contexts
    ]


async def _generate_guidance(
    problem: str,
    match: RunbookMatch,
    state: SupportGraphState,
    max_steps: int,
) -> tuple[TroubleshootGuidance | None, str | None, float]:
    """Return (guidance, failure_reason, latency_ms)."""
    if not match.contexts:
        return None, "no_contexts", 0.0
    gateway = get_conversation_llm()
    started = time.perf_counter()
    try:
        guidance = await gateway.generate_troubleshoot_guidance(
            problem,
            _contexts_as_dicts(match.contexts),
            history=list(state.get("messages") or []),
            max_steps=max_steps,
        )
    except Exception:
        logger.exception(
            "RAG guidance generation failed provider=%s hits=%s",
            getattr(gateway, "provider_name", "unknown"),
            len(match.contexts),
        )
        return None, "generation_error", (time.perf_counter() - started) * 1000
    latency_ms = (time.perf_counter() - started) * 1000
    allowed = {c.source_id for c in match.contexts}
    reason = _validate_guidance(guidance, allowed_source_ids=allowed, max_steps=max_steps)
    if reason and reason.startswith("unknown_source_"):
        guidance = _repair_guidance_sources(guidance, match.contexts)
        reason = _validate_guidance(
            guidance, allowed_source_ids=allowed, max_steps=max_steps
        )
        if reason is None:
            logger.info(
                "RAG source_ids repaired provider=%s hits=%s",
                getattr(gateway, "provider_name", "unknown"),
                len(match.contexts),
            )
    return guidance, reason, latency_ms


async def _begin_troubleshoot(
    state: SupportGraphState,
    ts: dict,
    statuses: list[str],
    user_input: str,
    intent,
) -> dict:
    if _classify_deterministic(user_input) == "escalate":
        return _escalate(state, ts, statuses, intent, reason="requested")

    problem = _problem_text(state, intent)
    statuses.append("Looking into that…")
    match = get_runbook(problem)
    if match is None or (not match.contexts and not match.steps):
        ts["status"] = "skipped"
        logger.info("Troubleshoot skipped: no retrieval match")
        return {"troubleshoot": ts, "system_statuses": statuses}

    max_steps = _max_steps()
    statuses.append("I have a suggestion…")
    guidance, failure_reason, latency_ms = await _generate_guidance(
        problem, match, state, max_steps
    )

    provider_name = "unknown"
    try:
        provider_name = get_conversation_llm().provider_name
    except Exception:
        pass

    presented: list[dict[str, str]]
    reply: str
    generation_mode: str

    if guidance is not None and failure_reason is None:
        presented = [
            {
                "title": "",
                "instruction": step.instruction.strip(),
                "source_ids": list(step.source_ids),
            }
            for step in guidance.steps
        ]
        reply = _format_guidance_reply(
            intro=guidance.intro,
            steps=presented,
            follow_up=guidance.follow_up,
            problem=problem,
        )
        generation_mode = "rag"
        logger.info(
            "RAG guidance ok provider=%s hits=%s sources=%s steps=%s latency_ms=%.1f",
            provider_name,
            len(match.contexts),
            [c.source_id for c in match.contexts],
            len(presented),
            latency_ms,
        )
    else:
        fallback = _fallback_from_match(match, problem)
        if fallback is None:
            ts["status"] = "skipped"
            logger.info(
                "Troubleshoot skipped: rag_failed reason=%s provider=%s hits=%s",
                failure_reason or "unknown",
                provider_name,
                len(match.contexts),
            )
            return {"troubleshoot": ts, "system_statuses": statuses}
        presented, reply = fallback
        generation_mode = "extractive_fallback"
        logger.info(
            "RAG fallback reason=%s provider=%s hits=%s sources=%s latency_ms=%.1f",
            failure_reason or "unknown",
            provider_name,
            len(match.contexts),
            [c.source_id for c in match.contexts],
            latency_ms,
        )

    # Never leak handbook titles into the user-facing reply.
    if match.title and match.title in reply:
        reply = reply.replace(match.title, "this issue")

    ts.update(
        {
            "status": "guiding",
            "document_id": match.document_id,
            "runbook_title": match.title,
            "steps": presented,
            "step_index": len(presented),
            "attempts": [],
            "score": match.score,
            "problem": problem,
            "generation_mode": generation_mode,
            "source_citations": _source_citations(match.contexts),
            "rag_latency_ms": latency_ms,
            "rag_failure_reason": failure_reason,
        }
    )
    return {
        "troubleshoot": ts,
        "system_statuses": statuses,
        "assistant_reply": reply,
        "needs_clarification": True,
    }


async def _continue_guiding(
    state: SupportGraphState,
    ts: dict,
    statuses: list[str],
    user_input: str,
    intent,
) -> dict:
    steps: list[dict[str, str]] = list(ts.get("steps") or [])
    attempts: list[dict] = list(ts.get("attempts") or [])
    signal = await _classify_reply(user_input, state)

    def _record_attempts(outcome: str) -> None:
        for step in steps:
            attempts.append(
                {
                    "instruction": step.get("instruction") or step.get("title") or "step",
                    "title": step.get("title") or "",
                    "source_ids": list(step.get("source_ids") or []),
                    "outcome": outcome,
                }
            )
        ts["attempts"] = attempts

    if signal == "resolved":
        _record_attempts("resolved")
        ts["status"] = "resolved"
        reply = (
            "Great — I'm glad that resolved it! I won't open a ticket. "
            "If anything else comes up, just let me know."
        )
        logger.info(
            "Troubleshoot resolved document_id=%s steps=%s mode=%s",
            ts.get("document_id"),
            len(attempts),
            ts.get("generation_mode"),
        )
        return {
            "troubleshoot": ts,
            "system_statuses": statuses,
            "assistant_reply": reply,
            "needs_clarification": True,
            "troubleshoot_deflection": {
                "outcome": "resolved",
                "document_id": ts.get("document_id"),
                "steps_count": len(attempts),
            },
        }

    if signal == "escalate":
        _record_attempts("failed")
        return _escalate(state, ts, statuses, intent, reason="requested")

    if signal == "failed":
        _record_attempts("failed")
        # Immediate escalation — no second troubleshooting round.
        return _escalate(state, ts, statuses, intent, reason="exhausted")

    # Unclear — ask the user to confirm without advancing.
    reply = (
        "Did that step resolve the issue? Reply “yes” if it's fixed, "
        "or “no” and I'll open a ticket for you."
    )
    return {
        "troubleshoot": ts,
        "system_statuses": statuses,
        "assistant_reply": reply,
        "needs_clarification": True,
    }


async def troubleshoot_node(state: SupportGraphState) -> dict:
    # Existing ticket sessions skip KB guidance.
    if state.get("active_ticket_number"):
        return {}

    intent = state.get("structured_intent")
    ts = dict(state.get("troubleshoot") or {})
    statuses = list(state.get("system_statuses", []))
    user_input = state.get("user_input", "")

    # Continue guiding even when the conversation LLM is still slot-filling
    # (no ready CreateTicket intent yet).
    if ts.get("status") == "guiding":
        return await _continue_guiding(state, ts, statuses, user_input, intent)

    is_create_ticket = intent is not None and intent.intent == IntentName.CREATE_TICKET
    if not is_create_ticket and not state.get("is_support_issue"):
        return {}

    return await _begin_troubleshoot(state, ts, statuses, user_input, intent)
