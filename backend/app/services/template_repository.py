from __future__ import annotations

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

    def load(self, template_key: str) -> dict[str, Any]:
        if not _TEMPLATE_KEY_PATTERN.fullmatch(template_key):
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_key}' not found",
            )

        event, version = template_key.split("/", maxsplit=1)
        template_path = self.workflows_root / event / version / "compiled.json"
        if not template_path.exists():
            raise ApiError(
                status_code=404,
                code="TEMPLATE_NOT_FOUND",
                message=f"Template '{template_key}' not found",
            )

        with template_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message="Template root must be an object",
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
