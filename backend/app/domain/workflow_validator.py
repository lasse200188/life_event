from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class WorkflowValidationError(ValueError):
    """Raised when a workflow template is invalid."""


def _as_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise WorkflowValidationError(f"'{field}' must be a list")
    return value


def _as_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowValidationError(f"'{field}' must be an object")
    return value


def validate_graph(template: dict[str, Any]) -> None:
    graph = _as_dict(template.get("graph"), "graph")
    tasks = _as_dict(template.get("tasks"), "tasks")

    nodes_raw = _as_list(graph.get("nodes"), "graph.nodes")
    nodes = [node for node in nodes_raw if isinstance(node, str)]
    if len(nodes) != len(nodes_raw):
        raise WorkflowValidationError("all graph.nodes entries must be strings")
    if len(set(nodes)) != len(nodes):
        raise WorkflowValidationError("Duplicate node ids in graph.nodes")

    task_ids = set(tasks.keys())
    node_ids = set(nodes)
    if node_ids != task_ids:
        missing_in_tasks = sorted(node_ids - task_ids)
        missing_in_graph = sorted(task_ids - node_ids)
        msg_parts: list[str] = []
        if missing_in_tasks:
            msg_parts.append(f"Node missing in tasks: {missing_in_tasks}")
        if missing_in_graph:
            msg_parts.append(f"Task missing in graph.nodes: {missing_in_graph}")
        raise WorkflowValidationError("; ".join(msg_parts))

    edges_raw = _as_list(graph.get("edges", []), "graph.edges")
    edges: list[tuple[str, str]] = []
    for idx, edge in enumerate(edges_raw):
        item = _as_dict(edge, f"graph.edges[{idx}]")
        source = item.get("from")
        target = item.get("to")
        if not isinstance(source, str) or not isinstance(target, str):
            raise WorkflowValidationError(
                f"graph.edges[{idx}] must contain string 'from' and 'to'"
            )
        if source not in node_ids or target not in node_ids:
            raise WorkflowValidationError(
                f"Edge references unknown node: {source!r} -> {target!r}"
            )
        edges.append((source, target))

    _assert_acyclic(nodes, edges)


def _assert_acyclic(nodes: list[str], edges: list[tuple[str, str]]) -> None:
    indegree: dict[str, int] = {node: 0 for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        outgoing[source].append(target)
        indegree[target] += 1

    queue = deque(sorted(node for node, deg in indegree.items() if deg == 0))
    visited = 0

    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in outgoing[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if visited != len(nodes):
        cycle_nodes = sorted(node for node, deg in indegree.items() if deg > 0)
        raise WorkflowValidationError(f"Cycle detected: affected nodes {cycle_nodes}")
