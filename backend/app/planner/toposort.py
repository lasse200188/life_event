from __future__ import annotations

import heapq
from collections import defaultdict

from app.planner.errors import PlannerCycleError, PlannerDependencyError


def toposort_task_ids(
    task_ids: set[str],
    edges: list[tuple[str, str]],
) -> list[str]:
    indegree = {task_id: 0 for task_id in task_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)

    for source, target in edges:
        if source not in task_ids or target not in task_ids:
            raise PlannerDependencyError("dependency references unknown active task")
        outgoing[source].append(target)
        indegree[target] += 1

    ready = [task_id for task_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)

    order: list[str] = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for nxt in sorted(outgoing[current]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, nxt)

    if len(order) != len(task_ids):
        raise PlannerCycleError("Cycle detected in active task graph")

    return order
