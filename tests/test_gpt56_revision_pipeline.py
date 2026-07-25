from __future__ import annotations

import json
from types import SimpleNamespace


def test_gpt56_model_guard_rejects_old_family(monkeypatch):
    from app.article_service import _normalise_gpt56_model

    monkeypatch.setenv("ARTICLEREADY_ALLOW_NON_GPT56_MODELS", "0")
    assert _normalise_gpt56_model("gpt-5.1", "gpt-5.6-terra") == "gpt-5.6-terra"
    assert _normalise_gpt56_model("gpt-5-mini", "") == ""
    assert _normalise_gpt56_model("gpt-5.6-luna", "gpt-5.6-terra") == "gpt-5.6-luna"


def test_responses_request_sends_xhigh_reasoning(monkeypatch):
    from app.article_service import _call_openai_response_with_fallback

    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text="completed", status="completed", id="resp-test")

    class Client:
        responses = Responses()

        def with_options(self, **kwargs):
            self.options = kwargs
            return self

    monkeypatch.setenv("OPENAI_ARTICLEREADY_ATTEMPTS_PER_MODEL", "1")
    text, model, notes = _call_openai_response_with_fallback(
        Client(),
        primary_model="gpt-5.6-terra",
        fallback_model="gpt-5.6-sol",
        instructions="Revise.",
        input_payload={"article": "text"},
        max_output_tokens=1000,
        reasoning_effort="xhigh",
        recovery_reasoning_effort="high",
        include_configured_fallbacks=False,
        request_timeout_seconds=600,
        purpose="test_revision",
    )
    assert text == "completed"
    assert model == "gpt-5.6-terra"
    assert notes == []
    assert calls[0]["reasoning"] == {"effort": "xhigh"}
    assert calls[0]["store"] is False


def test_long_manuscript_is_split_into_revision_batches(monkeypatch):
    from app.article_revision_service import _split_revision_batches

    monkeypatch.setenv("ARTICLEREADY_REVISION_SECTION_MAX_WORDS", "900")
    body = " ".join(["evidence"] * 1050)
    article = f"# Title\n\n## Introduction\n\n{body}\n\n## Methods\n\n{body}\n\n## References\n\nAdam (2025). Example."
    batches = _split_revision_batches(article)
    assert len(batches) >= 4
    assert any(item["protected"] for item in batches)
    assert all(item["word_count"] > 0 for item in batches)


def test_batched_revision_pipeline_uses_terra_and_luna(monkeypatch):
    from app import article_revision_service as service

    monkeypatch.setenv("ARTICLEREADY_REVISION_BATCH_THRESHOLD_WORDS", "1800")
    monkeypatch.setenv("ARTICLEREADY_REVISION_SECTION_MAX_WORDS", "900")
    monkeypatch.setenv("ARTICLEREADY_ALLOW_REVISION_FALLBACK", "0")
    monkeypatch.setenv("ARTICLEREADY_HUMANIZER_MODE", "off")

    body = " ".join(["This section presents confirmed evidence for procurement integrity."] * 210)
    article = (
        "# Procurement integrity\n\n"
        f"## Introduction\n\n{body}\n\n"
        f"## Methods\n\n{body}\n\n"
        f"## Results\n\n{body}\n\n"
        "## References\n\nAdam, A. (2025). Example reference."
    )

    monkeypatch.setattr(service, "_search_sources", lambda payload: ([], [], {"provider_errors": []}))
    monkeypatch.setattr(service, "_safe_get_openai_client", lambda timeout=None: object())
    monkeypatch.setattr(
        service,
        "_humanize_article_with_model",
        lambda client, text, payload, provider_errors: (text, {"mode": "off", "applied": False}, []),
    )

    purposes = []

    def fake_call(client, **kwargs):
        purpose = kwargs.get("purpose", "")
        purposes.append((purpose, kwargs.get("primary_model"), kwargs.get("reasoning_effort")))
        data = json.loads(kwargs["input_payload"])
        if purpose == "revision_plan":
            return "# Revision Plan\n\nStrengthen the contribution and preserve results.", "gpt-5.6-luna", []
        if purpose.startswith("revision_section_"):
            original = data["original_section"]
            revised = original.replace("This section", "This revised section", 1)
            return revised, "gpt-5.6-terra", []
        if purpose == "revision_report":
            return "# Revision and Publishability Report\n\nA substantive revision was completed.", "gpt-5.6-terra", []
        if purpose == "reviewer_response_matrix":
            return "| Reviewer comment | Revision made | Location | Remaining action |\n|---|---|---|---|", "gpt-5.6-luna", []
        raise AssertionError(purpose)

    monkeypatch.setattr(service, "_call_openai_response_with_fallback", fake_call)

    result = service.revise_article(
        {
            "article_title": "Procurement integrity",
            "article_text": article,
            "article_type": "Conceptual article",
            "include_source_search": False,
            "review_comments": "Clarify the contribution.",
            "humanizer_mode": "off",
        }
    )

    assert result["mode"] == "ai_revision"
    assert result["revision_batching_applied"] is True
    assert result["revision_batch_count"] >= 3
    assert "gpt-5.6-terra" in result["revision_models_used"]
    assert "gpt-5.6-luna" in result["revision_models_used"]
    assert result["reasoning_effort"] == "xhigh"
    assert any(item[0] == "revision_plan" and item[1] == "gpt-5.6-luna" for item in purposes)
    assert any(item[0].startswith("revision_section_") and item[1] == "gpt-5.6-terra" for item in purposes)



def test_startup_model_validation_fails_on_stale_old_model(monkeypatch):
    from app.article_service import validate_gpt56_configuration

    monkeypatch.setenv("ARTICLEREADY_ALLOW_NON_GPT56_MODELS", "0")
    monkeypatch.setenv("OPENAI_ARTICLE_REVISION_MODEL", "gpt-5.1")
    import pytest
    with pytest.raises(RuntimeError, match="GPT-5.6 family"):
        validate_gpt56_configuration()


def test_startup_model_validation_accepts_gpt56_routing(monkeypatch):
    from app.article_service import validate_gpt56_configuration

    monkeypatch.setenv("ARTICLEREADY_ALLOW_NON_GPT56_MODELS", "0")
    monkeypatch.setenv("OPENAI_ARTICLE_REVISION_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("OPENAI_ARTICLE_FAST_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("OPENAI_ARTICLE_ESCALATION_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("OPENAI_ARTICLE_FALLBACK_MODELS", "gpt-5.6-terra,gpt-5.6-sol")
    configured = validate_gpt56_configuration()
    assert configured["OPENAI_ARTICLE_REVISION_MODEL"] == "gpt-5.6-terra"
