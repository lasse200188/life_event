from __future__ import annotations

from typing import Any, Callable

from app.planner.errors import PlannerRuleError


def is_task_active(task: dict[str, Any], user_input: dict[str, Any]) -> bool:
    eligibility = task.get("eligibility", {"all": []})
    return eval_rule(eligibility, user_input)


def eval_rule(rule: Any, facts: dict[str, Any]) -> bool:
    if rule is None:
        raise PlannerRuleError("eligibility cannot be null")
    if not isinstance(rule, dict):
        raise PlannerRuleError("rule must be an object")

    if "all" in rule:
        clauses = rule["all"]
        if not isinstance(clauses, list):
            raise PlannerRuleError("rule.all must be a list")
        return all(eval_rule(clause, facts) for clause in clauses)

    if "any" in rule:
        clauses = rule["any"]
        if not isinstance(clauses, list):
            raise PlannerRuleError("rule.any must be a list")
        return any(eval_rule(clause, facts) for clause in clauses)

    if "not" in rule:
        return not eval_rule(rule["not"], facts)

    return eval_predicate(rule, facts)


def eval_predicate(pred: dict[str, Any], facts: dict[str, Any]) -> bool:
    fact_key = pred.get("fact")
    op = pred.get("op")
    if not isinstance(fact_key, str) or not isinstance(op, str):
        raise PlannerRuleError(f"invalid predicate shape: {pred!r}")

    if op != "exists" and fact_key not in facts:
        return False

    left = facts.get(fact_key)
    right = pred.get("value")

    if op == "exists":
        return fact_key in facts
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == "in":
        return left in right if isinstance(right, list) else False
    if op == ">":
        return _compare_numeric(left, right, lambda a, b: a > b)
    if op == ">=":
        return _compare_numeric(left, right, lambda a, b: a >= b)
    if op == "<":
        return _compare_numeric(left, right, lambda a, b: a < b)
    if op == "<=":
        return _compare_numeric(left, right, lambda a, b: a <= b)

    raise PlannerRuleError(f"unsupported predicate op: {op}")


def _compare_numeric(left: Any, right: Any, fn: Callable[[float, float], bool]) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(fn(float(left), float(right)))
    return False
