from __future__ import annotations

import base64

from tech_support_storage import get_object_storage


def encode_attachments_for_zammad(specs: list[dict]) -> list[dict]:
    """Load bytes from object storage and return Zammad article attachment payloads."""
    if not specs:
        return []

    storage = get_object_storage()
    encoded: list[dict] = []
    for spec in specs:
        raw = storage.get_object(spec["storage_key"])
        encoded.append(
            {
                "filename": spec["filename"],
                "data": base64.b64encode(raw).decode("ascii"),
                "mime-type": spec["mime_type"],
            }
        )
    return encoded
