from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
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
from app.services.facts_normalizer import normalize_facts
from app.services.template_repository import TemplateRepository


class PlanService:
    def __init__(self, template_repository: TemplateRepository | None = None) -> None:
        self.template_repository = template_repository or TemplateRepository()

    def create_plan(
        self, session: Session, *, template_key: str, facts: dict[str, Any]
    ) -> Plan:
        try:
            template = self.template_repository.load(template_key)
            normalized_facts = normalize_facts(template_key, facts)
            planner_plan = generate_plan(template, normalized_facts)
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
                    facts=normalized_facts,
                    snapshot=snapshot,
                    status=PlanStatus.active.value,
                )
                session.add(plan)
                session.flush()

                for idx, item in enumerate(planner_plan["tasks"]):
                    template_tasks = template.get("tasks", {})
                    template_task_raw = template_tasks.get(item["id"], {})
                    template_task = (
                        template_task_raw if isinstance(template_task_raw, dict) else {}
                    )

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

                    metadata = item.get("meta") or {}
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata = {
                        **metadata,
                        "category": template_task.get("category"),
                        "priority": template_task.get("priority"),
                        "tags": (
                            template_task.get("tags")
                            if isinstance(template_task.get("tags"), list)
                            else []
                        ),
                        "blocked_by": (
                            item.get("depends_on")
                            if isinstance(item.get("depends_on"), list)
                            else []
                        ),
                        "block_type": "hard",
                    }

                    task = Task(
                        plan_id=plan.id,
                        task_key=item["id"],
                        title=item["title"],
                        description=None,
                        status=TaskStatus.todo.value,
                        due_date=due_date,
                        metadata_json=metadata,
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

    def update_facts(
        self,
        session: Session,
        *,
        plan_id: UUID,
        facts_patch: dict[str, Any],
        recompute: bool = True,
    ) -> Plan:
        plan = self.get_plan(session, plan_id)
        merged_facts = dict(plan.facts) if isinstance(plan.facts, dict) else {}
        merged_facts.update(facts_patch)
        plan.facts = normalize_facts(plan.template_key, merged_facts)
        plan.updated_at = datetime.now(UTC)
        session.add(plan)
        session.commit()
        session.refresh(plan)

        if recompute:
            return self.recompute_plan(session, plan_id=plan_id)
        return plan

    def recompute_plan(self, session: Session, *, plan_id: UUID) -> Plan:
        plan = self.get_plan(session, plan_id)
        template_key = plan.template_key
        current_facts = dict(plan.facts) if isinstance(plan.facts, dict) else {}

        try:
            template = self.template_repository.load(template_key)
            normalized_facts = normalize_facts(template_key, current_facts)
            planner_plan = generate_plan(template, normalized_facts)
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

        done_status_by_task_key: dict[str, datetime | None] = {}
        existing_tasks = list(
            session.scalars(select(Task).where(Task.plan_id == plan.id)).all()
        )
        for existing_task in existing_tasks:
            if existing_task.status == TaskStatus.done.value:
                done_status_by_task_key[existing_task.task_key] = existing_task.completed_at

        try:
            plan.facts = normalized_facts
            plan.snapshot = snapshot
            plan.updated_at = now
            session.add(plan)

            for existing_task in existing_tasks:
                session.delete(existing_task)
            session.flush()

            for idx, item in enumerate(planner_plan["tasks"]):
                template_tasks = template.get("tasks", {})
                template_task_raw = template_tasks.get(item["id"], {})
                template_task = (
                    template_task_raw if isinstance(template_task_raw, dict) else {}
                )

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

                metadata = item.get("meta") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata = {
                    **metadata,
                    "category": template_task.get("category"),
                    "priority": template_task.get("priority"),
                    "tags": (
                        template_task.get("tags")
                        if isinstance(template_task.get("tags"), list)
                        else []
                    ),
                    "blocked_by": (
                        item.get("depends_on")
                        if isinstance(item.get("depends_on"), list)
                        else []
                    ),
                    "block_type": "hard",
                }

                was_done = item["id"] in done_status_by_task_key
                task = Task(
                    plan_id=plan.id,
                    task_key=item["id"],
                    title=item["title"],
                    description=None,
                    status=TaskStatus.done.value if was_done else TaskStatus.todo.value,
                    due_date=due_date,
                    metadata_json=metadata,
                    sort_key=idx,
                    completed_at=done_status_by_task_key.get(item["id"]),
                )
                session.add(task)

            session.commit()
            session.refresh(plan)
            return plan
        except ApiError:
            session.rollback()
            raise
        except SQLAlchemyError as exc:
            session.rollback()
            raise ApiError(
                status_code=500,
                code="PERSISTENCE_ERROR",
                message="Could not persist recomputed plan",
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
