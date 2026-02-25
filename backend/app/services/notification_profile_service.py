from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NotificationProfile


class NotificationProfileService:
    def get_or_create(self, session: Session, *, plan_id: UUID) -> NotificationProfile:
        profile = session.scalar(
            select(NotificationProfile).where(NotificationProfile.plan_id == plan_id)
        )
        if profile is not None:
            return profile

        profile = NotificationProfile(plan_id=plan_id)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile

    def upsert_profile(
        self,
        session: Session,
        *,
        plan_id: UUID,
        email: str | None,
        email_consent: bool,
        locale: str,
        timezone: str,
        reminder_due_soon_enabled: bool,
    ) -> NotificationProfile:
        profile = self.get_or_create(session, plan_id=plan_id)
        profile.email = email.strip() if isinstance(email, str) and email.strip() else None
        profile.email_consent = email_consent
        profile.locale = locale
        profile.timezone = timezone
        profile.reminder_due_soon_enabled = reminder_due_soon_enabled

        if not email_consent:
            profile.unsubscribed_at = datetime.now(UTC)
        elif profile.unsubscribed_at is not None:
            profile.unsubscribed_at = None

        profile.updated_at = datetime.now(UTC)
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile

    def is_sendable(self, profile: NotificationProfile) -> bool:
        email = profile.email.strip() if isinstance(profile.email, str) else ""
        return (
            bool(email)
            and profile.email_consent
            and profile.unsubscribed_at is None
            and profile.reminder_due_soon_enabled
        )

    def issue_unsubscribe_token(self, session: Session, *, profile: NotificationProfile) -> str:
        token = secrets.token_urlsafe(24)
        profile.unsubscribe_token_hash = self._hash_token(token)
        profile.updated_at = datetime.now(UTC)
        session.add(profile)
        session.flush()
        return token

    def unsubscribe_by_token(self, session: Session, *, token: str) -> bool:
        token_hash = self._hash_token(token)
        profile = session.scalar(
            select(NotificationProfile).where(
                NotificationProfile.unsubscribe_token_hash == token_hash
            )
        )

        if profile is None:
            return False

        if profile.unsubscribed_at is None:
            profile.unsubscribed_at = datetime.now(UTC)
            profile.updated_at = datetime.now(UTC)
            session.add(profile)
            session.commit()
        return True

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
