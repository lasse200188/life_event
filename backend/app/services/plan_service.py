from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Plan, PlanStatus, Task, TaskStatus, TemplateVersion
from app.planner.engine import generate_plan
from app.planner.errors import (
    PlannerDependencyError,
    PlannerInputError,
    PlannerRuleError,
)
from app.services.errors import ApiError
from app.services.facts_normalizer import (
    migrate_facts_to_latest_schema,
    normalize_facts,
)
from app.services.template_catalog_service import TemplateCatalogService
from app.services.template_repository import TemplateRepository

ENGINE_VERSION = "0.2.0"
RECOMPUTE_REASON_MANUAL = "MANUAL"
RECOMPUTE_REASON_FACT_CHANGE = "FACT_CHANGE"
RECOMPUTE_REASON_TEMPLATE_UPDATE = "TEMPLATE_UPDATE"
OPEN_TASK_STATUSES = {
    TaskStatus.todo.value,
    TaskStatus.in_progress.value,
    TaskStatus.blocked.value,
}


class PlanService:
    def __init__(
        self,
        template_repository: TemplateRepository | None = None,
        template_catalog_service: TemplateCatalogService | None = None,
    ) -> None:
        self.template_repository = template_repository or TemplateRepository()
        self.template_catalog_service = (
            template_catalog_service or TemplateCatalogService(self.template_repository)
        )

    def create_plan(
        self,
        session: Session,
        *,
        template_id: str | None = None,
        template_key: str | None = None,
        facts: dict[str, Any],
        upgraded_from_plan_id: UUID | None = None,
    ) -> Plan:
        try:
            (
                resolved_template_id,
                resolved_template_version,
                resolved_template_key,
                expected_compiled_hash,
            ) = self._resolve_template_selector(
                session,
                template_id=template_id,
                template_key=template_key,
            )
            template = self.template_repository.load_by_id_version(
                resolved_template_id,
                resolved_template_version,
                expected_compiled_hash=expected_compiled_hash,
            )
            normalized_facts, schema_from, schema_to = self._prepare_facts(
                template_key=resolved_template_key,
                template=template,
                input_facts=facts,
                source_schema_version=None,
            )
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
        facts_hash = _hash_facts(normalized_facts)
        snapshot = self._build_snapshot(
            template_key=resolved_template_key,
            template=template,
            planner_plan=planner_plan,
            generated_at=now,
            facts_hash=facts_hash,
            schema_from=schema_from,
            schema_to=schema_to,
            recompute_reason=None,
            recompute_delta=None,
        )

        try:
            plan = Plan(
                template_id=resolved_template_id,
                template_version=resolved_template_version,
                template_key=resolved_template_key,
                upgraded_from_plan_id=upgraded_from_plan_id,
                facts=normalized_facts,
                snapshot=snapshot,
                status=PlanStatus.active.value,
            )
            session.add(plan)
            session.flush()

            for idx, item in enumerate(planner_plan["tasks"]):
                template_task = _read_template_task(template, item["id"])
                due_date = _read_due_date(item.get("deadline"))
                metadata = _build_task_metadata(item=item, template_task=template_task)

                task = Task(
                    plan_id=plan.id,
                    task_key=item["id"],
                    title=item["title"],
                    description=None,
                    status=TaskStatus.todo.value,
                    due_date=due_date,
                    metadata_json=metadata,
                    task_template_version=_read_template_version(template),
                    sort_key=idx,
                )
                session.add(task)

            session.commit()
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

        if recompute:
            return self.recompute_plan(
                session,
                plan_id=plan_id,
                reason=RECOMPUTE_REASON_FACT_CHANGE,
                facts_override=merged_facts,
            )

        template = self._load_template_for_plan(session, plan)
        snapshot = plan.snapshot if isinstance(plan.snapshot, dict) else {}
        source_schema_version = _read_snapshot_fact_schema_version(snapshot)
        normalized_facts, _, _ = self._prepare_facts(
            template_key=plan.template_key,
            template=template,
            input_facts=merged_facts,
            source_schema_version=source_schema_version,
        )

        plan.facts = normalized_facts
        plan.updated_at = datetime.now(UTC)
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan

    def recompute_plan(
        self,
        session: Session,
        *,
        plan_id: UUID,
        reason: str = RECOMPUTE_REASON_MANUAL,
        facts_override: dict[str, Any] | None = None,
    ) -> Plan:
        plan = self.get_plan(session, plan_id)
        template_key = plan.template_key
        snapshot_before = plan.snapshot if isinstance(plan.snapshot, dict) else {}
        template = self._load_template_for_plan(session, plan)

        input_facts = (
            dict(facts_override)
            if isinstance(facts_override, dict)
            else (dict(plan.facts) if isinstance(plan.facts, dict) else {})
        )
        source_schema_version = _read_snapshot_fact_schema_version(snapshot_before)

        try:
            normalized_facts, schema_from, schema_to = self._prepare_facts(
                template_key=template_key,
                template=template,
                input_facts=input_facts,
                source_schema_version=source_schema_version,
            )
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

        current_facts = dict(plan.facts) if isinstance(plan.facts, dict) else {}
        facts_hash = _hash_facts(normalized_facts)
        current_facts_hash = _read_snapshot_facts_hash(snapshot_before)
        target_template_version = _read_template_version(template)
        current_template_version = _read_snapshot_template_version(snapshot_before)
        current_engine_version = _read_snapshot_engine_version(snapshot_before)

        if (
            reason == RECOMPUTE_REASON_FACT_CHANGE
            and current_facts_hash is not None
            and facts_hash == current_facts_hash
            and target_template_version == current_template_version
            and current_engine_version == ENGINE_VERSION
        ):
            now = datetime.now(UTC)
            existing_plan_payload = snapshot_before.get("planner_plan")
            existing_plan = (
                existing_plan_payload
                if isinstance(existing_plan_payload, dict)
                else {"tasks": []}
            )
            snapshot = self._build_snapshot(
                template_key=template_key,
                template=template,
                planner_plan=existing_plan,
                generated_at=now,
                facts_hash=facts_hash,
                schema_from=schema_from,
                schema_to=schema_to,
                recompute_reason=reason,
                recompute_delta={
                    "added_task_keys": [],
                    "soft_dismissed_task_keys": [],
                    "reactivated_task_keys": [],
                    "updated_task_keys": [],
                    "status_changes": [],
                    "deadline_changes": [],
                    "facts_diff": _facts_diff(current_facts, normalized_facts),
                },
            )

            plan.facts = normalized_facts
            plan.snapshot = snapshot
            plan.updated_at = now
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return plan

        try:
            planner_plan = generate_plan(template, normalized_facts)
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

        existing_tasks = list(
            session.scalars(select(Task).where(Task.plan_id == plan.id)).all()
        )
        existing_by_key = {task.task_key: task for task in existing_tasks}

        added_task_keys: list[str] = []
        soft_dismissed_task_keys: list[str] = []
        reactivated_task_keys: list[str] = []
        updated_task_keys: list[str] = []
        status_changes: list[dict[str, str]] = []
        deadline_changes: list[dict[str, str | None]] = []

        now = datetime.now(UTC)
        sort_index = 0

        for item in planner_plan["tasks"]:
            task_key = item["id"]
            template_task = _read_template_task(template, task_key)
            new_due_date = _read_due_date(item.get("deadline"))
            new_metadata = _build_task_metadata(item=item, template_task=template_task)
            new_title = item["title"]
            existing = existing_by_key.pop(task_key, None)

            if existing is None:
                task = Task(
                    plan_id=plan.id,
                    task_key=task_key,
                    title=new_title,
                    description=None,
                    status=TaskStatus.todo.value,
                    due_date=new_due_date,
                    metadata_json=new_metadata,
                    task_template_version=target_template_version,
                    sort_key=sort_index,
                )
                session.add(task)
                added_task_keys.append(task_key)
                sort_index += 1
                continue

            changed = False
            old_status = existing.status
            old_due_date = existing.due_date
            old_title = existing.title
            old_metadata = (
                existing.metadata_json
                if isinstance(existing.metadata_json, dict)
                else {}
            )

            next_status = _next_status(old_status=old_status, eligible=True)
            if next_status != old_status:
                existing.status = next_status
                existing.updated_at = now
                changed = True
                status_changes.append(
                    {
                        "task_key": task_key,
                        "from": old_status,
                        "to": next_status,
                    }
                )
                if (
                    old_status == TaskStatus.skipped.value
                    and next_status == TaskStatus.todo.value
                ):
                    reactivated_task_keys.append(task_key)
                if next_status != TaskStatus.done.value:
                    existing.completed_at = None

            if existing.status != TaskStatus.done.value:
                if old_title != new_title:
                    existing.title = new_title
                    changed = True
                if old_metadata != new_metadata:
                    existing.metadata_json = new_metadata
                    changed = True
                if existing.task_template_version != target_template_version:
                    existing.task_template_version = target_template_version
                    changed = True

            existing.sort_key = sort_index
            sort_index += 1

            if old_due_date != new_due_date and existing.status in OPEN_TASK_STATUSES:
                existing.due_date = new_due_date
                changed = True
                deadline_changes.append(
                    {
                        "task_key": task_key,
                        "from": _date_to_iso(old_due_date),
                        "to": _date_to_iso(new_due_date),
                    }
                )

            if changed:
                existing.updated_at = now
                session.add(existing)
                updated_task_keys.append(task_key)

        for task_key, existing in existing_by_key.items():
            changed = False
            old_status = existing.status
            next_status = _next_status(old_status=old_status, eligible=False)
            if next_status != old_status:
                existing.status = next_status
                existing.updated_at = now
                changed = True
                status_changes.append(
                    {
                        "task_key": task_key,
                        "from": old_status,
                        "to": next_status,
                    }
                )
                if (
                    next_status == TaskStatus.skipped.value
                    and old_status != TaskStatus.skipped.value
                ):
                    soft_dismissed_task_keys.append(task_key)

            existing.sort_key = sort_index
            sort_index += 1
            changed = True

            if changed:
                session.add(existing)
                updated_task_keys.append(task_key)

        recompute_delta = {
            "added_task_keys": sorted(set(added_task_keys)),
            "soft_dismissed_task_keys": sorted(set(soft_dismissed_task_keys)),
            "reactivated_task_keys": sorted(set(reactivated_task_keys)),
            "updated_task_keys": sorted(set(updated_task_keys)),
            "status_changes": status_changes,
            "deadline_changes": deadline_changes,
            "facts_diff": _facts_diff(current_facts, normalized_facts),
        }

        snapshot = self._build_snapshot(
            template_key=template_key,
            template=template,
            planner_plan=planner_plan,
            generated_at=now,
            facts_hash=facts_hash,
            schema_from=schema_from,
            schema_to=schema_to,
            recompute_reason=reason,
            recompute_delta=recompute_delta,
        )

        try:
            plan.facts = normalized_facts
            plan.snapshot = snapshot
            plan.updated_at = now
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return plan
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

    def upgrade_plan(self, session: Session, *, plan_id: UUID) -> Plan:
        source_plan = self.get_plan(session, plan_id)
        source_template_id = source_plan.template_id
        source_template_version = source_plan.template_version
        latest_published = self.template_catalog_service.resolve_latest_published(
            session, template_id=source_template_id
        )
        if latest_published.version == source_template_version:
            raise ApiError(
                status_code=409,
                code="NO_UPGRADE_AVAILABLE",
                message=(
                    f"Plan '{plan_id}' already uses latest published version "
                    f"{source_template_id}/v{source_template_version}"
                ),
            )

        source_facts = (
            dict(source_plan.facts) if isinstance(source_plan.facts, dict) else {}
        )
        return self.create_plan(
            session,
            template_key=latest_published.template_key,
            facts=source_facts,
            upgraded_from_plan_id=source_plan.id,
        )

    def _prepare_facts(
        self,
        *,
        template_key: str,
        template: dict[str, Any],
        input_facts: dict[str, Any],
        source_schema_version: int | None,
    ) -> tuple[dict[str, Any], int, int]:
        migrated_facts, schema_from, schema_to = migrate_facts_to_latest_schema(
            template,
            input_facts,
            source_schema_version=source_schema_version,
        )
        normalized_facts = normalize_facts(template_key, migrated_facts)
        return normalized_facts, schema_from, schema_to

    def _resolve_template_selector(
        self,
        session: Session,
        *,
        template_id: str | None,
        template_key: str | None,
    ) -> tuple[str, int, str, str | None]:
        has_template_id = isinstance(template_id, str) and bool(template_id)
        has_template_key = isinstance(template_key, str) and bool(template_key)
        if has_template_id == has_template_key:
            raise ApiError(
                status_code=400,
                code="INVALID_TEMPLATE_SELECTOR",
                message="Exactly one of 'template_id' or 'template_key' must be provided",
            )

        if has_template_id:
            resolved = self.template_catalog_service.resolve_latest_published(
                session, template_id=template_id
            )
            return (
                resolved.template_id,
                resolved.version,
                resolved.template_key,
                resolved.compiled_hash,
            )

        assert template_key is not None
        try:
            resolved = self.template_catalog_service.resolve_published_by_key(
                session, template_key=template_key
            )
            return (
                resolved.template_id,
                resolved.version,
                resolved.template_key,
                resolved.compiled_hash,
            )
        except ApiError as exc:
            if exc.code != "TEMPLATE_NOT_FOUND":
                raise

            parsed_template_id, parsed_template_version = (
                self.template_repository.parse_template_key(template_key)
            )
            return (
                parsed_template_id,
                parsed_template_version,
                template_key,
                None,
            )

    def _load_template_for_plan(
        self,
        session: Session,
        plan: Plan,
    ) -> dict[str, Any]:
        row = session.scalar(
            select(TemplateVersion).where(
                TemplateVersion.template_key == plan.template_key
            )
        )
        expected_compiled_hash = row.compiled_hash if row is not None else None
        return self.template_repository.load(
            plan.template_key, expected_compiled_hash=expected_compiled_hash
        )

    def latest_published_version(
        self,
        session: Session,
        *,
        template_id: str,
    ) -> int | None:
        return self.template_catalog_service.get_latest_published_version(
            session, template_id=template_id
        )

    def _build_snapshot(
        self,
        *,
        template_key: str,
        template: dict[str, Any],
        planner_plan: dict[str, Any],
        generated_at: datetime,
        facts_hash: str,
        schema_from: int,
        schema_to: int,
        recompute_reason: str | None,
        recompute_delta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        snapshot = {
            "planner_plan": planner_plan,
            "template_version": _read_template_version(template),
            "fact_schema_version": schema_to,
            "template_meta": {
                "template_key": template_key,
                "template_id": template.get("template_id"),
                "version": _read_template_version(template),
                "fact_schema_version": schema_to,
                "locale": template.get("locale"),
                "event_type": template.get("event_type"),
            },
            "engine_version": ENGINE_VERSION,
            "facts_hash": facts_hash,
            "generated_at": generated_at.isoformat(),
            "task_count": len(planner_plan.get("tasks", [])),
        }
        if recompute_reason is not None:
            snapshot["recompute"] = {
                "executed_at": generated_at.isoformat(),
                "reason": recompute_reason,
                "schema_from": schema_from,
                "schema_to": schema_to,
            }
            snapshot["recompute_delta"] = recompute_delta or {}
        return snapshot


def _read_due_date(raw_deadline: Any) -> date | None:
    if raw_deadline is None:
        return None
    if not isinstance(raw_deadline, str):
        raise ApiError(
            status_code=400,
            code="PLANNER_INPUT_INVALID",
            message="Task deadline must be an ISO date string",
        )
    try:
        return datetime.fromisoformat(raw_deadline).date()
    except ValueError as exc:
        raise ApiError(
            status_code=400,
            code="PLANNER_INPUT_INVALID",
            message="Task deadline must be an ISO date string",
        ) from exc


def _read_template_task(template: dict[str, Any], task_key: str) -> dict[str, Any]:
    template_tasks = template.get("tasks", {})
    if not isinstance(template_tasks, dict):
        return {}
    template_task_raw = template_tasks.get(task_key, {})
    if isinstance(template_task_raw, dict):
        return template_task_raw
    return {}


def _build_task_metadata(
    *,
    item: dict[str, Any],
    template_task: dict[str, Any],
) -> dict[str, Any]:
    metadata = item.get("meta") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        **metadata,
        "category": template_task.get("category"),
        "priority": template_task.get("priority"),
        "effort": (
            template_task.get("effort")
            if isinstance(template_task.get("effort"), dict)
            else {}
        ),
        "links": (
            template_task.get("links")
            if isinstance(template_task.get("links"), list)
            else []
        ),
        "docs_required": (
            template_task.get("docs_required")
            if isinstance(template_task.get("docs_required"), list)
            else []
        ),
        "tags": (
            template_task.get("tags")
            if isinstance(template_task.get("tags"), list)
            else []
        ),
        "ui_actions": (
            template_task.get("ui_actions")
            if isinstance(template_task.get("ui_actions"), list)
            else []
        ),
        "blocked_by": (
            item.get("depends_on") if isinstance(item.get("depends_on"), list) else []
        ),
        "block_type": "hard",
        "deadline_reference_value": item.get("deadline"),
    }


def _read_template_version(template: dict[str, Any]) -> int:
    value = template.get("version")
    if isinstance(value, int):
        return value
    return 1


def _next_status(*, old_status: str, eligible: bool) -> str:
    if old_status == TaskStatus.done.value:
        return TaskStatus.done.value
    if eligible:
        if old_status == TaskStatus.skipped.value:
            return TaskStatus.todo.value
        return old_status
    if old_status in {
        TaskStatus.todo.value,
        TaskStatus.in_progress.value,
        TaskStatus.blocked.value,
    }:
        return TaskStatus.skipped.value
    return old_status


def _facts_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    keys = sorted(set(before.keys()) | set(after.keys()))
    for key in keys:
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value != new_value:
            changes.append(
                {
                    "fact": key,
                    "from": old_value,
                    "to": new_value,
                }
            )
    return changes


def _hash_facts(facts: dict[str, Any]) -> str:
    serialized = json.dumps(
        facts, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _read_snapshot_fact_schema_version(snapshot: dict[str, Any]) -> int | None:
    template_meta = snapshot.get("template_meta")
    if isinstance(template_meta, dict) and isinstance(
        template_meta.get("fact_schema_version"), int
    ):
        return int(template_meta["fact_schema_version"])
    if isinstance(snapshot.get("fact_schema_version"), int):
        return int(snapshot["fact_schema_version"])
    return None


def _read_snapshot_facts_hash(snapshot: dict[str, Any]) -> str | None:
    value = snapshot.get("facts_hash")
    if isinstance(value, str) and value:
        return value
    return None


def _read_snapshot_template_version(snapshot: dict[str, Any]) -> int | None:
    template_meta = snapshot.get("template_meta")
    if isinstance(template_meta, dict) and isinstance(
        template_meta.get("version"), int
    ):
        return int(template_meta["version"])
    if isinstance(snapshot.get("template_version"), int):
        return int(snapshot["template_version"])
    return None


def _read_snapshot_engine_version(snapshot: dict[str, Any]) -> str | None:
    value = snapshot.get("engine_version")
    if isinstance(value, str):
        return value
    return None


def _date_to_iso(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
