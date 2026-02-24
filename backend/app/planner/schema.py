from __future__ import annotations

from typing import Any, TypedDict


class TaskPlanItem(TypedDict):
    id: str
    title: str
    relative_days: int
    deadline: str
    depends_on: list[str]
    meta: dict[str, Any]


class Plan(TypedDict):
    workflow_id: str
    event_date: str
    tasks: list[TaskPlanItem]
