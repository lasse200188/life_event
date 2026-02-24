from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanStatus(str, Enum):
    creating = "creating"
    active = "active"
    archived = "archived"


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"
    skipped = "skipped"


JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
JSON_EMPTY_DEFAULT = (
    text("'{}'::jsonb")
    if os.getenv("DATABASE_URL", "").startswith("postgresql")
    else text("'{}'")
)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    template_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tasks: Mapped[list[Task]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("plan_id", "task_key", name="uq_tasks_plan_task_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    task_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON_TYPE,
        nullable=False,
        server_default=JSON_EMPTY_DEFAULT,
    )
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan: Mapped[Plan] = relationship(back_populates="tasks")
