"""Send approved email drafts through an explicitly configured local relay."""

import os
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr


def _validated_address(value: str, label: str) -> str:
    address = parseaddr(value)[1]
    if not address or "@" not in address or "\n" in value or "\r" in value:
        raise ValueError(f"A valid {label} email address is required.")
    return address


def send_approved_email(draft: dict[str, str]) -> None:
    host = os.environ.get("LOCAL_SMTP_HOST", "127.0.0.1").strip().lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Email sending is restricted to a loopback SMTP relay.")

    sender = _validated_address(os.environ.get("LOCAL_SMTP_FROM", ""), "sender")
    recipient = _validated_address(draft.get("to", ""), "recipient")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = draft.get("subject", "")
    message.set_content(draft.get("body", ""))

    port = int(os.environ.get("LOCAL_SMTP_PORT", "1025"))
    with smtplib.SMTP(host, port, timeout=10) as relay:
        relay.send_message(message)