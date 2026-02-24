from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    PlanCreateLinks,
    PlanCreateRequest,
    PlanCreateResponse,
    PlanResponse,
    SnapshotMeta,
    TaskResponse,
    TaskStatusPatchRequest,
)
from app.db.models import TaskStatus
from app.db.session import get_db_session
from app.services.plan_service import PlanService
from app.services.task_service import TaskService

router = APIRouter(tags=["plans"])


@router.post("/plans", response_model=PlanCreateResponse, status_code=201)
def create_plan(
    payload: PlanCreateRequest,
    session: Session = Depends(get_db_session),
) -> PlanCreateResponse:
    plan = PlanService().create_plan(
        session,
        template_key=payload.template_key,
        facts=payload.facts,
    )

    return PlanCreateResponse(
        id=plan.id,
        template_key=plan.template_key,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        links=PlanCreateLinks(
            self=f"/plans/{plan.id}",
            tasks=f"/plans/{plan.id}/tasks",
        ),
    )


@router.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: UUID,
    include_snapshot: bool = Query(False),
    session: Session = Depends(get_db_session),
) -> PlanResponse:
    plan = PlanService().get_plan(session, plan_id)

    snapshot = plan.snapshot if isinstance(plan.snapshot, dict) else {}
    snapshot_meta = SnapshotMeta(
        generated_at=snapshot.get("generated_at"),
        task_count=snapshot.get("task_count"),
        engine_version=snapshot.get("engine_version"),
        template_key=(
            snapshot.get("template_meta", {}).get("template_key")
            if isinstance(snapshot.get("template_meta"), dict)
            else None
        ),
    )

    return PlanResponse(
        id=plan.id,
        template_key=plan.template_key,
        facts=plan.facts,
        status=plan.status,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        snapshot_meta=snapshot_meta,
        snapshot=snapshot if include_snapshot else None,
    )


@router.get("/plans/{plan_id}/tasks", response_model=list[TaskResponse])
def list_plan_tasks(
    plan_id: UUID,
    status: TaskStatus | None = Query(None),
    include_metadata: bool = Query(False),
    session: Session = Depends(get_db_session),
) -> list[TaskResponse]:
    PlanService().get_plan(session, plan_id)

    tasks = TaskService().list_tasks(session, plan_id=plan_id, status=status)
    return [_serialize_task(task, include_metadata=include_metadata) for task in tasks]


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=TaskResponse)
def update_task_status(
    plan_id: UUID,
    task_id: UUID,
    payload: TaskStatusPatchRequest,
    session: Session = Depends(get_db_session),
) -> TaskResponse:
    task = TaskService().update_status(
        session,
        plan_id=plan_id,
        task_id=task_id,
        status=payload.status,
    )
    return _serialize_task(task, include_metadata=True)


def _serialize_task(task: Any, *, include_metadata: bool) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        plan_id=task.plan_id,
        task_key=task.task_key,
        title=task.title,
        description=task.description,
        status=TaskStatus(task.status),
        due_date=task.due_date,
        metadata=task.metadata_json if include_metadata else None,
        sort_key=task.sort_key,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
