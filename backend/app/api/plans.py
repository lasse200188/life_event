from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    PlanFactsPatchRequest,
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

    return _serialize_plan(plan, include_snapshot=include_snapshot)


@router.patch("/plans/{plan_id}/facts", response_model=PlanResponse)
def patch_plan_facts(
    plan_id: UUID,
    payload: PlanFactsPatchRequest,
    session: Session = Depends(get_db_session),
) -> PlanResponse:
    plan = PlanService().update_facts(
        session,
        plan_id=plan_id,
        facts_patch=payload.facts,
        recompute=payload.recompute,
    )
    return _serialize_plan(plan, include_snapshot=False)


@router.post("/plans/{plan_id}/recompute", response_model=PlanResponse)
def recompute_plan(
    plan_id: UUID,
    session: Session = Depends(get_db_session),
) -> PlanResponse:
    plan = PlanService().recompute_plan(session, plan_id=plan_id)
    return _serialize_plan(plan, include_snapshot=False)


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
        force=payload.force,
    )
    return _serialize_task(task, include_metadata=True)


def _serialize_task(task: Any, *, include_metadata: bool) -> TaskResponse:
    metadata = _read_metadata(task.metadata_json)
    return TaskResponse(
        id=task.id,
        plan_id=task.plan_id,
        task_key=task.task_key,
        title=task.title,
        description=task.description,
        task_kind=_derive_task_kind(metadata),
        status=TaskStatus(task.status),
        due_date=task.due_date,
        metadata=metadata if include_metadata else None,
        sort_key=task.sort_key,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _serialize_plan(plan: Any, *, include_snapshot: bool) -> PlanResponse:
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


def _derive_task_kind(metadata: dict[str, Any]) -> str:
    raw_tags = metadata.get("tags", [])
    tags = raw_tags if isinstance(raw_tags, list) else []
    has_decision_tag = any(isinstance(tag, str) and tag == "decision" for tag in tags)

    raw_actions = metadata.get("ui_actions", [])
    has_ui_actions = isinstance(raw_actions, list) and len(raw_actions) > 0

    if has_decision_tag or has_ui_actions:
        return "decision"
    return "normal"


def _read_metadata(metadata: Any) -> dict[str, Any]:
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
