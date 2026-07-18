import base64

import pytest
from langchain_core.messages import HumanMessage
from tech_support_agents.attachment_content import (
    attachment_has_images,
    build_attachment_prompt_context,
    build_user_message_content,
)
from tech_support_storage import reset_object_storage_cache


@pytest.fixture(autouse=True)
def memory_storage(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    reset_object_storage_cache()
    yield
    reset_object_storage_cache()


def test_attachment_has_images():
    assert attachment_has_images([{"mime_type": "image/png"}])
    assert not attachment_has_images([{"mime_type": "application/pdf"}])


def test_build_user_message_content_with_vision_blocks():
    content = build_user_message_content(
        "Blue screen on laptop",
        vision_blocks=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}],
    )
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"


def test_build_attachment_prompt_context_loads_image_from_storage(monkeypatch):
    from tech_support_storage import get_object_storage

    storage = get_object_storage()
    storage.put_object(
        key="sessions/test/a/blue.png",
        data=b"fake-png-bytes",
        content_type="image/png",
    )

    vision_blocks, summary = build_attachment_prompt_context(
        [
            {
                "filename": "blue.png",
                "mime_type": "image/png",
                "storage_key": "sessions/test/a/blue.png",
            }
        ]
    )

    assert len(vision_blocks) == 1
    assert "blue.png" in summary
    url = vision_blocks[0]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == b"fake-png-bytes"


def test_build_user_message_content_anthropic_image_block():
    from tech_support_storage import get_object_storage

    storage = get_object_storage()
    storage.put_object(
        key="sessions/test/c/blue.png",
        data=b"\x89PNG",
        content_type="image/png",
    )
    vision_blocks, _ = build_attachment_prompt_context(
        [
            {
                "filename": "blue.png",
                "mime_type": "image/png",
                "storage_key": "sessions/test/c/blue.png",
            }
        ],
        llm_provider="anthropic",
    )
    assert vision_blocks[0]["type"] == "image"
    assert vision_blocks[0]["source"]["media_type"] == "image/png"


def test_build_prompt_messages_includes_image_blocks(monkeypatch):
    from uuid import uuid4

    from tech_support_storage import get_object_storage
    from tech_support_agents.openai_llm import _build_prompt_messages

    storage = get_object_storage()
    storage.put_object(
        key="sessions/test/b/blue.png",
        data=b"\x89PNG",
        content_type="image/png",
    )

    messages = _build_prompt_messages(
        "I am getting blue screen on my laptop",
        session_id=uuid4(),
        user_id="user@company.com",
        user_email="user@company.com",
        message_count=0,
        history=[],
        pending_attachments=[
            {
                "filename": "blue.png",
                "mime_type": "image/png",
                "storage_key": "sessions/test/b/blue.png",
            }
        ],
    )

    last = messages[-1]
    assert isinstance(last, HumanMessage)
    assert isinstance(last.content, list)
    assert last.content[0]["type"] == "text"
    assert last.content[1]["type"] == "image_url"
