"""Network helpers for ticketing provider connectivity."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse


def is_running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def resolve_zammad_base_url(base_url: str) -> str:
    """Rewrite localhost URLs when the API runs inside Docker.

    Docker Compose sets ``localhost`` to the API container itself. Zammad on the
    host (or another compose stack) is reachable via ``host.docker.internal``.
    """
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return normalized
    if not is_running_in_docker():
        return normalized

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    netloc = f"host.docker.internal:{port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    ).rstrip("/")
