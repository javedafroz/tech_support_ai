from tech_support_storage import get_object_storage, reset_object_storage_cache
from tech_support_ticketing.attachments import encode_attachments_for_zammad


def test_encode_attachments_for_zammad(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    reset_object_storage_cache()

    storage = get_object_storage()
    storage.put_object(key="sessions/test/file.txt", data=b"hello", content_type="text/plain")

    encoded = encode_attachments_for_zammad(
        [{"filename": "file.txt", "mime_type": "text/plain", "storage_key": "sessions/test/file.txt"}]
    )
    assert encoded[0]["filename"] == "file.txt"
    assert encoded[0]["mime-type"] == "text/plain"
    assert encoded[0]["data"] == "aGVsbG8="

    get_object_storage.cache_clear()