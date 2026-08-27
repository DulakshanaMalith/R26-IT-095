"""Resend email service for supervisor feedback delivery."""

from __future__ import annotations

import base64
import logging
import os
import socket
from dataclasses import dataclass
from email.utils import parseaddr
from importlib import metadata
from pathlib import Path
from typing import Iterable
from typing import Any

try:
    import resend
except ImportError:  # pragma: no cover - depends on local environment setup.
    resend = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - development dependency fallback.
    load_dotenv = None


logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_ROOT.parent


class EmailDeliveryNotConfigured(RuntimeError):
    """Raised when email delivery has not been configured."""


class EmailDeliveryError(RuntimeError):
    """Raised when the configured provider rejects delivery."""

    def __init__(
        self,
        message: str,
        *,
        provider_response: Any | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_response = provider_response
        self.status_code = status_code


class EmailAuthenticationError(EmailDeliveryError):
    """Raised when Resend authentication fails."""


class EmailSenderVerificationError(EmailDeliveryError):
    """Raised when Resend rejects the configured sender/domain."""


class EmailRecipientRestrictionError(EmailDeliveryError):
    """Raised when Resend rejects the recipient under testing restrictions."""


class EmailTimeoutError(EmailDeliveryError):
    """Raised when Resend delivery times out."""


class EmailConnectionError(EmailDeliveryError):
    """Raised when Resend cannot be reached."""


class InvalidRecipientEmail(ValueError):
    """Raised when an email address is not usable."""


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str = "application/pdf"


def load_email_environment(project_root: Path | None = None) -> None:
    """Load .env files from stable roots regardless of the current working directory."""
    if load_dotenv is None:
        return
    roots = [Path(project_root)] if project_root is not None else [BACKEND_ROOT, REPOSITORY_ROOT]
    for root in roots:
        env_path = root / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)


load_email_environment()


def is_configured() -> bool:
    return email_enabled() and selected_provider() == "resend" and not missing_configuration_fields()


def smtp_configured() -> bool:
    return False


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def email_enabled() -> bool:
    return _truthy(os.getenv("EMAIL_ENABLED"), default=True)


def selected_provider() -> str:
    return os.getenv("EMAIL_PROVIDER", "resend").strip().lower() or "resend"


def missing_configuration_fields() -> list[str]:
    if not email_enabled():
        return []
    return [name for name in ("RESEND_API_KEY", "EMAIL_FROM") if not os.getenv(name, "").strip()]


def validate_configuration() -> None:
    if not email_enabled():
        raise EmailDeliveryNotConfigured("Email delivery is not configured: EMAIL_ENABLED is false.")
    if selected_provider() != "resend":
        raise EmailDeliveryNotConfigured("Email delivery is not configured: EMAIL_PROVIDER must be resend.")
    missing = missing_configuration_fields()
    if missing:
        joined = " and ".join(missing)
        verb = "is" if len(missing) == 1 else "are"
        raise EmailDeliveryNotConfigured(f"Email delivery is not configured: {joined} {verb} missing.")
    validate_sender_address(os.getenv("EMAIL_FROM", ""))
    if resend is None:
        raise EmailDeliveryNotConfigured("Email delivery is not configured: install the resend Python package from requirements.txt.")


def validate_email_address(value: str, *, field_name: str = "email") -> str:
    address = str(value or "").strip()
    _, parsed = parseaddr(address)
    if not parsed or parsed != address or "@" not in parsed:
        raise InvalidRecipientEmail(f"Invalid {field_name} address.")
    local, domain = parsed.rsplit("@", 1)
    if not local or "." not in domain or any(char.isspace() for char in parsed):
        raise InvalidRecipientEmail(f"Invalid {field_name} address.")
    return parsed


def validate_sender_address(value: str) -> str:
    address = str(value or "").strip()
    _, parsed = parseaddr(address)
    if not parsed or "@" not in parsed:
        raise EmailDeliveryNotConfigured("Email delivery is not configured: EMAIL_FROM must be a valid sender address.")
    local, domain = parsed.rsplit("@", 1)
    if not local or "." not in domain or any(char.isspace() for char in parsed):
        raise EmailDeliveryNotConfigured("Email delivery is not configured: EMAIL_FROM must be a valid sender address.")
    return address


def sanitized_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    for secret_name in ("RESEND_API_KEY",):
        secret = os.getenv(secret_name, "")
        if secret:
            message = message.replace(secret, "[redacted]")
    return message[:500]


def _safe_provider_response(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    body = getattr(response, "text", None) or getattr(exc, "message", None)
    if body is None:
        return None
    return sanitized_error(RuntimeError(str(body)))


def _status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None) or getattr(exc, "status_code", None)
    try:
        return int(status_code) if status_code is not None else None
    except (TypeError, ValueError):
        return None


def _message_id_from_response(response: Any) -> str | None:
    if isinstance(response, dict):
        value = response.get("id") or response.get("message_id")
    else:
        value = getattr(response, "id", None) or getattr(response, "message_id", None)
    message_id = str(value or "").strip()
    return message_id or None


def _validate_attachments(attachments: Iterable[EmailAttachment]) -> list[EmailAttachment]:
    validated = []
    for attachment in attachments:
        filename = str(attachment.filename or "").strip()
        if not filename or "/" in filename or "\\" in filename:
            raise EmailDeliveryError("Attachment filename is invalid.")
        if not attachment.content:
            raise EmailDeliveryError("Generated feedback PDF was not found.")
        if attachment.content_type != "application/pdf":
            raise EmailDeliveryError("Attachment MIME type must be application/pdf.")
        validated.append(EmailAttachment(filename=filename, content=attachment.content, content_type=attachment.content_type))
    return validated


def _resend_sdk_version() -> str:
    try:
        return metadata.version("resend")
    except metadata.PackageNotFoundError:
        return "not-installed"


def _sender_domain(sender: str) -> str:
    _, parsed = parseaddr(sender)
    if "@" not in parsed:
        return "invalid"
    return parsed.rsplit("@", 1)[1].lower()


def _masked_email(email: str) -> str:
    if "@" not in email:
        return "[invalid-email]"
    local, domain = email.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[:1]}***@{domain}"


def _map_resend_exception(exc: Exception) -> EmailDeliveryError:
    safe_message = _safe_provider_response(exc) or sanitized_error(exc)
    status_code = _status_code(exc)
    normalized = safe_message.lower()
    if status_code in {401, 403} or any(
        known in normalized
        for known in (
            "api key is invalid",
            "invalid api key",
            "missing api key",
            "unauthorized",
        )
    ):
        return EmailAuthenticationError(
            "Resend authentication failed. Check RESEND_API_KEY.",
            provider_response=safe_message,
            status_code=status_code,
        )
    if any(
        known in normalized
        for known in (
            "can only send emails to your own email address",
            "you can only send testing emails",
            "verify a domain at resend.com/domains",
        )
    ):
        return EmailRecipientRestrictionError(
            "The Resend testing sender can only deliver to the email address associated with the Resend account.",
            provider_response=safe_message,
            status_code=status_code,
        )
    if any(
        known in normalized
        for known in (
            "domain is not verified",
            "sender domain is not verified",
            "sender is not verified",
            "invalid from address",
            "invalid sender",
        )
    ):
        return EmailSenderVerificationError(
            "Resend rejected EMAIL_FROM or the sending domain.",
            provider_response=safe_message,
            status_code=status_code,
        )
    return EmailDeliveryError(
        f"Resend provider request failed: {safe_message}",
        provider_response=safe_message,
        status_code=status_code,
    )


def send_feedback_email(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    attachments: Iterable[EmailAttachment],
) -> str:
    validate_configuration()
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = validate_sender_address(os.getenv("EMAIL_FROM", ""))
    recipient = validate_email_address(recipient_email, field_name="student email")
    validated_attachments = _validate_attachments(attachments)

    payload = {
        "from": from_email,
        "to": [recipient],
        "subject": subject,
        "html": body.replace("\n", "<br>"),
        "text": body,
        "attachments": [
            {
                "filename": attachment.filename,
                "content": base64.b64encode(attachment.content).decode("utf-8"),
            }
            for attachment in validated_attachments
        ],
    }

    resend.api_key = api_key
    for attachment in validated_attachments:
        logger.info(
            "Calling Resend: sender_domain=%s recipient=%s pdf_filename=%s pdf_bytes=%s resend_sdk_version=%s",
            _sender_domain(from_email),
            _masked_email(recipient),
            attachment.filename,
            len(attachment.content),
            _resend_sdk_version(),
        )

    try:
        response = resend.Emails.send(payload)
    except TimeoutError as exc:
        logger.warning("Resend exception: class=%s status_code=%s message=%s", exc.__class__.__name__, None, sanitized_error(exc))
        raise EmailTimeoutError("Resend delivery timed out.") from exc
    except (socket.timeout, OSError) as exc:
        logger.warning("Resend exception: class=%s status_code=%s message=%s", exc.__class__.__name__, None, sanitized_error(exc))
        raise EmailConnectionError("Unable to connect to Resend.") from exc
    except Exception as exc:
        mapped = _map_resend_exception(exc)
        logger.warning(
            "Resend exception: class=%s status_code=%s message=%s",
            exc.__class__.__name__,
            mapped.status_code,
            mapped.provider_response or sanitized_error(mapped),
        )
        raise mapped from exc

    message_id = _message_id_from_response(response)
    if not message_id:
        raise EmailDeliveryError("Resend did not return a message ID.", provider_response=str(response)[:500])
    return message_id
