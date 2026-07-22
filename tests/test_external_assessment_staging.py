from __future__ import annotations

import asyncio

from app.ai_config import HybridAIConfig
from app.ai_providers import AIProviderError, ProviderResult
from app.ai_schemas import AIUsageRecord
from app.external_assessment import enrich_with_external_assessment


def domain(name: str, evidence_id: str) -> dict:
    return {
        "domain": name,
        "judgement": "appropriate_with_minor_refinement",
        "coverage_status": "fully_assessed",
        "evidence_ids": [evidence_id],
        "assessment": f"Assessment of {name}.",
        "strengths": ["A relevant strength."],
        "concerns": ["A material concern."],
        "required_corrections": ["A precise correction."],
    }


def stage_payload(stage: str) -> dict:
    if stage == "foundation":
        return {
            "study_summary": "The study examines a defined research problem.",
            "degree_standard_judgement": "The work broadly meets the degree standard.",
            "chapter_one_gate_status": "major_concern",
            "chapter_one_assessment": domain("Chapter One", "P1"),
            "research_problem_and_purpose": domain("Research problem and purpose", "P1"),
            "literature_and_theoretical_foundation": domain("Literature and theory", "P2"),
            "methodology_and_procedures": domain("Methodology", "P3"),
        }
    if stage == "evidence_core":
        return {
            "results_or_findings": domain("Results or findings", "P4"),
            "discussion_and_interpretation": domain("Discussion", "P5"),
            "conclusions_recommendations_and_contribution": domain("Conclusions", "P6"),
            "structural_coherence_and_alignment": domain("Structural coherence", "P4"),
        }
    if stage == "integrity":
        return {
            "academic_writing_and_presentation": domain("Writing", "P5"),
            "ethics_and_research_integrity": domain("Ethics", "P6"),
            "originality_and_contribution": domain("Originality", "P6"),
            "major_strengths": ["The topic is significant."],
            "publication_potential": "The work has publication potential after revision.",
        }
    if stage == "adjudication":
        return {
            "corrections": [
                {
                    "number": 1,
                    "classification": "major",
                    "chapter_or_section": "Chapter One",
                    "location": "Statement of the Problem",
                    "evidence_ids": ["P1"],
                    "issue": "The gap requires clarification.",
                    "required_correction": "Clarify the gap with evidence.",
                    "rationale": "The thesis requires a defensible foundation.",
                    "verification_by": "External examiner",
                }
            ],
            "oral_examination_questions": [
                {
                    "category": "Research problem",
                    "question": "What precise gap does the thesis address?",
                    "rationale": "Tests the thesis foundation.",
                }
            ],
            "priority_corrections_before_award": ["Clarify the research gap."],
            "corrections_verification_assessment": "Not applicable at initial examination.",
            "overall_academic_judgement": "The thesis has merit but requires major correction.",
            "final_recommendation": "pass_subject_to_major_corrections",
            "recommendation_rationale": "The identified deficiencies are remediable.",
            "confidential_comments_to_university": "The corrections should be examiner-verified.",
            "recommendation_confidence": "moderate",
            "corrections_verification_by": "External examiner",
            "viva_recommendation": "required",
            "examiner_declaration": "I examined the thesis independently.",
        }
    raise AssertionError(stage)


def make_result(stage: str) -> ProviderResult:
    return ProviderResult(
        data=stage_payload(stage),
        usage=AIUsageRecord(
            provider="openai",
            model="gpt-5.6-terra",
            purpose=f"external_thesis_assessment_{stage}",
            input_tokens=100,
            cached_input_tokens=10,
            output_tokens=50,
            request_id=f"request-{stage}",
        ),
    )



def realistic_runtime_paragraphs() -> list[dict]:
    filler = " This paragraph provides detailed scholarly explanation, evidence and interpretation for the examination record." * 220
    return [
        {"paragraph": 1, "chapter_number": 1, "heading": "Statement of the Problem", "text": "The statement of the problem, research objectives and research questions are presented." + filler, "is_heading": False},
        {"paragraph": 2, "chapter_number": 3, "heading": "Literature Review", "text": "The literature review, theoretical framework, conceptual model and hypotheses are developed." + filler, "is_heading": False},
        {"paragraph": 3, "chapter_number": 4, "heading": "Research Methodology", "text": "The research philosophy, research design, sampling procedure, sample size and data collection procedures are explained." + filler, "is_heading": False},
        {"paragraph": 4, "chapter_number": 5, "heading": "Results", "text": "The results include measurement model, structural model, bootstrapping, path coefficients and hypothesis testing." + filler, "is_heading": False},
        {"paragraph": 5, "chapter_number": 6, "heading": "Discussion", "text": "The discussion of findings interprets the results against theory and prior research." + filler, "is_heading": False},
        {"paragraph": 6, "chapter_number": 7, "heading": "Conclusions and Recommendations", "text": "The conclusions, recommendations, contribution to knowledge, limitations, future research and ethical clearance are presented." + filler, "is_heading": False},
    ]

def test_external_assessment_uses_three_examiners_and_one_adjudicator(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = HybridAIConfig.from_env()
    calls: list[str] = []

    async def fake_complete(self, **kwargs):
        stage = kwargs["purpose"].removeprefix("external_thesis_assessment_")
        calls.append(stage)
        return make_result(stage)

    monkeypatch.setattr(
        "app.external_assessment.OpenAIProvider.complete_json",
        fake_complete,
    )

    review = {
        "review_id": "review-1",
        "summary": {
            "filename": "phd.docx",
            "academic_level": "PhD",
            "research_approach": "mixed",
        },
        "ai_review": {
            "usage": [],
            "estimated_cost_usd": 0.0,
            "api_call_count": 0,
        },
    }
    runtime_context = {"current_paragraphs": realistic_runtime_paragraphs()}
    metadata = {
        "candidate_name": "Candidate",
        "degree_programme": "PhD",
        "assessment_stage": "initial_examination",
    }

    output = asyncio.run(
        enrich_with_external_assessment(
            review,
            runtime_context,
            metadata=metadata,
            config=config,
        )
    )

    assert set(calls) == {"foundation", "evidence_core", "integrity", "adjudication"}
    assert len(calls) == 4
    assert set(calls[:3]) == {"foundation", "evidence_core", "integrity"}
    assert calls[3] == "adjudication"
    assert output["summary"]["external_assessment_generation_mode"] == "three_examiners_one_adjudicator"
    assert output["summary"]["external_assessment_stage_count"] == 4
    assert output["external_assessment"]["final_recommendation"] == "pass_subject_to_major_corrections"
    assert output["external_assessment_usage"]["api_call_count"] == 4
    assert len(output["ai_review"]["usage"]) == 4


def test_truncated_stage_gets_one_recovery_attempt(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = HybridAIConfig.from_env()
    attempts = {"foundation": 0}

    async def fake_complete(self, **kwargs):
        stage = kwargs["purpose"].removeprefix("external_thesis_assessment_")
        if stage == "foundation":
            attempts["foundation"] += 1
            if attempts["foundation"] == 1:
                raise AIProviderError(
                    "OpenAI output was truncated because the output-token limit was reached."
                )
        return make_result(stage)

    monkeypatch.setattr(
        "app.external_assessment.OpenAIProvider.complete_json",
        fake_complete,
    )

    review = {
        "review_id": "review-2",
        "summary": {
            "filename": "phd.docx",
            "academic_level": "PhD",
            "research_approach": "quantitative",
        },
    }
    output = asyncio.run(
        enrich_with_external_assessment(
            review,
            {"current_paragraphs": realistic_runtime_paragraphs()},
            metadata={"assessment_stage": "initial_examination"},
            config=config,
        )
    )

    assert attempts["foundation"] == 2
    assert output["summary"]["external_assessment_available"] is True
