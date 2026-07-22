from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel

from app.ai_config import HybridAIConfig
from app.ai_providers import DeepSeekProvider
import app.ai_providers as providers


class TinyPayload(BaseModel):
    ok: bool


def test_deepseek_thinking_payload_uses_official_top_level_effort(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    config = HybridAIConfig.from_env()
    provider = DeepSeekProvider(config)
    captured = {}

    async def fake_post(**kwargs):
        captured.update(kwargs["payload"])
        return (
            {
                "id": "ds-test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"ok": True})},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
            "request-test",
        )

    monkeypatch.setattr(providers, "_post_json_with_retry", fake_post)

    asyncio.run(
        provider.complete_json(
            model="deepseek-v4-pro",
            system_prompt="Return JSON.",
            user_prompt="Check.",
            schema_model=TinyPayload,
            purpose="payload_test",
            reasoning_effort="high",
            thinking_enabled=True,
        )
    )

    assert captured["thinking"] == {"type": "enabled"}
    assert captured["reasoning_effort"] == "high"
    assert "reasoning_effort" not in captured["thinking"]


def test_deepseek_fast_mode_disables_thinking_and_omits_effort(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    config = HybridAIConfig.from_env()
    provider = DeepSeekProvider(config)
    captured = {}

    async def fake_post(**kwargs):
        captured.update(kwargs["payload"])
        return (
            {
                "id": "ds-test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"ok": True})},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
            "request-test",
        )

    monkeypatch.setattr(providers, "_post_json_with_retry", fake_post)

    asyncio.run(
        provider.complete_json(
            model="deepseek-v4-flash",
            system_prompt="Return JSON.",
            user_prompt="Check.",
            schema_model=TinyPayload,
            purpose="payload_test",
            reasoning_effort="high",
            thinking_enabled=False,
        )
    )

    assert captured["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in captured


def test_fast_review_audit_defaults_are_bounded(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    config = HybridAIConfig.from_env()

    assert config.fast_audit_max_batches == 1
    assert config.fast_audit_batch_issue_limit == 6
    assert config.standard_audit_max_output_tokens <= 4000
    assert config.light_audit_max_output_tokens <= 3000
