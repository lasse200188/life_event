from __future__ import annotations

import pytest

from app.planner.errors import PlannerRuleError
from app.planner.rules import eval_rule, is_task_active


def test_is_task_active_defaults_to_true_when_eligibility_missing() -> None:
    task = {"title": "X"}
    assert is_task_active(task, {}) is True


def test_eval_rule_all_any_not() -> None:
    rule = {
        "all": [
            {"fact": "country", "op": "=", "value": "DE"},
            {
                "any": [
                    {"fact": "employment", "op": "=", "value": "employed"},
                    {"not": {"fact": "student", "op": "=", "value": True}},
                ]
            },
        ]
    }

    assert eval_rule(rule, {"country": "DE", "employment": "employed"}) is True
    assert eval_rule(rule, {"country": "DE", "student": False}) is True
    assert eval_rule(rule, {"country": "DE", "student": True}) is False


def test_eval_rule_unknown_field_is_false_for_equality() -> None:
    rule = {"fact": "employment", "op": "=", "value": "employed"}
    assert eval_rule(rule, {}) is False


def test_explicit_null_eligibility_raises() -> None:
    task = {"eligibility": None}
    with pytest.raises(PlannerRuleError, match="cannot be null"):
        is_task_active(task, {})


def test_unsupported_operator_raises() -> None:
    with pytest.raises(PlannerRuleError, match="unsupported predicate op"):
        eval_rule({"fact": "x", "op": "contains", "value": "a"}, {"x": "abc"})
