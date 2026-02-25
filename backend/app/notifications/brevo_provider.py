from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.notifications.config import NotificationConfig
from app.notifications.templates import RenderedEmail


@dataclass(frozen=True)
class ProviderSendResult:
    status: str
    failure_class: str | None
    error_code: str | None
    error_message: str | None
    provider_message_id: str | None


class BrevoEmailProvider:
    def __init__(self, config: NotificationConfig) -> None:
        self.config = config

    def send(
        self,
        *,
        to_email: str,
        rendered: RenderedEmail,
    ) -> ProviderSendResult:
        if self.config.email_dry_run:
            return ProviderSendResult(
                status="sent",
                failure_class=None,
                error_code=None,
                error_message=None,
                provider_message_id="dry-run",
            )

        recipient_domain = to_email.split("@")[-1].lower()
        if (
            self.config.allowed_recipient_domains
            and recipient_domain not in self.config.allowed_recipient_domains
        ):
            return ProviderSendResult(
                status="dead",
                failure_class="permanent",
                error_code="RECIPIENT_DOMAIN_NOT_ALLOWED",
                error_message="recipient domain is not in whitelist",
                provider_message_id=None,
            )

        if not self.config.brevo_api_key:
            return ProviderSendResult(
                status="dead",
                failure_class="permanent",
                error_code="BREVO_API_KEY_MISSING",
                error_message="BREVO_API_KEY missing",
                provider_message_id=None,
            )

        request_payload = {
            "sender": {
                "name": self.config.from_name,
                "email": self.config.from_email,
            },
            "to": [{"email": to_email}],
            "subject": rendered.subject,
            "textContent": rendered.text_body,
            "htmlContent": rendered.html_body,
            "tracking": {"opens": False, "clicks": False},
        }

        headers = {
            "api-key": self.config.brevo_api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.config.brevo_base_url}/smtp/email",
                    headers=headers,
                    json=request_payload,
                )
        except httpx.TimeoutException as exc:
            return ProviderSendResult(
                status="pending",
                failure_class="retryable",
                error_code="TIMEOUT",
                error_message=str(exc),
                provider_message_id=None,
            )
        except httpx.HTTPError as exc:
            return ProviderSendResult(
                status="pending",
                failure_class="retryable",
                error_code="HTTP_ERROR",
                error_message=str(exc),
                provider_message_id=None,
            )

        if 200 <= response.status_code < 300:
            provider_message_id = None
            body = response.json() if response.content else {}
            if isinstance(body, dict):
                provider_message_id = body.get("messageId")
            return ProviderSendResult(
                status="sent",
                failure_class=None,
                error_code=None,
                error_message=None,
                provider_message_id=provider_message_id,
            )

        if response.status_code in {408, 409, 429} or response.status_code >= 500:
            return ProviderSendResult(
                status="pending",
                failure_class="retryable",
                error_code=f"HTTP_{response.status_code}",
                error_message=response.text[:500],
                provider_message_id=None,
            )

        return ProviderSendResult(
            status="dead",
            failure_class="permanent",
            error_code=f"HTTP_{response.status_code}",
            error_message=response.text[:500],
            provider_message_id=None,
        )
