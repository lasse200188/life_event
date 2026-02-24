from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.workflow_validator import WorkflowValidationError, validate_graph

pytestmark = pytest.mark.workflow

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = ROOT / "workflows" / "birth_de" / "v1" / "compiled.json"


def test_template_graph_is_valid() -> None:
    with TEMPLATE_PATH.open("r", encoding="utf-8") as f:
        template = json.load(f)

    validate_graph(template)


def test_cycle_detection_raises() -> None:
    cyclic_template = {
        "graph": {
            "nodes": ["t_a", "t_b"],
            "edges": [
                {"from": "t_a", "to": "t_b"},
                {"from": "t_b", "to": "t_a"},
            ],
        },
        "tasks": {
            "t_a": {"eligibility": {"all": []}},
            "t_b": {"eligibility": {"all": []}},
        },
    }

    with pytest.raises(WorkflowValidationError, match="Cycle detected"):
        validate_graph(cyclic_template)


def test_edge_referencing_unknown_node_raises() -> None:
    template = {
        "graph": {
            "nodes": ["t_a"],
            "edges": [{"from": "t_a", "to": "t_missing"}],
        },
        "tasks": {
            "t_a": {"eligibility": {"all": []}},
        },
    }

    with pytest.raises(WorkflowValidationError, match="unknown node"):
        validate_graph(template)


def test_node_missing_in_tasks_raises() -> None:
    template = {
        "graph": {"nodes": ["t_a", "t_b"], "edges": []},
        "tasks": {
            "t_a": {"eligibility": {"all": []}},
        },
    }

    with pytest.raises(WorkflowValidationError, match="missing in tasks"):
        validate_graph(template)


def test_duplicate_node_ids_raises() -> None:
    template = {
        "graph": {"nodes": ["t_a", "t_a"], "edges": []},
        "tasks": {
            "t_a": {"eligibility": {"all": []}},
        },
    }

    with pytest.raises(WorkflowValidationError, match="Duplicate node ids"):
        validate_graph(template)
