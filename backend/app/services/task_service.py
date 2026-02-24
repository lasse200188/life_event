from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Task, TaskStatus
from app.services.errors import ApiError


class TaskService:
    def list_tasks(
        self,
        session: Session,
        *,
        plan_id: UUID,
        status: TaskStatus | None,
    ) -> list[Task]:
        stmt = select(Task).where(Task.plan_id == plan_id)
        if status is not None:
            stmt = stmt.where(Task.status == status.value)
        stmt = stmt.order_by(Task.sort_key.asc())
        return list(session.scalars(stmt).all())

    def update_status(
        self,
        session: Session,
        *,
        plan_id: UUID,
        task_id: UUID,
        status: TaskStatus,
    ) -> Task:
        task = session.get(Task, task_id)
        if task is None or task.plan_id != plan_id:
            raise ApiError(
                status_code=404,
                code="TASK_NOT_FOUND",
                message=f"Task '{task_id}' not found for plan '{plan_id}'",
            )

        previous_status = task.status
        now = datetime.now(UTC)

        task.status = status.value
        task.updated_at = now

        if status == TaskStatus.done:
            if previous_status != TaskStatus.done.value and task.completed_at is None:
                task.completed_at = now
        else:
            task.completed_at = None

        session.add(task)
        session.commit()
        session.refresh(task)
        return task
