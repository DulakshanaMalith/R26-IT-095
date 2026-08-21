"""Resend email service for supervisor feedback delivery."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Iterable

import requests


class EmailDeliveryNotConfigured(RuntimeError):
    """Raised when email delivery has not been configured."""


class EmailDeliveryError(RuntimeError):
    """Raised when the configured provider rejects delivery."""


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/pdf"


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY", "").strip() and os.getenv("EMAIL_FROM", "").strip())


def send_feedback_email(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    attachments: Iterable[EmailAttachment],
) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("EMAIL_FROM", "").strip()

    if not api_key or not from_email:
        raise EmailDeliveryNotConfigured("Email delivery is not configured.")

    resend_attachments = []
    for attachment in attachments:
        resend_attachments.append({
            "filename": attachment.filename,
            "content": base64.b64encode(attachment.content).decode("utf-8"),
        })

    payload = {
        "from": from_email,
        "to": [recipient_email],
        "subject": subject,
        "text": body,
        "attachments": resend_attachments,
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        error_msg = str(exc)
        if getattr(exc, 'response', None) is not None:
            error_msg = f"{error_msg} - Details: {exc.response.text}"
        raise EmailDeliveryError(error_msg or "Email delivery failed.") from exc
