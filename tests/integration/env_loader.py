"""Load project .env into os.environ for integration tests (Zammad uses os.environ directly)."""

from __future__ import annotations

import os
from pathlib import Path

# Always prefer .env for these keys — they control local test UX, not secrets.
_INTEGRATION_OVERRIDE_KEYS = frozenset(
    {
        "INTEGRATION_HEADLESS",
        "INTEGRATION_SLOW_MO",
        "INTEGRATION_UI_PAUSE_MS",
        "LIVE_API_PORT",
        "LIVE_WEB_PORT",
        "USER_SIM_MODEL",
        "USER_SIM_TEMPERATURE",
        "INTEGRATION_MAX_TURNS",
    }
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_env_value(raw: str) -> str:
    """Strip quotes and trailing inline comments from a .env value."""
    value = raw.strip()
    if "#" in value:
        value = value.split("#", 1)[0].strip()
    return value.strip('"').strip("'")


def integration_env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    parsed = parse_env_value(str(raw)).lower()
    if parsed in {"1", "true", "yes", "on"}:
        return True
    if parsed in {"0", "false", "no", "off"}:
        return False
    return default


def load_project_env() -> None:
    env_path = project_root() / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = parse_env_value(value)
        if not key:
            continue
        if key not in os.environ or key in _INTEGRATION_OVERRIDE_KEYS:
            os.environ[key] = value


def require_live_credentials() -> tuple[str, str, str, str]:
    load_project_env()

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    zammad_url = os.environ.get("ZAMMAD_BASE_URL", "").strip()
    zammad_token = os.environ.get("ZAMMAD_API_TOKEN", "").strip()
    test_email = os.environ.get("ZAMMAD_TEST_EMAIL", "").strip()

    missing = [
        name
        for name, value in [
            ("OPENAI_API_KEY", openai_key),
            ("ZAMMAD_BASE_URL", zammad_url),
            ("ZAMMAD_API_TOKEN", zammad_token),
            ("ZAMMAD_TEST_EMAIL", test_email),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Live integration tests require these variables in .env: "
            + ", ".join(missing)
        )

    return openai_key, zammad_url, zammad_token, test_email
