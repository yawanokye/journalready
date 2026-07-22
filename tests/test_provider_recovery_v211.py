from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from app.academic_ai_engine import _audit_issue_batch_limit
from app.ai_config import HybridAIConfig
from app.ai_providers import AIProviderError, OpenAIProvider
from app.model_router import CostAwareAIProvider, ProviderName, ReviewStage, RouteTarget, _CircuitState
from app.supervisory_accuracy_guard import deterministic_expert_issues


class Payload(BaseModel):
    judgement: str


def _config(monkeypatch) -> HybridAIConfig:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "true")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "false")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "true")
    monkeypatch.setenv("AI_STRUCTURED_OUTPUT_RETRIES", "1")
    monkeypatch.setenv("AI_MAX_OUTPUT_TOKENS", "12000")
    return HybridAIConfig.from_env()


def test_deterministic_expert_interface_accepts_submission_scope():
    rows = [{
        "paragraph_id": "P1",
        "paragraph": 1,
        "text": "This is a chapter-only review.",
        "document_role": "current",
        "chapter_number": 1,
        "section_reference": "Introduction",
    }]
    assert deterministic_expert_issues(
        rows,
        academic_level="Bachelors",
        research_approach="quantitative",
        submission_scope="chapter",
    ) == []


def test_truncation_does_not_open_provider_circuit(monkeypatch):
    config = _config(monkeypatch)
    router = CostAwareAIProvider(config)
    _CircuitState.success(ProviderName.OPENAI)

    async def truncated(**kwargs):
        raise AIProviderError(
            "OpenAI output was truncated because the output-token limit was reached."
        )

    monkeypatch.setattr(router.openai, "complete_json", truncated)
    for _ in range(4):
        with pytest.raises(AIProviderError, match="truncated"):
            asyncio.run(router.complete_json(
                model=config.openai_chapter_model,
                system_prompt="Review.",
                user_prompt="Review P1.",
                schema_model=Payload,
                purpose="audit",
                stage=ReviewStage.FINAL_AUDIT,
                review_depth="standard",
            ))
    assert _CircuitState.available(ProviderName.OPENAI)
    assert _CircuitState.failures[ProviderName.OPENAI] == 0


def test_same_model_is_not_used_as_provider_fallback(monkeypatch):
    config = _config(monkeypatch)
    router = CostAwareAIProvider(config)
    primary = RouteTarget(ProviderName.OPENAI, "gpt-5.6-terra", "medium")
    same_model = RouteTarget(ProviderName.OPENAI, "gpt-5.6-terra", "high")
    selected, fallback, _ = router._normalise_targets(primary, same_model, None)
    assert selected == primary
    assert fallback is None


def test_audit_batch_limit_is_token_safe(monkeypatch):
    monkeypatch.setenv("AI_FAST_AUDIT_BATCH_ISSUE_LIMIT", "100")
    monkeypatch.setenv("AI_VERIFICATION_BATCH_SIZE", "12")
    config = _config(monkeypatch)
    assert _audit_issue_batch_limit(
        depth="standard", audit_tokens=3200, config=config
    ) == 7
    assert _audit_issue_batch_limit(
        depth="standard", audit_tokens=6000, config=config
    ) == 12


def test_openai_truncation_retry_expands_output_budget(monkeypatch):
    config = _config(monkeypatch)
    payloads = []

    async def fake_post_json_with_retry(**kwargs):
        payloads.append(kwargs["payload"])
        if len(payloads) == 1:
            return ({
                "id": "first",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            }, "first")
        return ({
            "id": "second",
            "status": "completed",
            "output": [{"type": "message", "content": [{
                "type": "output_text",
                "text": '{"judgement":"complete"}',
            }]}],
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }, "second")

    monkeypatch.setattr("app.ai_providers._post_json_with_retry", fake_post_json_with_retry)
    result = asyncio.run(OpenAIProvider(config).complete_json(
        model="gpt-5.6-terra",
        system_prompt="Return JSON.",
        user_prompt="Audit the findings.",
        schema_model=Payload,
        purpose="truncation_retry",
        max_output_tokens=3200,
        request_max_retries=0,
    ))
    assert result.data == {"judgement": "complete"}
    assert payloads[0]["max_output_tokens"] == 3200
    assert payloads[1]["max_output_tokens"] == 6400
