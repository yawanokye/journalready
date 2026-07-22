from pathlib import Path
import hashlib
import importlib


def _configure(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_ENABLED", "1")
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_EMAIL", "developer@example.com")
    monkeypatch.setenv("ARTICLEREADY_DEVELOPER_ACCESS_CODE_SHA256", hashlib.sha256(b"246810").hexdigest())
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


def test_developer_login_accepts_exact_six_digit_code(monkeypatch):
    _configure(monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.developer_access import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/developer/login",
        json={"email": "developer@example.com", "access_code": "246810"},
    )
    assert response.status_code == 200
    assert response.json()["developer_token"]

    short_response = client.post(
        "/api/developer/login",
        json={"email": "developer@example.com", "access_code": "24681"},
    )
    assert short_response.status_code == 422


def test_developer_assets_and_paid_requests_are_wired_correctly():
    root = Path(__file__).resolve().parents[1]
    developer_html = (root / "app/static/developer_access.html").read_text(encoding="utf-8")
    developer_js = (root / "app/static/developer_access.js").read_text(encoding="utf-8")
    topic_html = (root / "app/static/topic_ideas.html").read_text(encoding="utf-8")
    topic_js = (root / "app/static/topic_ideas.js").read_text(encoding="utf-8")
    payments_js = (root / "app/static/articleready_payments.js").read_text(encoding="utf-8")

    assert "```" not in developer_html
    assert "```" not in developer_js
    assert 'pattern="[0-9]{6}"' in developer_html
    assert "authorisedFetch" in payments_js
    assert 'ArticleReadyPayments.authorisedFetch("/api/article-ideas"' in topic_js
    assert topic_html.index("articleready_payments.js") < topic_html.index("topic_ideas.js")


def test_article_ideas_route_accepts_developer_header(monkeypatch):
    _configure(monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import developer_access, routers

    monkeypatch.setattr(
        routers,
        "generate_article_ideas",
        lambda data: {"ok": True, "mode": "test", "ideas": [], "max_ideas": data.get("max_ideas")},
    )
    token = developer_access.issue_developer_token("developer@example.com")["developer_token"]

    app = FastAPI()
    app.include_router(routers.router)
    client = TestClient(app)
    response = client.post(
        "/api/article-ideas",
        headers={"x-articleready-developer-token": token},
        json={"research_area": "finance", "max_ideas": 20},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["max_ideas"] == 20
