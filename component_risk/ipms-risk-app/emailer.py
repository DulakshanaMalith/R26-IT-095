"""Sends email notifications through SMTP, configured via .env."""
import os
import smtplib
from email.message import EmailMessage


def get_config():
    host = os.environ.get("SMTP_HOST", "").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
    except ValueError:
        port = 587
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip() or username
    use_tls = os.environ.get("SMTP_USE_TLS", "1").strip() != "0"
    return host, port, username, password, sender, use_tls


def is_configured():
    host, _port, _user, _pw, sender, _tls = get_config()
    return bool(host and sender)


def send_email(recipients, subject, body):
    """Sends a plain-text email. Returns None on success, or an error message."""
    host, port, username, password, sender, use_tls = get_config()

    if not (host and sender):
        return ("Email is not configured. Set SMTP_HOST and SMTP_USERNAME/"
                "SMTP_PASSWORD (or SMTP_FROM) in .env.")

    recipients = [r for r in recipients if r]
    if not recipients:
        return "No recipients."

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        return f"Email send failed: {error}"

    return None
