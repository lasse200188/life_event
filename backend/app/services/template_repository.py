from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.domain.workflow_validator import WorkflowValidationError
from app.domain.workflow_validator import validate_graph
from app.services.errors import ApiError

_TEMPLATE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+/v[0-9]+$")


class TemplateRepository:
    def __init__(self, workflows_root: Path | None = None) -> None:
        if workflows_root is None:
            workflows_root = Path(__file__).resolve().parents[3] / "workflows"
        self.workflows_root = workflows_root

    def derive_template_key(self, template_id: str, version: int) -> str:
        return f"{template_id}/v{version}"

    def parse_template_key(self, template_key: str) -> tuple[str, int]:
        if not _TEMPLATE_KEY_PATTERN.fullmatch(template_key):
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_key}' not found",
            )
        event, version = template_key.split("/", maxsplit=1)
        version_value = int(version[1:])
        return event, version_value

    def load(
        self, template_key: str, *, expected_compiled_hash: str | None = None
    ) -> dict[str, Any]:
        template_id, version = self.parse_template_key(template_key)
        return self.load_by_id_version(
            template_id,
            version,
            expected_compiled_hash=expected_compiled_hash,
        )

    def load_by_id_version(
        self,
        template_id: str,
        version: int,
        *,
        expected_compiled_hash: str | None = None,
    ) -> dict[str, Any]:
        version_key = f"v{version}"
        template_key = self.derive_template_key(template_id, version)
        template_path = (
            self.workflows_root / template_id / version_key / "compiled.json"
        )
        if not template_path.exists():
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_key}' not found",
            )

        raw = template_path.read_bytes()
        compiled_hash = hashlib.sha256(raw).hexdigest()
        if (
            isinstance(expected_compiled_hash, str)
            and expected_compiled_hash
            and compiled_hash != expected_compiled_hash
        ):
            raise ApiError(
                status_code=409,
                code="TEMPLATE_INTEGRITY_ERROR",
                message=(
                    "Template integrity check failed for "
                    f"'{template_key}': compiled hash mismatch"
                ),
            )

        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message="Template root must be an object",
            )

        if (
            payload.get("template_id") != template_id
            or payload.get("version") != version
        ):
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message=(
                    "Template file does not match requested identity "
                    f"'{template_key}'"
                ),
            )

        try:
            validate_graph(payload)
        except WorkflowValidationError as exc:
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message=str(exc),
            ) from exc
        return payload

    def compiled_hash(self, template_id: str, version: int) -> str:
        version_key = f"v{version}"
        template_path = (
            self.workflows_root / template_id / version_key / "compiled.json"
        )
        if not template_path.exists():
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=(
                    f"Template '{self.derive_template_key(template_id, version)}' not found"
                ),
            )
        return hashlib.sha256(template_path.read_bytes()).hexdigest()
