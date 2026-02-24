from __future__ import annotations

from typing import Any

from app.planner.deadlines import compute_deadline, parse_iso_date
from app.planner.errors import PlannerDependencyError, PlannerInputError
from app.planner.rules import is_task_active
from app.planner.schema import Plan, TaskPlanItem
from app.planner.toposort import toposort_task_ids


def generate_plan(workflow: dict[str, Any], user_input: dict[str, Any]) -> Plan:
    template_id = _read_str(workflow, "template_id")
    event_date_key = _read_str(workflow, "event_date_key")
    tasks_by_id = _read_tasks(workflow)
    edges = _read_edges(workflow, set(tasks_by_id.keys()))

    if event_date_key not in user_input:
        raise PlannerInputError(f"missing event date fact '{event_date_key}'")
    event_date = parse_iso_date(user_input[event_date_key])

    active_task_ids = {
        task_id
        for task_id in sorted(tasks_by_id.keys())
        if is_task_active(
            _as_dict(tasks_by_id[task_id], f"tasks.{task_id}"), user_input
        )
    }

    depends_on_map: dict[str, list[str]] = {task_id: [] for task_id in active_task_ids}
    active_edges: list[tuple[str, str]] = []

    for source, target in edges:
        if target not in active_task_ids:
            continue
        if source in active_task_ids:
            depends_on_map[target].append(source)
            active_edges.append((source, target))

    for task_id in active_task_ids:
        depends_on_map[task_id] = sorted(depends_on_map[task_id])

    ordered_ids = toposort_task_ids(active_task_ids, active_edges)

    items_by_id: dict[str, TaskPlanItem] = {}
    for task_id in active_task_ids:
        task = _as_dict(tasks_by_id[task_id], f"tasks.{task_id}")
        title = _read_str(task, "title", context=f"tasks.{task_id}")
        deadline_def = _as_dict(task.get("deadline"), f"tasks.{task_id}.deadline")
        deadline_type = deadline_def.get("type")
        if deadline_type != "relative_days":
            raise PlannerInputError(
                f"tasks.{task_id}.deadline.type must be 'relative_days'"
            )

        offset_days = deadline_def.get("offset_days")
        if not isinstance(offset_days, int):
            raise PlannerInputError(f"tasks.{task_id}.deadline.offset_days must be int")

        grace_days = deadline_def.get("grace_days", 0)
        if not isinstance(grace_days, int):
            raise PlannerInputError(f"tasks.{task_id}.deadline.grace_days must be int")

        due_date = compute_deadline(
            event_date=event_date,
            relative_days=offset_days,
            grace_days=grace_days,
        )

        items_by_id[task_id] = {
            "id": task_id,
            "title": title,
            "relative_days": offset_days,
            "deadline": due_date.isoformat(),
            "depends_on": depends_on_map[task_id],
            "meta": {},
        }

    return {
        "workflow_id": template_id,
        "event_date": event_date.isoformat(),
        "tasks": [items_by_id[task_id] for task_id in ordered_ids],
    }


def _read_tasks(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = workflow.get("tasks")
    if not isinstance(raw, dict):
        raise PlannerInputError("workflow.tasks must be an object")

    parsed: dict[str, dict[str, Any]] = {}
    for task_id, task in raw.items():
        if not isinstance(task_id, str):
            raise PlannerInputError("workflow.tasks keys must be strings")
        parsed[task_id] = _as_dict(task, f"tasks.{task_id}")
    return parsed


def _read_edges(
    workflow: dict[str, Any],
    known_task_ids: set[str],
) -> list[tuple[str, str]]:
    graph = _as_dict(workflow.get("graph"), "workflow.graph")
    raw_edges = graph.get("edges", [])
    if not isinstance(raw_edges, list):
        raise PlannerInputError("workflow.graph.edges must be a list")

    parsed: list[tuple[str, str]] = []
    for idx, raw_edge in enumerate(raw_edges):
        edge = _as_dict(raw_edge, f"workflow.graph.edges[{idx}]")
        source = edge.get("from")
        target = edge.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            raise PlannerInputError(
                f"workflow.graph.edges[{idx}] must contain string 'from' and 'to'"
            )
        if source not in known_task_ids or target not in known_task_ids:
            raise PlannerDependencyError(
                "dependency references unknown workflow task id"
            )
        parsed.append((source, target))
    return parsed


def _read_str(payload: dict[str, Any], key: str, context: str = "workflow") -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise PlannerInputError(f"{context}.{key} must be a string")
    return value


def _as_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlannerInputError(f"{field} must be an object")
    return value
