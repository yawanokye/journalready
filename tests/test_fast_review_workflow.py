from pathlib import Path

from app.ai_config import HybridAIConfig
from app.academic_ai_engine import REVIEW_LEVEL_PROFILES, _batch


def test_fast_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    for name in (
        "AI_SECTION_BATCH_SIZE",
        "AI_LIGHT_SECTION_BATCH_SIZE",
        "AI_ADVANCED_SECTION_BATCH_SIZE",
        "AI_STRUCTURED_OUTPUT_RETRIES",
        "OPENAI_CHAPTER_MODEL",
        "OPENAI_EXPERT_MODEL",
        "OPENAI_FINAL_AUDIT_MODEL",
        "OPENAI_EXTERNAL_MODEL",
        "OPENAI_EXTERNAL_DOMAIN_MODEL",
        "OPENAI_EXTERNAL_ADJUDICATOR_MODEL",
        "OPENAI_REVIEW_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = HybridAIConfig.from_env()
    assert config.chapter_review_concurrency == 2
    assert config.chapter_packet_max_chars == 60000
    assert config.verification_batch_size == 12
    assert config.structured_output_retries == 0
    assert config.openai_chapter_model == "gpt-5.6-terra"
    assert config.openai_expert_model == "gpt-5.6-terra"
    assert config.openai_final_audit_model == "gpt-5.6-terra"
    assert config.openai_chapter_reasoning_effort == "medium"


def test_legacy_batch_helper_remains_available():
    sections = list(range(15))
    assert len(_batch(sections, 4)) == 4


def test_issue_limits_are_concise_but_level_calibrated():
    assert REVIEW_LEVEL_PROFILES["light"]["normal_issue_limit_per_section"] == 0
    assert REVIEW_LEVEL_PROFILES["standard"]["normal_issue_limit_per_section"] == 0
    assert REVIEW_LEVEL_PROFILES["advanced"]["normal_issue_limit_per_section"] == 0


def test_universal_accuracy_audit_is_present_for_all_depths():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    assert "academic-comment-audit-v2.5.0-isolated-risk-selected-natural-release-guard" in source
    assert "Accuracy is mandatory at every review depth" in source
    assert "verification_batches" in source
    assert "_chapter_review_packets" in source
    assert "_degree_audit_settings" in source
