import os

from app.ai_config import HybridAIConfig
from app.model_router import CostAwareAIProvider, ReviewStage


def test_deepseek_v4_pro_only_routes_supervisory_stages(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "false")
    monkeypatch.setenv("VPROF_EXPERT_PROVIDER_MODE", "deepseek_v4_pro_only")
    monkeypatch.setenv("VPROF_FORCE_DEEPSEEK_V4_PRO", "true")
    monkeypatch.setenv("DEEPSEEK_QUALITY_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_ADVANCED_PRIMARY_REASONING_EFFORT", "max")

    config = HybridAIConfig.from_env()
    router = CostAwareAIProvider(config)

    for stage in (
        ReviewStage.STANDARD_REVIEW,
        ReviewStage.RESEARCH_INTENSIVE_REVIEW,
        ReviewStage.RESEARCH_INTENSIVE_AUDIT,
        ReviewStage.FINAL_AUDIT,
        ReviewStage.STRUCTURE_MAP,
    ):
        plan = router.plan(stage=stage)
        assert plan.primary.provider.value == "deepseek"
        assert plan.primary.model == "deepseek-v4-pro"
        assert plan.fallback is None
        assert plan.escalation is None
        assert plan.allow_escalation is False
