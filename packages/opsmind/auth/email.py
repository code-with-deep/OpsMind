"""Minimal transactional email (SMTP, with dev log fallback)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_email(
    *,
    to_address: str,
    subject: str,
    body_text: str,
    from_address: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_username: str = "",
    smtp_password: str = "",
    smtp_use_tls: bool = True,
) -> None:
    """Send a plain-text email. If SMTP host is unset, log the message (dev)."""
    to_address = (to_address or "").strip()
    if not to_address:
        raise ValueError("to_address is required")

    host = (smtp_host or "").strip()
    if not host:
        logger.info(
            "email_dev_fallback to=%s subject=%s\n%s",
            to_address,
            subject,
            body_text,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_address or "noreply@opsmind.local"
    msg["To"] = to_address
    msg.set_content(body_text)

    if smtp_use_tls:
        with smtplib.SMTP(host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if smtp_username:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, smtp_port, timeout=30) as server:
            if smtp_username:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)


def build_password_reset_email(
    *,
    reset_url: str,
    ttl_minutes: int,
    app_name: str = "OpsMind",
) -> tuple[str, str]:
    subject = f"Reset your {app_name} password"
    body = (
        f"You requested a password reset for your {app_name} account.\n\n"
        f"Open this link to choose a new password (expires in {ttl_minutes} minutes):\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    return subject, body
