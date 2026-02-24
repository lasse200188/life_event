from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import TaskStatus


class PlanCreateRequest(BaseModel):
    template_key: str
    facts: dict[str, Any]


class PlanCreateLinks(BaseModel):
    self: str
    tasks: str


class PlanCreateResponse(BaseModel):
    id: UUID
    template_key: str
    status: str
    created_at: datetime
    updated_at: datetime
    links: PlanCreateLinks


class SnapshotMeta(BaseModel):
    generated_at: str | None
    task_count: int | None
    engine_version: str | None
    template_key: str | None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_key: str
    facts: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
    snapshot_meta: SnapshotMeta
    snapshot: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    task_key: str
    title: str
    description: str | None
    status: TaskStatus
    due_date: date | None
    metadata: dict[str, Any] | None = None
    sort_key: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskStatusPatchRequest(BaseModel):
    status: TaskStatus = Field(...)
    force: bool = Field(default=False)


class ErrorEnvelope(BaseModel):
    error: dict[str, Any]
