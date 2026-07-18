from __future__ import annotations

from uuid import uuid4

from tech_support_knowledge.chunking import PAGE_BREAK_MARKER, chunk_markdown
from tech_support_knowledge.models import ChunkRecord
from tech_support_knowledge.store import MemoryKnowledgeStore


def test_chunk_by_page_default() -> None:
    text = f"""# Cover

Page one content.
{PAGE_BREAK_MARKER}
## Details

Page two content.
{PAGE_BREAK_MARKER}
More on page three.
"""
    chunks = chunk_markdown(text)
    assert len(chunks) == 3
    assert [c.page for c in chunks] == [1, 2, 3]
    assert chunks[0].section_title == "Cover"
    assert chunks[2].section_title == "Page 3"  # no heading on that page


def test_chunk_by_page_windows_oversized_page() -> None:
    big_page = "word " * 500  # ~2500 chars
    text = f"# A\n\nsmall{PAGE_BREAK_MARKER}{big_page}"
    chunks = chunk_markdown(text, max_chars=800, overlap_chars=50)
    pages = {c.page for c in chunks}
    assert pages == {1, 2}
    # Page 2 got split into multiple windowed chunks
    assert sum(1 for c in chunks if c.page == 2) > 1


def test_chunk_falls_back_to_headings_without_page_marker() -> None:
    text = "# VPN\n\nIntro.\n\n## Step 1\n\nDo a thing."
    chunks = chunk_markdown(text)  # strategy=page by default, but no marker present
    assert all(c.page is None for c in chunks)
    assert any(c.section_title in {"VPN", "Step 1"} for c in chunks)


def test_chunk_markdown_by_headings() -> None:
    text = """# VPN

Intro text.

## Step 1

Quit AnyConnect.

## Step 2

Clear the cache.
"""
    chunks = chunk_markdown(text, max_chars=500)
    assert len(chunks) >= 2
    titles = {c.section_title for c in chunks}
    assert "VPN" in titles or "Step 1" in titles


def test_memory_store_retrieve_by_similarity() -> None:
    store = MemoryKnowledgeStore()
    doc_id = uuid4()
    target = ChunkRecord(
        chunk_id=uuid4(),
        document_id=doc_id,
        chunk_index=0,
        title="VPN guide",
        section_title="Step 1",
        body="Quit AnyConnect and clear cache",
        embedding=[1.0, 0.0, 0.0],
        embedding_model="test",
        status="published",
    )
    other = ChunkRecord(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        title="Email guide",
        section_title=None,
        body="Outlook password prompt",
        embedding=[0.0, 1.0, 0.0],
        embedding_model="test",
        status="published",
    )
    store.upsert_chunks([target, other])
    hits = store.retrieve([0.99, 0.01, 0.0], top_k=1, min_score=0.5)
    assert len(hits) == 1
    assert hits[0].title == "VPN guide"


def test_handbook_object_key() -> None:
    from tech_support_knowledge.handbook_storage import handbook_object_key

    key = handbook_object_key(
        org_id="default",
        document_id="abc",
        version=2,
        filename="../secret/runbook.pdf",
    )
    assert key == "handbooks/default/abc/v2/runbook.pdf"
