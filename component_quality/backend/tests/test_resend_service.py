import pytest

from src.api.services import resend_service


class FakeEmails:
    calls = []
    response = {"id": "resend_msg_123"}
    error = None

    @classmethod
    def send(cls, payload):
        cls.calls.append(payload)
        if cls.error is not None:
            raise cls.error
        return cls.response


class FakeResend:
    api_key = None
    Emails = FakeEmails


@pytest.fixture(autouse=True)
def fake_resend(monkeypatch):
    FakeEmails.calls = []
    FakeEmails.response = {"id": "resend_msg_123"}
    FakeEmails.error = None
    FakeResend.api_key = None
    monkeypatch.setattr(resend_service, "resend", FakeResend)
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "resend-secret")
    monkeypatch.setenv("EMAIL_FROM", "ResearchPilot <onboarding@resend.dev>")
    for key in (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM_EMAIL",
        "SMTP_USE_TLS",
    ):
        monkeypatch.delenv(key, raising=False)


def send_sample_feedback():
    return resend_service.send_feedback_email(
        recipient_email="student@example.test",
        subject="ResearchPilot Final Feedback Report",
        body="Please review your final feedback.",
        attachments=[
            resend_service.EmailAttachment(
                filename="ResearchPilot_Final_Feedback.pdf",
                content=b"%PDF-test",
                content_type="application/pdf",
            )
        ],
    )


def test_successful_resend_delivery_returns_provider_message_id():
    message_id = send_sample_feedback()

    assert message_id == "resend_msg_123"
    assert FakeResend.api_key == "resend-secret"


def test_resend_payload_uses_student_recipient_sender_and_base64_pdf_attachment():
    send_sample_feedback()

    payload = FakeEmails.calls[0]
    assert payload["from"] == "ResearchPilot <onboarding@resend.dev>"
    assert payload["to"] == ["student@example.test"]
    assert payload["subject"] == "ResearchPilot Final Feedback Report"
    assert payload["text"] == "Please review your final feedback."
    assert payload["html"] == "Please review your final feedback."
    assert payload["attachments"] == [
        {
            "filename": "ResearchPilot_Final_Feedback.pdf",
            "content": "JVBERi10ZXN0",
        }
    ]


def test_no_smtp_variables_are_required():
    resend_service.validate_configuration()

    assert resend_service.is_configured() is True
    assert resend_service.smtp_configured() is False


def test_missing_api_key_reports_configuration_error_without_smtp(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(resend_service.EmailDeliveryNotConfigured) as exc_info:
        resend_service.validate_configuration()

    assert "RESEND_API_KEY" in str(exc_info.value)
    assert "SMTP_HOST" not in str(exc_info.value)


def test_invalid_api_key_maps_to_authentication_error_without_secret():
    FakeEmails.error = RuntimeError("Invalid API key resend-secret")

    with pytest.raises(resend_service.EmailAuthenticationError) as exc_info:
        send_sample_feedback()

    assert str(exc_info.value) == "Resend authentication failed. Check RESEND_API_KEY."
    assert "resend-secret" not in str(exc_info.value)


def test_restricted_onboarding_sender_maps_to_recipient_restriction():
    FakeEmails.error = RuntimeError("onboarding@resend.dev can only send emails to your own email address")

    with pytest.raises(resend_service.EmailRecipientRestrictionError) as exc_info:
        send_sample_feedback()

    assert str(exc_info.value) == "The Resend testing sender can only deliver to the email address associated with the Resend account."


def test_rejected_sender_maps_to_sender_verification_error():
    FakeEmails.error = RuntimeError("sender domain is not verified")

    with pytest.raises(resend_service.EmailSenderVerificationError) as exc_info:
        send_sample_feedback()

    assert str(exc_info.value) == "Resend rejected EMAIL_FROM or the sending domain."


def test_generic_message_containing_from_or_to_is_not_misclassified():
    FakeEmails.error = RuntimeError("provider moved message from queue to retry queue resend-secret")

    with pytest.raises(resend_service.EmailDeliveryError) as exc_info:
        send_sample_feedback()

    assert not isinstance(exc_info.value, resend_service.EmailSenderVerificationError)
    assert not isinstance(exc_info.value, resend_service.EmailRecipientRestrictionError)
    assert str(exc_info.value) == "Resend provider request failed: provider moved message from queue to retry queue [redacted]"


def test_missing_provider_message_id_is_failure():
    FakeEmails.response = {"ok": True}

    with pytest.raises(resend_service.EmailDeliveryError) as exc_info:
        send_sample_feedback()

    assert str(exc_info.value) == "Resend did not return a message ID."
