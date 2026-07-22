from app.ai_config import HybridAIConfig
from app.model_router import CostAwareAIProvider, ReviewStage, ProviderName


def _config(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('VPROF_ENABLE_OPENAI', 'true')
    monkeypatch.setenv('VPROF_ENABLE_DEEPSEEK', 'false')
    monkeypatch.setenv('VPROF_COMBINED_APP_PIPELINE', 'true')
    monkeypatch.setenv('OPENAI_CLEANING_MODEL', 'gpt-5.6-terra')
    monkeypatch.setenv('OPENAI_SECTION_ANALYSIS_MODEL', 'gpt-5.6-terra')
    monkeypatch.setenv('OPENAI_SECTION_ANALYSIS_FALLBACK_MODEL', 'gpt-5.6-terra')
    monkeypatch.setenv('OPENAI_FINAL_SYNTHESIS_MODEL', 'gpt-5.6-terra')
    monkeypatch.setenv('OPENAI_FINAL_SYNTHESIS_FALLBACK_MODEL', 'gpt-5.6-terra')
    return HybridAIConfig.from_env()


def test_phase_1_routes_to_cleaning_model(monkeypatch):
    router = CostAwareAIProvider(_config(monkeypatch))
    plan = router.plan(stage=ReviewStage.LANGUAGE_SCAN, review_depth='standard')
    assert plan.primary.provider is ProviderName.OPENAI
    assert plan.primary.model == 'gpt-5.6-terra'


def test_phase_2_routes_to_section_analysis_model(monkeypatch):
    router = CostAwareAIProvider(_config(monkeypatch))
    plan = router.plan(stage=ReviewStage.RESEARCH_INTENSIVE_REVIEW, review_depth='standard')
    assert plan.primary.provider is ProviderName.OPENAI
    assert plan.primary.model == 'gpt-5.6-terra'
    # The same provider/model must not be presented as its own fallback.
    assert plan.fallback is None


def test_phase_3_routes_to_final_synthesis_model(monkeypatch):
    router = CostAwareAIProvider(_config(monkeypatch))
    plan = router.plan(stage=ReviewStage.FINAL_AUDIT, review_depth='advanced')
    assert plan.primary.provider is ProviderName.OPENAI
    assert plan.primary.model == 'gpt-5.6-terra'
    assert plan.fallback is None
