from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.ai_config import HybridAIConfig
from app.ai_providers import ProviderResult
from app.ai_schemas import AIUsageRecord
from app.model_router import CostAwareAIProvider, ReviewStage


class RoutedPayload(BaseModel):
    confidence: float
    severity: str
    judgement: str


def _result(provider: str, model: str, confidence: float, severity: str = "moderate"):
    return ProviderResult(
        data={
            "confidence": confidence,
            "severity": severity,
            "judgement": "checked",
        },
        usage=AIUsageRecord(
            provider=provider,
            model=model,
            purpose="test",
            input_tokens=1000,
            output_tokens=200,
        ),
    )


def test_high_confidence_standard_review_uses_one_deepseek_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_ROUTING_PROFILE", "balanced")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "false")
    config = HybridAIConfig.from_env()
    router = CostAwareAIProvider(config)
    calls: list[str] = []

    async def fake_deepseek(**kwargs):
        calls.append(kwargs["model"])
        return _result("deepseek", kwargs["model"], 0.94)

    async def fake_openai(**kwargs):
        calls.append(kwargs["model"])
        return _result("openai", kwargs["model"], 0.95)

    monkeypatch.setattr(router.deepseek, "complete_json", fake_deepseek)
    monkeypatch.setattr(router.openai, "complete_json", fake_openai)

    result = asyncio.run(router.complete_json(
        model=config.openai_chapter_model,
        system_prompt="Assess accurately.",
        user_prompt="Review P1.",
        schema_model=RoutedPayload,
        purpose="standard_test",
        stage=ReviewStage.STANDARD_REVIEW,
        review_depth="standard",
    ))
    assert calls == ["deepseek-v4-flash"]
    assert result.usage.provider == "deepseek"


def test_low_confidence_standard_review_escalates_once(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_ROUTING_PROFILE", "balanced")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "false")
    config = HybridAIConfig.from_env()
    router = CostAwareAIProvider(config)
    calls: list[str] = []

    async def fake_deepseek(**kwargs):
        calls.append(kwargs["model"])
        return _result("deepseek", kwargs["model"], 0.55, "major")

    async def fake_openai(**kwargs):
        calls.append(kwargs["model"])
        return _result("openai", kwargs["model"], 0.96, "major")

    monkeypatch.setattr(router.deepseek, "complete_json", fake_deepseek)
    monkeypatch.setattr(router.openai, "complete_json", fake_openai)

    result = asyncio.run(router.complete_json(
        model=config.openai_chapter_model,
        system_prompt="Assess accurately.",
        user_prompt="Review P1.",
        schema_model=RoutedPayload,
        purpose="standard_test",
        stage=ReviewStage.STANDARD_REVIEW,
        review_depth="standard",
    ))
    assert calls == ["deepseek-v4-flash", "gpt-5.6-terra"]
    assert result.usage.provider == "routed"
    assert result.usage.model == "deepseek-v4-flash->gpt-5.6-terra"
    assert result.usage.input_tokens == 2000


def test_provider_failure_uses_low_cost_openai_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_ROUTING_PROFILE", "balanced")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "false")
    config = HybridAIConfig.from_env()
    router = CostAwareAIProvider(config)
    calls: list[str] = []

    async def failed_deepseek(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("flash unavailable")

    async def fake_openai(**kwargs):
        calls.append(kwargs["model"])
        return _result("openai", kwargs["model"], 0.95)

    monkeypatch.setattr(router.deepseek, "complete_json", failed_deepseek)
    monkeypatch.setattr(router.openai, "complete_json", fake_openai)

    result = asyncio.run(router.complete_json(
        model=config.openai_chapter_model,
        system_prompt="Assess accurately.",
        user_prompt="Review P1.",
        schema_model=RoutedPayload,
        purpose="fallback_test",
        stage=ReviewStage.STANDARD_REVIEW,
        review_depth="standard",
    ))
    assert calls == ["deepseek-v4-flash", "gpt-5.6-terra"]
    assert result.usage.provider == "openai"
