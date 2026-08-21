"""Small SMTP email service for supervisor feedback delivery."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable


class EmailDeliveryNotConfigured(RuntimeError):
    """Raised when SMTP delivery has not been configured."""


class EmailDeliveryError(RuntimeError):
    """Raised when the configured SMTP provider rejects delivery."""


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/pdf"


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip() and os.getenv("SMTP_FROM_EMAIL", "").strip())


def send_feedback_email(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    attachments: Iterable[EmailAttachment],
) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    if not host or not from_email:
        raise EmailDeliveryNotConfigured("Email delivery is not configured.")

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    from_name = os.getenv("SMTP_FROM_NAME", "ResearchPilot").strip() or "ResearchPilot"
    use_tls = _truthy(os.getenv("SMTP_USE_TLS"), default=True)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = recipient_email
    message.set_content(body)

    for attachment in attachments:
        maintype, subtype = attachment.content_type.split("/", 1)
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(str(exc) or "Email delivery failed.") from exc
    except OSError as exc:
        raise EmailDeliveryError(str(exc) or "Email delivery failed.") from exc
