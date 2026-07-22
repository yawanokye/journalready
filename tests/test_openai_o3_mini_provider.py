from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import BaseModel

from app.ai_config import HybridAIConfig
from app.ai_providers import AIProviderError, OpenAIProvider, _openai_output_text


class SamplePayload(BaseModel):
    judgement: str
    evidence_ids: list[str]


def test_openai_provider_uses_gpt54_mini_responses_and_strict_schema(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.delenv("OPENAI_CHAPTER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REVIEW_MODEL", raising=False)
    config = HybridAIConfig.from_env()
    captured: dict = {}

    async def fake_post_json_with_retry(**kwargs):
        captured.update(kwargs)
        return (
            {
                "id": "resp-test",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"judgement":"supported","evidence_ids":["P1"]}',
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 45,
                    "input_tokens_details": {"cached_tokens": 20},
                },
            },
            "request-header-id",
        )

    monkeypatch.setattr(
        "app.ai_providers._post_json_with_retry",
        fake_post_json_with_retry,
    )

    result = asyncio.run(
        OpenAIProvider(config).complete_json(
            model=config.openai_chapter_model,
            system_prompt="Ground every finding.",
            user_prompt="Assess paragraph P1.",
            schema_model=SamplePayload,
            purpose="provider_test",
            reasoning_effort="high",
            max_output_tokens=5000,
            request_timeout_seconds=360,
            request_max_retries=0,
        )
    )

    assert captured["url"].endswith("/responses")
    assert captured["payload"]["model"] == "gpt-5.6-terra"
    assert captured["payload"]["reasoning"] == {"effort": "high"}
    assert captured["payload"]["text"]["format"]["type"] == "json_schema"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert captured["payload"]["store"] is False
    assert captured["timeout_seconds"] == 360
    assert captured["max_retries"] == 0
    assert result.data == {"judgement": "supported", "evidence_ids": ["P1"]}
    assert result.usage.provider == "openai"
    assert result.usage.model == "gpt-5.6-terra"
    assert result.usage.cached_input_tokens == 20


def test_openai_provider_accepts_xhigh_reasoning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    config = HybridAIConfig.from_env()
    captured: dict = {}

    async def fake_post_json_with_retry(**kwargs):
        captured.update(kwargs)
        return ({
            "id": "resp-xhigh",
            "status": "completed",
            "output": [{"type": "message", "content": [{
                "type": "output_text",
                "text": '{"judgement":"supported","evidence_ids":["P1"]}',
            }]}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }, "request-xhigh")

    monkeypatch.setattr("app.ai_providers._post_json_with_retry", fake_post_json_with_retry)
    asyncio.run(OpenAIProvider(config).complete_json(
        model=config.openai_external_model,
        system_prompt="Assess.",
        user_prompt="Assess P1.",
        schema_model=SamplePayload,
        purpose="xhigh_test",
        reasoning_effort="xhigh",
    ))
    assert captured["payload"]["reasoning"] == {"effort": "xhigh"}


def test_openai_incomplete_output_is_rejected_as_truncated():
    with pytest.raises(AIProviderError, match="truncated"):
        _openai_output_text(
            {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            }
        )
