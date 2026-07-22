from __future__ import annotations

import pytest

from app.ai_config import AIConfigurationError, HybridAIConfig
from app.model_router import CostAwareAIProvider, ProviderName, ReviewStage
from app.review_release_guard import (
    classify_review_context,
    filter_and_rewrite_release_findings,
)
from app.thorough_review import _detected_methods


def _provider_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "true")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_COMBINED_APP_PIPELINE", "true")
    monkeypatch.setenv("DEEPSEEK_FAST_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DEEPSEEK_QUALITY_MODEL", "deepseek-v4-pro")


def test_explicit_deepseek_selection_overrides_combined_openai_pipeline(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.setenv("VPROF_PRIMARY_PROVIDER", "deepseek")
    monkeypatch.setenv("VPROF_FALLBACK_PROVIDER", "none")
    monkeypatch.setenv("VPROF_PROVIDER_FAILOVER", "false")

    router = CostAwareAIProvider(HybridAIConfig.from_env())
    utility = router.plan(stage=ReviewStage.STRUCTURE_MAP)
    standard = router.plan(stage=ReviewStage.STANDARD_REVIEW)
    final_audit = router.plan(stage=ReviewStage.FINAL_AUDIT)

    assert utility.primary.provider is ProviderName.DEEPSEEK
    assert utility.primary.model == "deepseek-v4-flash"
    for plan in (standard, final_audit):
        assert plan.primary.provider is ProviderName.DEEPSEEK
        assert plan.primary.model == "deepseek-v4-pro"
        assert plan.fallback is None
        assert plan.escalation is None
        assert plan.allow_escalation is False


def test_explicit_openai_selection_overrides_deepseek_and_keeps_openai_pipeline(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.setenv("VPROF_PRIMARY_PROVIDER", "openai")
    monkeypatch.setenv("VPROF_FALLBACK_PROVIDER", "none")
    monkeypatch.setenv("VPROF_PROVIDER_FAILOVER", "false")

    router = CostAwareAIProvider(HybridAIConfig.from_env())
    plan = router.plan(stage=ReviewStage.STANDARD_REVIEW)
    assert plan.primary.provider is ProviderName.OPENAI
    assert plan.primary.model == "gpt-5.6-terra"
    assert plan.fallback is None


def test_explicit_deepseek_can_fail_over_to_openai_only_when_enabled(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.setenv("VPROF_PRIMARY_PROVIDER", "deepseek")
    monkeypatch.setenv("VPROF_FALLBACK_PROVIDER", "openai")
    monkeypatch.setenv("VPROF_PROVIDER_FAILOVER", "true")

    plan = CostAwareAIProvider(HybridAIConfig.from_env()).plan(
        stage=ReviewStage.STANDARD_REVIEW
    )
    assert plan.primary.provider is ProviderName.DEEPSEEK
    assert plan.primary.model == "deepseek-v4-pro"
    assert plan.fallback is not None
    assert plan.fallback.provider is ProviderName.OPENAI


def test_explicit_provider_requires_the_selected_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")
    monkeypatch.setenv("VPROF_ENABLE_OPENAI", "true")
    monkeypatch.setenv("VPROF_ENABLE_DEEPSEEK", "true")
    monkeypatch.setenv("VPROF_PRIMARY_PROVIDER", "deepseek")

    config = HybridAIConfig.from_env()
    with pytest.raises(AIConfigurationError, match="selected Deepseek provider"):
        config.resolve_mode("standard")


def _runtime_review():
    rows = [
        {
            "chapter_number": 1,
            "section_reference": "Background to the Study",
            "section_path": ["CHAPTER ONE", "Background to the Study"],
            "paragraph_id": "C1-P1",
            "text": (
                "Fraud is a global problem. In Ghana, Bank of Ghana evidence shows the challenge. "
                "Assinman Rural Bank PLC is the specific rural-bank setting. Internal controls are "
                "examined in relation to fraud detection and fraud prevention."
            ),
        },
        {
            "chapter_number": 1,
            "section_reference": "Statement of the Problem",
            "section_path": ["CHAPTER ONE", "Statement of the Problem"],
            "paragraph_id": "C1-P2",
            "text": (
                "The Bank of Ghana (2025) reported a 33 per cent rise. Prior studies (A, 2024) and "
                "(B, 2025) did not examine rural banks or disaggregated controls. This contextual "
                "and methodological gap remains unresolved. The present study investigates it."
            ),
        },
        {
            "chapter_number": 1,
            "section_reference": "Significance of the Study",
            "section_path": ["CHAPTER ONE", "Significance of the Study"],
            "paragraph_id": "C1-P3",
            "text": (
                "The study contributes to theory and literature, gives management and the board "
                "institutional evidence, and informs Bank of Ghana policy."
            ),
        },
        {
            "chapter_number": 2,
            "section_reference": "Theoretical Review",
            "section_path": ["CHAPTER TWO", "Theoretical Review"],
            "paragraph_id": "C2-P1",
            "text": "Agency Theory supports Objective 1 and Fraud Theory supports Objective 3.",
        },
        {
            "chapter_number": 3,
            "section_reference": "Population and Sampling",
            "section_path": ["CHAPTER THREE", "Population and Sampling"],
            "paragraph_id": "C3-P1",
            "text": (
                "The Human Resource Department provided the staff list of 70 employees. A census "
                "was selected because the population was manageable and sensitive."
            ),
        },
        {
            "chapter_number": 3,
            "section_reference": "Data Analysis",
            "section_path": ["CHAPTER THREE", "Data Analysis"],
            "paragraph_id": "C3-P2",
            "text": (
                "Questionnaire responses will be coded and analysed in SPSS Version 26 using "
                "multiple regression. The instrument draws on a systematic review of established scales."
            ),
        },
    ]
    return {
        "summary": {"submission_scope": "chapters one to three"},
        "_runtime_context": {"current_paragraphs": rows},
    }


def _finding(fid: str, title: str, action: str = "Revise the marked passage."):
    return {
        "finding_id": fid,
        "chapter": 1,
        "section_reference": "Statement of the Problem",
        "item": title,
        "issue_title": title,
        "assessment": title,
        "comment": title,
        "required_action": action,
        "severity": "major",
        "confidence": 0.9,
        "evidence": [{"paragraph": 2, "text": "The Bank of Ghana (2025) reported a 33 per cent rise."}],
    }


def test_release_guard_blocks_wrong_design_wrong_stage_and_section_false_positives():
    review = _runtime_review()
    context = classify_review_context(review)
    assert context.design == "primary_quantitative"
    assert context.submission_stage == "chapters_one_to_three"
    assert context.has_results is False

    findings = [
        _finding("BG", "The background needs a clearer applied or professional logic"),
        _finding("NUM", "A numerical empirical claim has no clearly supported citation"),
        _finding("GAP", "The contextual argument does not yet establish a precise research gap"),
        _finding("SIG", "The applied or professional contribution is not explicit"),
        _finding("THEORY", "Each theory is not clearly linked to the rest of the study"),
        _finding("FRAME", "Sampling frame is missing or not clearly reported"),
        _finding("SAMPLE", "Sampling technique is not sufficiently justified"),
        _finding("SOFT", "Software is named but its use is not sufficiently explained"),
        _finding("REVIEW", "Review-based research needs transparent search, screening and appraisal procedures"),
        _finding("RESULTS", "The regression results do not clearly report confidence intervals"),
        _finding("MOD", "Moderation analysis should explain the interaction p value and simple slopes"),
    ]

    released = filter_and_rewrite_release_findings(findings, review)
    titles = " ".join(str(row.get("item")) for row in released).lower()
    assert "background needs" not in titles
    assert "numerical empirical" not in titles
    assert "precise research gap" not in titles
    assert "professional contribution" not in titles
    assert "review-based research" not in titles
    assert "regression results do not" not in titles
    assert "moderation role is not aligned" in titles


def test_questionnaire_scale_review_phrase_does_not_activate_systematic_review_route():
    rows = _runtime_review()["_runtime_context"]["current_paragraphs"]
    methods = _detected_methods(rows, {3})
    assert "systematic_review" not in methods
    assert "survey" in methods or "regression" in methods or "linear_regression" in methods
