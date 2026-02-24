from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from domain.workflow_validator import WorkflowValidationError, validate_graph
except ModuleNotFoundError:
    from app.domain.workflow_validator import WorkflowValidationError, validate_graph


@dataclass(frozen=True)
class ValidationIssue:
    file: Path
    message: str


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        raise WorkflowValidationError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(payload, dict):
        raise WorkflowValidationError(f"Template root must be an object in {path}")
    return payload


def _basic_template_checks(template: Dict[str, Any], path: Path) -> None:
    required = ["template_id", "version", "graph", "tasks", "event_date_key"]
    missing = [key for key in required if key not in template]
    if missing:
        raise WorkflowValidationError(f"Missing required keys {missing} in {path}")

    template_id = template.get("template_id")
    if not isinstance(template_id, str) or not template_id:
        raise WorkflowValidationError(f"template_id must be non-empty string in {path}")

    version = template.get("version")
    if not isinstance(version, int):
        raise WorkflowValidationError(f"version must be int in {path}")

    graph = template.get("graph")
    if not isinstance(graph, dict):
        raise WorkflowValidationError(f"graph must be object in {path}")
    if "nodes" not in graph or "edges" not in graph:
        raise WorkflowValidationError(f"graph must contain nodes and edges in {path}")

    tasks = template.get("tasks")
    if not isinstance(tasks, dict):
        raise WorkflowValidationError(f"tasks must be object in {path}")

    nodes = graph.get("nodes", [])
    if isinstance(nodes, list) and len(nodes) != len(set(nodes)):
        raise WorkflowValidationError(f"duplicate node ids in graph.nodes in {path}")


def validate_one_compiled_json(path: Path) -> None:
    template = _load_json(path)
    _basic_template_checks(template, path)
    validate_graph(template)


def validate_all_workflows(root: Path) -> Tuple[int, List[ValidationIssue]]:
    compiled_paths = sorted(root.rglob("compiled.json"))
    if not compiled_paths:
        return 1, [ValidationIssue(file=root, message="No compiled.json files found")]

    issues: List[ValidationIssue] = []
    for compiled_path in compiled_paths:
        try:
            validate_one_compiled_json(compiled_path)
        except Exception as e:  # noqa: BLE001
            issues.append(ValidationIssue(file=compiled_path, message=str(e)))

    return len(issues), issues


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate all workflow compiled.json files."
    )
    parser.add_argument(
        "root", type=str, help="Path to workflows root (e.g. ../workflows)"
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    count, issues = validate_all_workflows(root)
    if count == 0:
        print(f"OK: all workflows valid under {root}")
        return 0

    print(f"FAILED: {count} workflow template(s) invalid under {root}\n")
    for issue in issues:
        print(f"- {issue.file}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
