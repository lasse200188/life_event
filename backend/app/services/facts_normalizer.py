from __future__ import annotations

from typing import Any

_CHILD_INSURANCE_VALUES = {"unknown", "gkv", "pkv"}


def normalize_facts(template_key: str, facts: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(facts)

    if template_key.startswith("birth_de/"):
        normalized = _normalize_birth_facts(normalized)

    return normalized


def migrate_facts_to_latest_schema(
    template: dict[str, Any],
    facts: dict[str, Any],
    *,
    source_schema_version: int | None,
) -> tuple[dict[str, Any], int, int]:
    template_id = template.get("template_id")
    target_schema_version = _read_int(template.get("fact_schema_version"), default=1)
    current_version = source_schema_version or target_schema_version
    migrated = dict(facts)

    while current_version < target_schema_version:
        next_version = current_version + 1
        migrated = _apply_migration_step(
            template_id=template_id,
            from_version=current_version,
            to_version=next_version,
            facts=migrated,
        )
        current_version = next_version

    return (
        migrated,
        source_schema_version or target_schema_version,
        target_schema_version,
    )


def _apply_migration_step(
    *,
    template_id: Any,
    from_version: int,
    to_version: int,
    facts: dict[str, Any],
) -> dict[str, Any]:
    if template_id == "birth_de" and from_version == 1 and to_version == 2:
        migrated = dict(facts)
        if migrated.get("child_insurance_kind") not in {"gkv", "pkv", "unknown"}:
            migrated["child_insurance_kind"] = "unknown"
        return migrated
    return dict(facts)


def _read_int(value: Any, *, default: int) -> int:
    if isinstance(value, int):
        return value
    return default


def _normalize_birth_facts(facts: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(facts)

    current = normalized.get("child_insurance_kind")
    if current in {"gkv", "pkv"}:
        return normalized

    public_insurance = normalized.get("public_insurance")
    private_insurance = normalized.get("private_insurance")

    derived = "unknown"
    if public_insurance is True and private_insurance is False:
        derived = "gkv"
    elif public_insurance is False and private_insurance is True:
        derived = "pkv"

    if current not in _CHILD_INSURANCE_VALUES or current == "unknown":
        normalized["child_insurance_kind"] = derived

    return normalized
