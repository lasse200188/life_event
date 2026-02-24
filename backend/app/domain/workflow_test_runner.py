from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.domain.workflow_validator import validate_graph


@dataclass(frozen=True)
class RuntimeResult:
    active_tasks: set[str]
    blocked_by: dict[str, list[str]]
    deadlines: dict[str, str]
    active_recommendations: set[str]


def load_template(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        template = json.load(f)

    if not isinstance(template, dict):
        raise ValueError("template root must be a JSON object")
    validate_graph(template)
    return template


def load_testcase(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)

    if not isinstance(payload, dict):
        raise ValueError(f"testcase at {path} must be a YAML mapping")
    return payload


def run_template(template: dict[str, Any], facts: dict[str, Any]) -> RuntimeResult:
    tasks = _as_dict(template.get("tasks"), "tasks")
    graph = _as_dict(template.get("graph"), "graph")

    active_tasks = {
        task_id
        for task_id, task in tasks.items()
        if eval_rule(
            _as_dict(task, f"tasks.{task_id}").get("eligibility", {"all": []}), facts
        )
    }

    active_recommendations: set[str] = set()
    recommendations = template.get("recommendations", {})
    if isinstance(recommendations, dict):
        for rec_id, rec in recommendations.items():
            rec_rule = _as_dict(rec, f"recommendations.{rec_id}").get(
                "eligibility", {"all": []}
            )
            if eval_rule(rec_rule, facts):
                active_recommendations.add(rec_id)

    blocked_by: dict[str, list[str]] = {task_id: [] for task_id in active_tasks}
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = edge.get("from")
        target = edge.get("to")
        if source in active_tasks and target in active_tasks:
            blocked_by[target].append(source)

    deadlines: dict[str, str] = {}
    for task_id in active_tasks:
        task = _as_dict(tasks[task_id], f"tasks.{task_id}")
        deadline = task.get("deadline")
        if not isinstance(deadline, dict):
            continue
        value = compute_deadline(deadline, facts)
        if value is not None:
            deadlines[task_id] = value

    return RuntimeResult(
        active_tasks=active_tasks,
        blocked_by={task_id: sorted(reqs) for task_id, reqs in blocked_by.items()},
        deadlines=deadlines,
        active_recommendations=active_recommendations,
    )


def eval_rule(rule: Any, facts: dict[str, Any]) -> bool:
    if rule is None:
        return True
    if not isinstance(rule, dict):
        raise ValueError("rule must be an object")

    if "all" in rule:
        clauses = rule["all"]
        if not isinstance(clauses, list):
            raise ValueError("rule.all must be a list")
        return all(eval_rule(clause, facts) for clause in clauses)

    if "any" in rule:
        clauses = rule["any"]
        if not isinstance(clauses, list):
            raise ValueError("rule.any must be a list")
        return any(eval_rule(clause, facts) for clause in clauses)

    if "not" in rule:
        return not eval_rule(rule["not"], facts)

    return eval_predicate(rule, facts)


def eval_predicate(pred: dict[str, Any], facts: dict[str, Any]) -> bool:
    fact_key = pred.get("fact")
    op = pred.get("op")
    if not isinstance(fact_key, str) or not isinstance(op, str):
        raise ValueError(f"invalid predicate shape: {pred!r}")

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

    raise ValueError(f"unsupported predicate op: {op}")


def _compare_numeric(left: Any, right: Any, fn: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(fn(left, right))
    return False


def compute_deadline(deadline: dict[str, Any], facts: dict[str, Any]) -> str | None:
    if deadline.get("type") != "relative_days":
        return None

    reference = deadline.get("reference")
    offset_days = deadline.get("offset_days")
    grace_days = deadline.get("grace_days", 0)

    if not isinstance(reference, str):
        raise ValueError("deadline.reference must be a string")
    if not isinstance(offset_days, int) or not isinstance(grace_days, int):
        raise ValueError("deadline.offset_days/grace_days must be int")

    raw = facts.get(reference)
    if raw is None:
        return None

    start = _parse_date(raw)
    due = start + timedelta(days=offset_days + grace_days)
    return due.isoformat()


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"unsupported date value: {value!r}")


def _as_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"'{field}' must be an object")
    return value
