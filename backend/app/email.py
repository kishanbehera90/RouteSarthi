"""Transactional email via SMTP (Brevo's free relay). Uses Python's stdlib
smtplib/email — no new dependency for a single outbound message type.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import settings


def send_reset_email(to: str, reset_link: str) -> bool:
    """Best-effort: returns False (and logs) on any failure rather than
    raising — a flaky email provider shouldn't 500 the reset endpoint, which
    must always respond 200 regardless (no email-enumeration)."""
    if not settings.smtp_user or not settings.smtp_from_email:
        print("SMTP not configured — skipping reset email (link:", reset_link, ")")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset your RouteSarthi password"
        msg["From"] = settings.smtp_from_email
        msg["To"] = to
        msg.attach(MIMEText(
            f"Someone requested a password reset for this email.\n\n"
            f"Reset your password: {reset_link}\n"
            f"(link expires in 1 hour)\n\n"
            f"If this wasn't you, you can safely ignore this email.",
            "plain",
        ))
        msg.attach(MIMEText(
            f"<p>Someone requested a password reset for this email.</p>"
            f"<p><a href=\"{reset_link}\">Reset your password</a> "
            f"(link expires in 1 hour).</p>"
            f"<p>If this wasn't you, you can safely ignore this email.</p>",
            "html",
        ))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from_email, [to], msg.as_string())
        return True
    except Exception as e:  # noqa: BLE001
        print("send_reset_email failed:", e)
        return False
