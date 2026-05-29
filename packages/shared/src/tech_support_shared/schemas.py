"""Path helpers for JSON Schema artifacts."""

from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"


def schema_path(name: str) -> Path:
    return SCHEMAS_DIR / name
