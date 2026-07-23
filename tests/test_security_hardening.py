from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_public_security_files_and_headers(monkeypatch):
    monkeypatch.setenv("ARTICLEREADY_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers.get("x-request-id")

        robots = client.get("/robots.txt")
        assert robots.status_code == 200
        assert "Disallow: /api/" in robots.text

        favicon = client.get("/favicon.ico")
        assert favicon.status_code == 200
        assert favicon.headers["content-type"].startswith("image/x-icon")

        private_page = client.get("/review-evidence")
        assert private_page.status_code == 200
        assert "noindex,nofollow,noarchive" in private_page.text
        assert private_page.headers["cache-control"].startswith("no-store")


def test_openai_call_sets_store_false_and_uses_configured_model(monkeypatch):
    from app.article_service import _call_openai_response_with_fallback

    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text="revised text")

    client = SimpleNamespace(responses=Responses())
    monkeypatch.setenv("OPENAI_ARTICLE_FALLBACK_MODELS", "gpt-5-mini")
    text, model, notes = _call_openai_response_with_fallback(
        client,
        primary_model="account-model",
        instructions="Revise.",
        input_payload=json.dumps({"article": "text"}),
        max_output_tokens=1000,
    )
    assert text == "revised text"
    assert model == "account-model"
    assert notes == []
    assert calls[0]["store"] is False


def test_semantic_scholar_api_key_is_sent(monkeypatch):
    from app import source_finder

    captured = {}

    def fake_get_json(url, *, extra_headers=None):
        captured["url"] = url
        captured["headers"] = extra_headers
        return {"data": []}

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "test-key")
    monkeypatch.setattr(source_finder, "_get_json", fake_get_json)
    assert source_finder._search_semantic_scholar("procurement ethics", 5) == []
    assert captured["headers"] == {"x-api-key": "test-key"}
