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


class NotificationChannel(str, Enum):
    email = "email"


class NotificationType(str, Enum):
    task_due_soon = "task_due_soon"


class NotificationOutboxStatus(str, Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    dead = "dead"


class NotificationFailureClass(str, Enum):
    retryable = "retryable"
    permanent = "permanent"


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


class NotificationProfile(Base):
    __tablename__ = "notification_profiles"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_notification_profiles_plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_consent: Mapped[bool] = mapped_column(nullable=False, default=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="de-DE")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Europe/Berlin"
    )
    reminder_due_soon_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True
    )
    max_reminders_per_day: Mapped[int] = mapped_column(nullable=False, default=1)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unsubscribe_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan: Mapped[Plan] = relationship()


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint(
            "dedupe_key_raw", name="uq_notification_outbox_dedupe_key_raw"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key_raw: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        nullable=False,
        server_default=JSON_EMPTY_DEFAULT,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped[NotificationProfile] = relationship()
