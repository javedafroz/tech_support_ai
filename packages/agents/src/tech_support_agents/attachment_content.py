"""Load attachment bytes for LLM vision / text context."""

from __future__ import annotations

import base64

from tech_support_storage import get_object_storage

IMAGE_MIME_PREFIX = "image/"
TEXT_MIME_TYPES = {"text/plain", "text/csv", "application/json"}


def attachment_has_images(attachments: list[dict]) -> bool:
    return any(
        str(item.get("mime_type", "")).lower().startswith(IMAGE_MIME_PREFIX)
        for item in attachments
    )


def build_attachment_prompt_context(
    attachments: list[dict],
    *,
    llm_provider: str = "openai",
) -> tuple[list[dict], str]:
    """Build vision blocks and a text summary for the system context."""
    if not attachments:
        return [], ""

    storage = get_object_storage()
    vision_blocks: list[dict] = []
    summary_lines: list[str] = []

    for item in attachments:
        filename = str(item.get("filename") or "attachment")
        mime_type = str(item.get("mime_type") or "application/octet-stream").lower()
        storage_key = item.get("storage_key")
        if not storage_key:
            summary_lines.append(f"- {filename} ({mime_type})")
            continue

        try:
            raw = storage.get_object(storage_key)
        except FileNotFoundError:
            summary_lines.append(f"- {filename} ({mime_type}) — file not found in storage")
            continue

        if mime_type.startswith(IMAGE_MIME_PREFIX):
            encoded = base64.b64encode(raw).decode("ascii")
            vision_blocks.append(_image_block_for_provider(mime_type, encoded, llm_provider))
            summary_lines.append(
                f"- Image `{filename}` is attached below — read any visible error codes, "
                "stop codes, and on-screen messages from it."
            )
            continue

        if mime_type in TEXT_MIME_TYPES:
            excerpt = raw.decode("utf-8", errors="replace").strip()[:4000]
            summary_lines.append(f"- Text file `{filename}`:\n{excerpt}")
            continue

        summary_lines.append(f"- File `{filename}` ({mime_type}) — metadata only in this turn")

    return vision_blocks, "\n".join(summary_lines)


def _image_block_for_provider(mime_type: str, encoded: str, llm_provider: str) -> dict:
    if llm_provider == "anthropic":
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": encoded,
            },
        }
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
    }


def build_user_message_content(
    user_text: str,
    *,
    vision_blocks: list[dict],
    llm_provider: str = "openai",
) -> str | list[dict]:
    text = user_text.strip() or "Please review the attached file(s)."
    if not vision_blocks:
        return text

    parts: list[dict] = [{"type": "text", "text": text}]
    parts.extend(vision_blocks)
    return parts
