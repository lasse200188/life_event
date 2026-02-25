from __future__ import annotations

from typing import Any

_CHILD_INSURANCE_VALUES = {"unknown", "gkv", "pkv"}


def normalize_facts(template_key: str, facts: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(facts)

    if template_key.startswith("birth_de/"):
        normalized = _normalize_birth_facts(normalized)

    return normalized


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
