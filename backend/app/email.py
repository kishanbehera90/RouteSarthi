"""Transactional email via Brevo's HTTPS API (v3/smtp/email) — NOT raw SMTP.

Render's free tier blocks outbound traffic to SMTP ports 25/465/587 entirely
(since Sep 2025), so a raw smtplib connection just hangs until timeout there,
regardless of how correct the credentials are. The HTTPS API travels over 443,
which is never blocked, so this is the actual fix for that host, not a
workaround. It also happens to need no new dependency — httpx is already used
elsewhere (app/roads.py).
"""
import httpx

from .config import settings

_API_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 10  # seconds — an email provider hiccup must never hang the request


def send_reset_email(to: str, reset_link: str) -> bool:
    """Best-effort: returns False (and logs) on any failure rather than
    raising — a flaky email provider shouldn't 500 the reset endpoint, which
    must always respond 200 regardless (no email-enumeration)."""
    if not settings.brevo_api_key or not settings.smtp_from_email:
        print("Brevo not configured — skipping reset email (link:", reset_link, ")")
        return False
    payload = {
        "sender": {"email": settings.smtp_from_email, "name": "RouteSarthi"},
        "to": [{"email": to}],
        "subject": "Reset your RouteSarthi password",
        "textContent": (
            f"Someone requested a password reset for this email.\n\n"
            f"Reset your password: {reset_link}\n"
            f"(link expires in 1 hour)\n\n"
            f"If this wasn't you, you can safely ignore this email."
        ),
        "htmlContent": (
            f"<p>Someone requested a password reset for this email.</p>"
            f"<p><a href=\"{reset_link}\">Reset your password</a> "
            f"(link expires in 1 hour).</p>"
            f"<p>If this wasn't you, you can safely ignore this email.</p>"
        ),
    }
    try:
        r = httpx.post(
            _API_URL,
            json=payload,
            headers={"api-key": settings.brevo_api_key, "content-type": "application/json"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        print("send_reset_email failed:", e)
        return False
