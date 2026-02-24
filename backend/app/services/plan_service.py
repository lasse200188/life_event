from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Plan, PlanStatus, Task, TaskStatus
from app.planner.engine import generate_plan
from app.planner.errors import (
    PlannerDependencyError,
    PlannerInputError,
    PlannerRuleError,
)
from app.services.errors import ApiError
from app.services.template_repository import TemplateRepository


class PlanService:
    def __init__(self, template_repository: TemplateRepository | None = None) -> None:
        self.template_repository = template_repository or TemplateRepository()

    def create_plan(
        self, session: Session, *, template_key: str, facts: dict[str, Any]
    ) -> Plan:
        try:
            template = self.template_repository.load(template_key)
            planner_plan = generate_plan(template, facts)
        except ApiError:
            raise
        except (
            PlannerInputError,
            PlannerDependencyError,
            PlannerRuleError,
            ValueError,
        ) as exc:
            raise ApiError(
                status_code=400,
                code="PLANNER_INPUT_INVALID",
                message=str(exc),
            ) from exc

        now = datetime.now(UTC)
        snapshot = {
            "planner_plan": planner_plan,
            "template_meta": {
                "template_key": template_key,
                "template_id": template.get("template_id"),
                "version": template.get("version"),
                "locale": template.get("locale"),
                "event_type": template.get("event_type"),
            },
            "engine_version": "0.1.0",
            "generated_at": now.isoformat(),
            "task_count": len(planner_plan["tasks"]),
        }

        try:
            with session.begin():
                plan = Plan(
                    template_key=template_key,
                    facts=facts,
                    snapshot=snapshot,
                    status=PlanStatus.active.value,
                )
                session.add(plan)
                session.flush()

                for idx, item in enumerate(planner_plan["tasks"]):
                    raw_deadline = item.get("deadline")
                    due_date = None
                    if raw_deadline is not None:
                        if not isinstance(raw_deadline, str):
                            raise ApiError(
                                status_code=400,
                                code="PLANNER_INPUT_INVALID",
                                message="Task deadline must be an ISO date string",
                            )
                        try:
                            due_date = datetime.fromisoformat(raw_deadline).date()
                        except ValueError as exc:
                            raise ApiError(
                                status_code=400,
                                code="PLANNER_INPUT_INVALID",
                                message="Task deadline must be an ISO date string",
                            ) from exc

                    task = Task(
                        plan_id=plan.id,
                        task_key=item["id"],
                        title=item["title"],
                        description=None,
                        status=TaskStatus.todo.value,
                        due_date=due_date,
                        metadata_json=item.get("meta") or {},
                        sort_key=idx,
                    )
                    session.add(task)

            session.refresh(plan)
            return plan
        except ApiError:
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise ApiError(
                status_code=500,
                code="PERSISTENCE_ERROR",
                message="Could not persist generated plan",
            ) from exc

    def get_plan(self, session: Session, plan_id: UUID) -> Plan:
        plan = session.get(Plan, plan_id)
        if plan is None:
            raise ApiError(
                status_code=404,
                code="PLAN_NOT_FOUND",
                message=f"Plan '{plan_id}' not found",
            )
        return plan
