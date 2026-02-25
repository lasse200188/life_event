from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationConfig:
    app_base_url: str
    from_email: str
    from_name: str
    brevo_api_key: str
    brevo_base_url: str
    email_dry_run: bool
    allowed_recipient_domains: set[str]



def load_notification_config() -> NotificationConfig:
    allowed_domains_raw = os.getenv("EMAIL_ALLOWED_RECIPIENT_DOMAINS", "")
    allowed_domains = {
        domain.strip().lower()
        for domain in allowed_domains_raw.split(",")
        if domain.strip()
    }

    return NotificationConfig(
        app_base_url=os.getenv("APP_BASE_URL", "http://localhost:3000"),
        from_email=os.getenv("EMAIL_FROM_ADDRESS", "noreply@example.com"),
        from_name=os.getenv("EMAIL_FROM_NAME", "Life Event"),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        brevo_base_url=os.getenv("BREVO_BASE_URL", "https://api.brevo.com/v3"),
        email_dry_run=os.getenv("EMAIL_DRY_RUN", "true").lower() == "true",
        allowed_recipient_domains=allowed_domains,
    )
