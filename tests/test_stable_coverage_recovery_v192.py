from pathlib import Path

from app.ai_config import HybridAIConfig
from app.academic_ai_engine import _unresolved_section_fallback
from app.ai_providers import _normalise_model_payload
from app.ai_schemas import AcademicSectionReviewItem


def test_focused_recovery_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    for name in (
        "AI_FOCUSED_RECOVERY_PARALLEL_CALLS",
        "AI_FOCUSED_RECOVERY_MAX_OUTPUT_TOKENS",
        "AI_FOCUSED_RECOVERY_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    config = HybridAIConfig.from_env()
    assert config.focused_recovery_parallel_calls == 2
    assert config.focused_recovery_max_output_tokens == 4200
    assert config.focused_recovery_timeout_seconds == 240


def test_single_section_payload_preserves_key():
    value = _normalise_model_payload(
        {
            "section_key": "chapter-three-methods",
            "section_name": "Research Methods",
            "section_score": 72,
            "section_assessment": "The methods are present but need clearer justification.",
            "strengths": [],
            "issues": [],
            "coverage_warning": "",
        },
        AcademicSectionReviewItem,
    )
    validated = AcademicSectionReviewItem.model_validate(value)
    assert validated.section_key == "chapter-three-methods"


def test_unresolved_fallback_never_calls_present_section_missing():
    review = _unresolved_section_fallback({
        "section_key": "s1",
        "heading": "Sampling Procedures",
        "chapter_number": 3,
        "section_path": ["Chapter Three", "Sampling Procedures"],
        "part": 1,
        "paragraphs": [{"text": "A sampling procedure is described."}],
    })
    assert review["section_assessment"] == ""
    assert review["coverage_warning"] == ""
    assert review["issues"] == []


def test_browser_does_not_auto_resume_forever():
    javascript = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "job.auto_resume_allowed !== false" in javascript
    assert "Automatic recovery stopped" in javascript
    assert "job.auto_resume_allowed !== false" in javascript


def test_server_exposes_auto_resume_guard():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert '"auto_resume_allowed"' in source
    assert "ReviewRecord.resume_count < MAX_AUTO_RESUMES" in source


def test_bounded_chapter_recovery_pipeline_is_present():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    assert "academic-review-v2.5.0-isolated-generic-natural-evidence-ledger" in source
    assert "chapter_packet_coverage_recovery" in source
    assert "single_chapter_packet_retry" in source
    assert "academic-focused-section-recovery-v1.9.2" not in source
