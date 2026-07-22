from pathlib import Path

from app.ai_config import HybridAIConfig
from app.assessment_schemas import ExternalAssessmentAdjudication


def test_combined_adjudication_schema_keeps_corrections_and_decision_together():
    value = ExternalAssessmentAdjudication.model_validate({
        "corrections": [{
            "number": 1,
            "classification": "major",
            "chapter_or_section": "Chapter Four",
            "location": "Table 4.2",
            "evidence_ids": ["T4"],
            "issue": "The interpretation exceeds the reported evidence.",
            "required_correction": "Revise the interpretation to match Table 4.2.",
            "rationale": "The recommendation must follow the verified results.",
            "verification_by": "External examiner",
        }],
        "oral_examination_questions": [],
        "priority_corrections_before_award": ["Correct the results interpretation."],
        "corrections_verification_assessment": "Verify against the corrected chapter.",
        "overall_academic_judgement": "The thesis is defensible after major correction.",
        "final_recommendation": "pass_subject_to_major_corrections",
        "recommendation_rationale": "The deficiencies are material but remediable.",
        "confidential_comments_to_university": "The examiner should verify corrections.",
        "recommendation_confidence": "high",
        "corrections_verification_by": "External examiner",
        "viva_recommendation": "required",
        "examiner_declaration": "I examined the thesis independently.",
    })
    assert value.corrections[0].classification == "major"
    assert value.final_recommendation == "pass_subject_to_major_corrections"


def test_external_role_specific_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_EXTERNAL_DOMAIN_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("OPENAI_EXTERNAL_ADJUDICATOR_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("OPENAI_EXTERNAL_DOMAIN_REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_EXTERNAL_ADJUDICATOR_REASONING_EFFORT", "xhigh")
    config = HybridAIConfig.from_env()
    assert config.openai_external_domain_model == "gpt-5.6-terra"
    assert config.openai_external_adjudicator_model == "gpt-5.6-sol"
    assert config.openai_external_domain_reasoning_effort == "high"
    assert config.openai_external_adjudicator_reasoning_effort == "xhigh"


def test_supervisory_and_external_workflows_are_both_simplified():
    academic = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    external = Path("app/external_assessment.py").read_text(encoding="utf-8")
    assert "AI_CHAPTER_REVIEW_CONCURRENCY" not in academic  # config is resolved outside source literals
    assert "def _chapter_review_packets" in academic
    assert 'stage="adjudication"' in external
    assert '"external_assessment_stage_count": 4' in external
    assert "three_examiners_one_adjudicator" in external
