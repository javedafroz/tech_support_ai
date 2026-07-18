"""KB retrieval for the troubleshoot node.

Wraps ``tech_support_knowledge`` retrieval into bounded grounded contexts for
classic RAG generation. Section extraction is retained only as a safe fallback
when LLM generation is unavailable.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)\s*$")
_STEP_HINT_RE = re.compile(r"\b(step|check|verify|try|confirm|restart|reset|reconnect)\b", re.I)
_ESCALATE_HINT_RE = re.compile(r"\b(ticket|escalat|contact support|raise a case)\b", re.I)
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "your",
        "you",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "not",
        "cannot",
        "cant",
        "able",
        "into",
        "onto",
        "about",
        "their",
        "them",
        "then",
        "than",
        "when",
        "what",
        "which",
        "while",
        "will",
        "would",
        "could",
        "should",
        "does",
        "did",
        "doing",
        "any",
        "all",
        "our",
        "out",
        "over",
        "under",
        "after",
        "before",
        "because",
        "being",
        "been",
        "user",
        "customer",
        "employee",
        "issue",
        "problem",
        "please",
        "help",
    }
)
_FALLBACK_BODY_MAX = 1200
_DEFAULT_MAX_CONTEXT_CHARS = 12000


@dataclass(frozen=True)
class RetrievedContext:
    """Stable grounded passage passed to the RAG generator."""

    source_id: str
    chunk_id: str
    document_id: str
    title: str
    section_title: str | None
    score: float
    body: str
    chunk_index: int = 0


@dataclass
class RunbookMatch:
    document_id: str
    title: str
    score: float
    contexts: list[RetrievedContext] = field(default_factory=list)
    # Fallback extractive steps when RAG generation is unavailable.
    steps: list[dict[str, str]] = field(default_factory=list)


class RunbookRetriever(Protocol):
    def get_runbook(self, problem: str) -> RunbookMatch | None: ...


def _split_sections(markdown: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []
    for line in markdown.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            if current_title is not None:
                sections.append((current_title, current_body))
            current_title = heading.group(1).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_title is not None:
        sections.append((current_title, current_body))
    return sections


def _extract_steps(markdown: str, max_steps: int) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    for title, body_lines in _split_sections(markdown):
        if not _STEP_HINT_RE.search(title):
            continue
        if _ESCALATE_HINT_RE.search(title):
            continue
        body = "\n".join(body_lines).strip()
        steps.append({"title": title, "instruction": body or title})
        if len(steps) >= max_steps:
            break
    return steps


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def _score_section(problem: str, title: str, body: str) -> float:
    problem_tokens = _tokens(problem)
    if not problem_tokens:
        return 0.0
    title_tokens = _tokens(title)
    body_tokens = _tokens(body)
    title_hits = len(problem_tokens & title_tokens)
    body_hits = len(problem_tokens & body_tokens)
    return (3.0 * title_hits) + (1.0 * body_hits)


def _best_section_step(markdown: str, problem: str) -> dict[str, str] | None:
    sections = _split_sections(markdown)
    if not sections:
        return None

    scored: list[tuple[float, str, str]] = []
    for title, body_lines in sections:
        if _ESCALATE_HINT_RE.search(title):
            continue
        body = "\n".join(body_lines).strip()
        score = _score_section(problem, title, body)
        scored.append((score, title, body))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    _best_score, best_title, best_body = scored[0]
    return {"title": best_title, "instruction": best_body or best_title}


def _truncate(text: str, max_chars: int = _FALLBACK_BODY_MAX) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _build_contexts(
    doc_hits: list,
    *,
    max_context_chars: int,
) -> list[RetrievedContext]:
    # Prefer higher-scoring chunks when applying the character budget, then
    # present the selected set in handbook order for coherent prompting.
    ranked = sorted(doc_hits, key=lambda h: float(h.score), reverse=True)
    selected: list = []
    used = 0
    for hit in ranked:
        body = (hit.body or "").strip()
        if not body:
            continue
        remaining = max_context_chars - used
        if remaining <= 0:
            break
        if len(body) > remaining:
            body = _truncate(body, max_chars=remaining)
        selected.append((hit, body))
        used += len(body)

    selected.sort(key=lambda item: int(getattr(item[0], "chunk_index", 0) or 0))
    contexts: list[RetrievedContext] = []
    for idx, (hit, body) in enumerate(selected, start=1):
        contexts.append(
            RetrievedContext(
                source_id=f"src{idx}",
                chunk_id=str(getattr(hit, "chunk_id", "") or f"{hit.document_id}:{hit.chunk_index}"),
                document_id=str(hit.document_id),
                title=str(hit.title),
                section_title=getattr(hit, "section_title", None),
                score=float(hit.score),
                body=body,
                chunk_index=int(getattr(hit, "chunk_index", 0) or 0),
            )
        )
    return contexts


def _fallback_steps(
    markdown: str,
    problem: str,
    *,
    max_steps: int,
    top_title: str | None,
    top_body: str,
) -> list[dict[str, str]]:
    """Extractive fallback steps when RAG generation is unavailable.

    The troubleshoot node presents at most one of these when falling back.
    """
    steps = _extract_steps(markdown, max_steps)
    if steps:
        return steps
    best = _best_section_step(markdown, problem)
    if best is not None:
        return [best]
    return [
        {
            "title": top_title or "Guidance",
            "instruction": _truncate(top_body),
        }
    ]


def _match_from_hits(
    hits: list,
    max_steps: int,
    problem: str = "",
    *,
    max_context_chars: int = _DEFAULT_MAX_CONTEXT_CHARS,
) -> RunbookMatch | None:
    if not hits:
        return None
    top = hits[0]
    document_id = str(top.document_id)
    doc_hits = [h for h in hits if str(h.document_id) == document_id]
    doc_hits.sort(key=lambda h: h.chunk_index)

    contexts = _build_contexts(doc_hits, max_context_chars=max_context_chars)
    if not contexts:
        return None

    markdown = "\n\n".join(ctx.body for ctx in contexts)
    steps = _fallback_steps(
        markdown,
        problem,
        max_steps=max_steps,
        top_title=top.section_title or top.title,
        top_body=top.body or "",
    )
    return RunbookMatch(
        document_id=document_id,
        title=top.title,
        score=float(top.score),
        contexts=contexts,
        steps=steps,
    )


class _DefaultRetriever:
    def get_runbook(self, problem: str) -> RunbookMatch | None:
        from tech_support_knowledge.embeddings import get_embedder
        from tech_support_knowledge.store import get_knowledge_settings, get_knowledge_store

        settings = get_knowledge_settings()
        if not settings.kb_rag_enabled:
            return None
        embedder = get_embedder(settings)
        store = get_knowledge_store()
        embedding = embedder.embed_query(problem)
        # Over-fetch so the winning document still has several candidate chunks
        # after filtering; contexts are then score-budgeted and ordered.
        top_k = max(int(settings.retrieval_top_k), 5) * 3
        hits = store.retrieve(
            embedding,
            top_k=top_k,
            min_score=settings.min_score,
        )
        max_chars = getattr(settings, "rag_max_context_chars", _DEFAULT_MAX_CONTEXT_CHARS)
        return _match_from_hits(
            hits,
            settings.max_troubleshoot_steps,
            problem=problem,
            max_context_chars=int(max_chars),
        )


_override: RunbookRetriever | None = None


def configure_runbook_retriever(retriever: RunbookRetriever | None) -> None:
    """Install (or clear) a retriever override, primarily for tests."""
    global _override
    _override = retriever


def get_runbook(problem: str) -> RunbookMatch | None:
    retriever: RunbookRetriever = _override or _DefaultRetriever()
    try:
        return retriever.get_runbook(problem)
    except Exception:
        logger.exception("KB runbook retrieval failed; proceeding without troubleshooting")
        return None
