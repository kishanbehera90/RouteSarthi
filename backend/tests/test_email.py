"""Unit tests for app.email — the Brevo HTTPS-API password-reset sender. Pure
with a mocked HTTP layer; no live network or DB needed. Verifies the
not-configured no-op and failure paths never raise (send_trip_id's caller,
the always-200 forgot-password endpoint, depends on that contract)."""
import pytest

from app import email


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_noop_when_not_configured(monkeypatch):
    monkeypatch.setattr(email.settings, "brevo_api_key", "")
    monkeypatch.setattr(email.settings, "smtp_from_email", "")
    assert email.send_reset_email("a@b.com", "http://x/reset?token=abc") is False


def test_noop_when_sender_missing(monkeypatch):
    monkeypatch.setattr(email.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(email.settings, "smtp_from_email", "")
    assert email.send_reset_email("a@b.com", "http://x/reset?token=abc") is False


def test_sends_via_https_api_when_configured(monkeypatch):
    monkeypatch.setattr(email.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(email.settings, "smtp_from_email", "noreply@routesarthi.app")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(201)

    monkeypatch.setattr(email.httpx, "post", fake_post)
    assert email.send_reset_email("a@b.com", "http://x/reset?token=abc") is True
    url, kwargs = calls[0]
    assert url == "https://api.brevo.com/v3/smtp/email"
    assert kwargs["headers"]["api-key"] == "test-key"
    assert kwargs["json"]["to"] == [{"email": "a@b.com"}]
    assert "http://x/reset?token=abc" in kwargs["json"]["htmlContent"]


def test_returns_false_on_api_error_never_raises(monkeypatch):
    monkeypatch.setattr(email.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(email.settings, "smtp_from_email", "noreply@routesarthi.app")
    monkeypatch.setattr(email.httpx, "post", lambda *a, **k: _FakeResponse(401))
    assert email.send_reset_email("a@b.com", "http://x/reset") is False


def test_returns_false_on_network_error_never_raises(monkeypatch):
    monkeypatch.setattr(email.settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(email.settings, "smtp_from_email", "noreply@routesarthi.app")

    def boom(*a, **k):
        raise ConnectionError("timed out")

    monkeypatch.setattr(email.httpx, "post", boom)
    assert email.send_reset_email("a@b.com", "http://x/reset") is False
