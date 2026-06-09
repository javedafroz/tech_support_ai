from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def normalize_customer_email(raw: str) -> str:
    """Strip Zammad query prefixes the LLM sometimes copies into customer_email."""
    value = raw.strip()
    prefixes = ("guess:email:", "email:")
    while True:
        lower = value.lower()
        stripped = False
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = value[len(prefix) :].strip()
                stripped = True
                break
        if not stripped:
            break
    return value


class FieldMappingConfig(BaseModel):
    version: str = "1.0"
    priorities: dict[str, str] = Field(default_factory=dict)
    groups: dict[str, str] = Field(default_factory=dict)
    categories: dict[str, str] = Field(default_factory=dict)
    default_group: str = "Software Support"
    default_priority: str = "2 normal"
    customer_lookup: dict[str, str] = Field(
        default_factory=lambda: {"customer_id_pattern": "guess:{email}"}
    )

    def resolve_group(self, category_key: str | None) -> str:
        if category_key and category_key in self.groups:
            return self.groups[category_key]
        if category_key and category_key in self.categories:
            cat = self.categories[category_key]
            for key, group in self.groups.items():
                if self.categories.get(key) == cat:
                    return group
        return self.default_group

    def resolve_priority(self, suggested: str | None, impact: str | None = None) -> str:
        if suggested:
            normalized = suggested.strip().lower()
            for _key, label in self.priorities.items():
                if normalized in label.lower() or normalized == _key:
                    return label
            if suggested in self.priorities.values():
                return suggested
        if impact:
            impact_lower = impact.lower()
            if "outage" in impact_lower or "multiple" in impact_lower:
                return self.priorities.get("high", self.default_priority)
            if "blocked" in impact_lower:
                return self.priorities.get("normal", self.default_priority)
        return self.default_priority

    def customer_id_for_email(self, email: str) -> str:
        normalized = normalize_customer_email(email)
        pattern = self.customer_lookup.get("customer_id_pattern", "guess:{email}")
        if pattern == "guess:email":
            # Legacy config value — real Zammad expects guess:{email}, not guess:email:{email}.
            return f"guess:{normalized}"
        if "{email}" in pattern:
            return pattern.replace("{email}", normalized)
        return f"guess:{normalized}"


def normalize_customer_id(customer_id: str) -> str:
    """Ensure customer_id uses Zammad's guess:{plain_email} form."""
    value = customer_id.strip()
    if value.lower().startswith("guess:"):
        suffix = normalize_customer_email(value[6:])
        return f"guess:{suffix}"
    return customer_id


def _config_root() -> Path:
    return Path(__file__).resolve().parents[4] / "config"


def resolve_mapping_path(provider: str = "zammad") -> Path:
    """Resolve provider-scoped mapping file with legacy fallback."""
    root = _config_root()
    provider_path = root / "providers" / provider / "mapping.yaml"
    if provider_path.exists():
        return provider_path
    legacy_path = root / "zammad-field-mapping.yaml"
    if legacy_path.exists():
        return legacy_path
    return provider_path


def load_field_mapping(path: Path | None = None, *, provider: str = "zammad") -> FieldMappingConfig:
    resolved = path or resolve_mapping_path(provider)
    if not resolved.exists():
        return FieldMappingConfig()
    with resolved.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}
    return FieldMappingConfig.model_validate(raw)
