from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel

import app.ai_providers as providers
from app.ai_config import HybridAIConfig
from app.ai_providers import AIProviderError, DeepSeekProvider
from app.coverage_review import split_coverage_units_to_single_targets
from app.model_router import CostAwareAIProvider, ReviewStage


class TinyPayload(BaseModel):
    ok: bool


def _config(monkeypatch) -> HybridAIConfig:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "false")
    monkeypatch.setenv("VPROF_PRIMARY_PROVIDER", "deepseek")
    monkeypatch.setenv("VPROF_FALLBACK_PROVIDER", "none")
    monkeypatch.setenv("VPROF_PROVIDER_FAILOVER", "false")
    monkeypatch.setenv("AI_STRUCTURED_OUTPUT_RETRIES", "1")
    monkeypatch.setenv("DEEPSEEK_PRIMARY_THINKING_ENABLED", "false")
    monkeypatch.setenv("DEEPSEEK_AUDIT_THINKING_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_TRUNCATION_RECOVERY", "true")
    monkeypatch.setenv("DEEPSEEK_TRUNCATION_RETRY_MULTIPLIER", "1.6")
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "12000")
    return HybridAIConfig.from_env()


def test_primary_packet_truncation_is_not_retried_at_same_size(monkeypatch):
    config = _config(monkeypatch)
    payloads = []

    async def fake_post_json_with_retry(**kwargs):
        payloads.append(kwargs["payload"])
        return ({
            "id": "first",
            "choices": [{
                "finish_reason": "length",
                "message": {"content": "{\"ok\":"},
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 3200},
        }, "first")

    monkeypatch.setattr(providers, "_post_json_with_retry", fake_post_json_with_retry)
    with pytest.raises(AIProviderError, match="truncated"):
        asyncio.run(DeepSeekProvider(config).complete_json(
            model="deepseek-v4-pro",
            system_prompt="Return JSON.",
            user_prompt="Review the packet.",
            schema_model=TinyPayload,
            purpose="batched_academic_review",
            reasoning_effort="max",
            max_output_tokens=3200,
            thinking_enabled=False,
            request_max_retries=0,
        ))

    assert len(payloads) == 1
    assert payloads[0]["max_tokens"] == 3200


def test_bounded_audit_truncation_retry_expands_budget(monkeypatch):
    config = _config(monkeypatch)
    payloads = []

    async def fake_post_json_with_retry(**kwargs):
        payloads.append(kwargs["payload"])
        if len(payloads) == 1:
            return ({
                "id": "first",
                "choices": [{
                    "finish_reason": "length",
                    "message": {"content": "{\"ok\":"},
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 3200},
            }, "first")
        return ({
            "id": "second",
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps({"ok": True})},
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 8},
        }, "second")

    monkeypatch.setattr(providers, "_post_json_with_retry", fake_post_json_with_retry)
    result = asyncio.run(DeepSeekProvider(config).complete_json(
        model="deepseek-v4-pro",
        system_prompt="Return JSON.",
        user_prompt="Audit the findings.",
        schema_model=TinyPayload,
        purpose="final_audit",
        reasoning_effort="max",
        max_output_tokens=3200,
        thinking_enabled=True,
        request_max_retries=0,
    ))

    assert result.data == {"ok": True}
    assert len(payloads) == 2
    assert payloads[1]["max_tokens"] > 3200
    assert payloads[1]["max_tokens"] <= 12000
    assert payloads[1]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in payloads[1]


def test_deepseek_standard_packets_disable_thinking_but_audits_keep_it(monkeypatch):
    config = _config(monkeypatch)
    router = CostAwareAIProvider(config)

    standard = router.plan(stage=ReviewStage.STANDARD_REVIEW)
    intensive = router.plan(stage=ReviewStage.RESEARCH_INTENSIVE_REVIEW)
    audit = router.plan(stage=ReviewStage.FINAL_AUDIT)

    assert standard.primary.thinking_enabled is False
    assert intensive.primary.thinking_enabled is False
    assert audit.primary.thinking_enabled is True


def test_deepseek_packet_defaults_are_compact_and_cost_bounded(monkeypatch):
    config = _config(monkeypatch)
    assert config.deepseek_coverage_units_per_request == 1
    assert config.deepseek_coverage_high_risk_units_per_request == 1
    assert config.deepseek_coverage_request_max_chars == 9000
    assert config.deepseek_coverage_prose_paragraphs_per_unit == 3
    assert config.deepseek_coverage_unit_max_chars == 7000
    assert config.deepseek_primary_max_output_tokens == 7000
    assert config.deepseek_single_target_recovery_max_output_tokens == 4200
    assert config.deepseek_compact_issue_limit_per_target == 2


def test_truncated_unit_splits_into_single_target_recovery_units():
    unit = {
        "section_key": "S001P01",
        "heading": "Problem Statement",
        "coverage_unit": True,
        "target_paragraph_ids": ["P1", "P2", "P3"],
        "paragraphs": [
            {"paragraph": 1, "text": "First target."},
            {"paragraph": 2, "text": "Second target."},
            {"paragraph": 3, "text": "Third target."},
        ],
    }
    split = split_coverage_units_to_single_targets([unit], context_paragraphs=1)
    assert [row["target_paragraph_ids"] for row in split] == [["P1"], ["P2"], ["P3"]]
    assert all(row["parent_section_key"] == "S001P01" for row in split)
    assert all(row["parent_target_paragraph_ids"] == ["P1", "P2", "P3"] for row in split)
