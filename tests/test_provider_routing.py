from __future__ import annotations

from pathlib import Path

from app.ai_config import AIConfigurationError, HybridAIConfig
from app.academic_ai_engine import _batch_model_route
from app.model_router import CostAwareAIProvider, ProviderName, ReviewStage


def _clear_router_env(monkeypatch):
    for name in (
        "VPROF_ROUTING_PROFILE",
        "VPROF_ENABLE_OPENAI",
        "VPROF_ENABLE_DEEPSEEK",
        "VPROF_ENABLE_SELECTIVE_ESCALATION",
        "DEEPSEEK_FAST_MODEL",
        "DEEPSEEK_QUALITY_MODEL",
        "OPENAI_REVIEW_MODEL",
        "OPENAI_REVIEW_REASONING_EFFORT",
        "OPENAI_CHAPTER_MODEL",
        "OPENAI_EXPERT_MODEL",
        "OPENAI_FINAL_AUDIT_MODEL",
        "OPENAI_EXTERNAL_MODEL",
        "OPENAI_EXTERNAL_DOMAIN_MODEL",
        "OPENAI_EXTERNAL_ADJUDICATOR_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_balanced_defaults_enable_cost_aware_routing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    _clear_router_env(monkeypatch)
    config = HybridAIConfig.from_env()

    assert config.resolve_mode("light") == "light"
    assert config.resolve_mode("standard") == "standard"
    assert config.resolve_mode("advanced") == "advanced"
    assert config.routing_profile == "quality"
    assert config.enable_deepseek_routing is False
    assert config.deepseek_fast_model == "deepseek-v4-flash"
    assert config.deepseek_quality_model == "deepseek-v4-pro"
    assert config.openai_chapter_model == "gpt-5.6-terra"
    assert config.openai_expert_model == "gpt-5.6-terra"
    assert config.openai_external_domain_model == "gpt-5.6-terra"
    assert config.openai_external_adjudicator_model == "gpt-5.6-terra"
    status = config.public_status()
    assert status["review_depths"] == ["light", "standard", "advanced"]
    assert "provider" not in status
    assert "model" not in status


def test_deepseek_can_keep_normal_reviews_available_without_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    _clear_router_env(monkeypatch)
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    config = HybridAIConfig.from_env()
    for depth in ("light", "standard", "advanced"):
        assert config.resolve_mode(depth) == depth


def test_all_depths_fail_without_any_enabled_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _clear_router_env(monkeypatch)
    config = HybridAIConfig.from_env()
    for depth in ("light", "standard", "advanced"):
        try:
            config.resolve_mode(depth)
            assert False, f"{depth} should require an enabled provider."
        except AIConfigurationError:
            pass


def test_research_intensive_sections_keep_expert_route_hint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    config = HybridAIConfig.from_env()
    methods = [{"heading": "Research Methods", "section_path": [], "paragraphs": []}]
    literature = [{"heading": "Definition of Terms", "section_path": [], "paragraphs": []}]

    assert _batch_model_route(methods, "Research Masters (MPhil)", config) == (
        "gpt-5.6-terra",
        "high",
    )
    assert _batch_model_route(literature, "Research Masters (MPhil)", config) == (
        "gpt-5.6-terra",
        "medium",
    )


def test_balanced_route_plans(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    _clear_router_env(monkeypatch)
    config = HybridAIConfig.from_env()
    router = CostAwareAIProvider(config)

    standard = router.plan(stage=ReviewStage.STANDARD_REVIEW)
    assert standard.primary.provider is ProviderName.OPENAI
    assert standard.primary.model == "gpt-5.6-terra"
    assert standard.escalation is not None
    assert standard.escalation.model == "gpt-5.6-terra"

    advanced = router.plan(
        stage=ReviewStage.ADVANCED_REVIEW,
        requested_model=config.openai_expert_model,
        requested_effort=config.openai_expert_reasoning_effort,
    )
    assert advanced.primary.provider is ProviderName.OPENAI
    assert advanced.primary.model == "gpt-5.6-terra"
    assert advanced.escalation is None

    external = router.plan(
        stage=ReviewStage.EXTERNAL_EXAMINATION,
        requested_model=config.openai_external_adjudicator_model,
        requested_effort=config.openai_external_adjudicator_reasoning_effort,
    )
    assert external.primary.provider is ProviderName.OPENAI
    assert external.primary.model == "gpt-5.6-terra"
    assert external.allow_escalation is False


def test_academic_engine_uses_integrated_router_and_expert_audit():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    assert "provider = router" in source
    assert "CostAwareAIProvider" in source
    assert "_batch_model_route(batch, academic_level, config)" in source
    assert "universal_comment_accuracy_audit" in source
    assert "focused_comment_accuracy_retry" in source
    assert "_degree_audit_settings" in source
    assert '"active_provider": "cost_aware_router"' in source
