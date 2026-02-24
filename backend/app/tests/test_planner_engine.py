from __future__ import annotations

import json

import pytest

from app.planner.engine import generate_plan
from app.planner.errors import PlannerDependencyError, PlannerInputError


def test_generate_plan_soft_prunes_inactive_dependencies_and_is_deterministic() -> None:
    workflow = {
        "template_id": "demo",
        "event_date_key": "birth_date",
        "graph": {
            "nodes": ["t_a", "t_b", "t_c", "t_d"],
            "edges": [
                {"from": "t_a", "to": "t_b"},
                {"from": "t_c", "to": "t_b"},
            ],
        },
        "tasks": {
            "t_a": {
                "title": "A",
                "eligibility": {"all": []},
                "deadline": {"type": "relative_days", "offset_days": 7},
            },
            "t_b": {
                "title": "B",
                "eligibility": {"fact": "employed", "op": "=", "value": True},
                "deadline": {"type": "relative_days", "offset_days": 14},
            },
            "t_c": {
                "title": "C",
                "eligibility": {"fact": "include_c", "op": "=", "value": True},
                "deadline": {"type": "relative_days", "offset_days": 3},
            },
            "t_d": {
                "title": "D",
                "eligibility": {"all": []},
                "deadline": {"type": "relative_days", "offset_days": 2},
            },
        },
    }
    user_input = {"birth_date": "2026-04-01", "employed": True, "include_c": False}

    plan1 = generate_plan(workflow, user_input)
    plan2 = generate_plan(workflow, user_input)

    assert plan1 == plan2
    assert json.dumps(plan1, sort_keys=True) == json.dumps(plan2, sort_keys=True)
    assert plan1["tasks"] == [
        {
            "id": "t_a",
            "title": "A",
            "relative_days": 7,
            "deadline": "2026-04-08",
            "depends_on": [],
            "meta": {},
        },
        {
            "id": "t_b",
            "title": "B",
            "relative_days": 14,
            "deadline": "2026-04-15",
            "depends_on": ["t_a"],
            "meta": {},
        },
        {
            "id": "t_d",
            "title": "D",
            "relative_days": 2,
            "deadline": "2026-04-03",
            "depends_on": [],
            "meta": {},
        },
    ]


def test_generate_plan_unknown_workflow_dependency_raises() -> None:
    workflow = {
        "template_id": "demo",
        "event_date_key": "birth_date",
        "graph": {
            "nodes": ["t_a", "t_b"],
            "edges": [{"from": "t_unknown", "to": "t_b"}],
        },
        "tasks": {
            "t_a": {
                "title": "A",
                "eligibility": {"all": []},
                "deadline": {"type": "relative_days", "offset_days": 1},
            },
            "t_b": {
                "title": "B",
                "eligibility": {"all": []},
                "deadline": {"type": "relative_days", "offset_days": 1},
            },
        },
    }

    with pytest.raises(PlannerDependencyError, match="unknown workflow task id"):
        generate_plan(workflow, {"birth_date": "2026-04-01"})


def test_generate_plan_invalid_deadline_type_raises() -> None:
    workflow = {
        "template_id": "demo",
        "event_date_key": "birth_date",
        "graph": {"nodes": ["t_a"], "edges": []},
        "tasks": {
            "t_a": {
                "title": "A",
                "eligibility": {"all": []},
                "deadline": {"type": "fixed_date", "offset_days": 1},
            }
        },
    }

    with pytest.raises(PlannerInputError, match="must be 'relative_days'"):
        generate_plan(workflow, {"birth_date": "2026-04-01"})


def test_generate_plan_invalid_workflow_shape_raises() -> None:
    with pytest.raises(PlannerInputError, match="workflow.template_id"):
        generate_plan({"tasks": {}, "graph": {}, "event_date_key": "birth_date"}, {})
