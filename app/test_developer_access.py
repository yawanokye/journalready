import hashlib
import importlib


def _configure(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_ENABLED", "1")
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_EMAIL", "developer@example.com")
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_CODE_SHA256", hashlib.sha256(b"482731").hexdigest())
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_SECRET", "test-signing-secret-that-is-long-enough")
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_SESSION_HOURS", "2")


def test_developer_token_is_signed_and_valid(monkeypatch):
    _configure(monkeypatch)
    from app import developer_access
    token = developer_access.issue_developer_token("developer@example.com")
    claims = developer_access.validate_developer_token(token["developer_token"])
    assert claims is not None
    assert claims["scope"] == "all_paid_actions"
    assert claims["email"] == "developer@example.com"
    assert developer_access.validate_developer_token(token["developer_token"] + "x") is None


def test_developer_access_bypasses_payment_claim(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("ARTICLEREADY_PAYMENT_REQUIRED", "1")
    from app import developer_access
    token = developer_access.issue_developer_token("developer@example.com")["developer_token"]
    from app.payments import guard
    importlib.reload(guard)
    with guard.paid_article_action(
        purchase_id="",
        access_token="",
        developer_token=token,
        action="draft",
    ) as claim:
        assert claim["developer_access"] is True
        assert claim["payment_bypass"] is True
        assert claim["claimed"] is False
