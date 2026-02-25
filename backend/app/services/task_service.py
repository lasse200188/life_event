from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
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
        force: bool = False,
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

        if status == TaskStatus.done:
            if self._is_decision_task(task):
                raise ApiError(
                    status_code=409,
                    code="TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN",
                    message=(
                        "Decision-Task kann nicht manuell abgeschlossen werden; "
                        "bitte Auswahl treffen."
                    ),
                )
            unresolved = self._read_unresolved_dependencies(session, task)
            block_type = self._read_block_type(task.metadata_json)
            if unresolved and block_type == "hard" and not force:
                raise ApiError(
                    status_code=409,
                    code="TASK_BLOCKED",
                    message=(
                        f"Task '{task.task_key}' is blocked by unresolved dependencies: "
                        + ", ".join(unresolved)
                    ),
                )

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

    def _read_unresolved_dependencies(self, session: Session, task: Task) -> list[str]:
        metadata = self._read_metadata(task.metadata_json)
        raw_blocked_by = metadata.get("blocked_by", [])
        if not isinstance(raw_blocked_by, list):
            return []

        blocked_by = [entry for entry in raw_blocked_by if isinstance(entry, str)]
        if not blocked_by:
            return []

        stmt = select(Task.task_key, Task.status).where(
            Task.plan_id == task.plan_id,
            Task.task_key.in_(blocked_by),
        )
        dep_rows = list(session.execute(stmt).all())
        dep_status_by_key = {task_key: status for task_key, status in dep_rows}

        unresolved: list[str] = []
        for dep_key in blocked_by:
            if dep_status_by_key.get(dep_key) != TaskStatus.done.value:
                unresolved.append(dep_key)
        return unresolved

    def _read_block_type(self, metadata: Any) -> str:
        payload = self._read_metadata(metadata)
        block_type = payload.get("block_type", "hard")
        if block_type not in {"hard", "soft"}:
            return "hard"
        return block_type

    def _is_decision_task(self, task: Task) -> bool:
        metadata = self._read_metadata(task.metadata_json)
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            return False
        return any(isinstance(tag, str) and tag == "decision" for tag in tags)

    def _read_metadata(self, metadata: Any) -> dict[str, Any]:
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                parsed = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}
