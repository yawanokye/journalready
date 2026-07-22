from __future__ import annotations

import inspect
from io import BytesIO
from zipfile import ZipFile

import app.main as main_module
from app.assessment_schemas import ExternalAssessmentReport
from app.external_assessment import prepare_external_assessment
from app.external_assessment_guard import build_document_manifest
from app.external_assessment_exporter import (
    build_confidential_recommendation,
    build_corrections_schedule,
    build_external_examination_report,
    build_oral_examination_questions,
)


def domain(name: str, judgement: str = "appropriate_with_minor_refinement") -> dict:
    return {
        "domain": name,
        "judgement": judgement,
        "coverage_status": "fully_assessed",
        "evidence_ids": ["P1"],
        "assessment": f"Assessment of {name}.",
        "strengths": ["A defensible strength."],
        "concerns": ["A material concern."],
        "required_corrections": ["A specific correction."],
    }


def raw_report() -> dict:
    fields = {
        "study_summary": "The study examines a defined research problem.",
        "overall_academic_judgement": "The thesis has merit but requires correction.",
        "degree_standard_judgement": "The work partly meets the degree standard.",
        "chapter_one_gate_status": "fundamentally_deficient",
        "major_strengths": ["The topic is important."],
        "publication_potential": "One article may be developed after revision.",
        "corrections": [
            {
                "number": 9,
                "classification": "major",
                "chapter_or_section": "Statement of the Problem",
                "location": "Chapter One",
                "evidence_ids": ["P1"],
                "issue": "The research gap is not established.",
                "required_correction": "Reconstruct the problem statement using evidence.",
                "rationale": "The thesis requires a defensible foundation.",
                "verification_by": "External examiner",
            }
        ],
        "oral_examination_questions": [
            {
                "category": "Research problem",
                "question": "What precise knowledge gap does the study address?",
                "rationale": "Tests the coherence of the thesis foundation.",
            }
        ],
        "final_recommendation": "pass_without_corrections",
        "recommendation_rationale": "The thesis is promising.",
        "priority_corrections_before_award": ["Reconstruct Chapter One."],
        "corrections_verification_assessment": "Not applicable at initial examination.",
        "confidential_comments_to_university": "The foundation requires close scrutiny.",
        "recommendation_confidence": "high",
        "corrections_verification_by": "External examiner",
        "viva_recommendation": "required",
        "examiner_declaration": "I examined the thesis independently.",
    }
    domain_fields = (
        "chapter_one_assessment",
        "research_problem_and_purpose",
        "literature_and_theoretical_foundation",
        "methodology_and_procedures",
        "results_or_findings",
        "discussion_and_interpretation",
        "conclusions_recommendations_and_contribution",
        "structural_coherence_and_alignment",
        "academic_writing_and_presentation",
        "ethics_and_research_integrity",
        "originality_and_contribution",
    )
    for field in domain_fields:
        fields[field] = domain(
            field,
            "fundamentally_deficient" if field == "chapter_one_assessment" else "appropriate_with_minor_refinement",
        )
    return fields


def prepared_review() -> dict:
    review = {
        "summary": {
            "filename": "thesis.docx",
            "academic_level": "PhD",
            "research_approach": "mixed",
        }
    }
    metadata = {
        "candidate_name": "Candidate",
        "candidate_number": "PG001",
        "degree_programme": "PhD Management",
        "candidate_department": "School of Business",
        "institution": "University of Cape Coast",
        "thesis_title": "A Thesis Title",
        "assessment_stage": "initial_examination",
        "examiner_name": "Professor Examiner",
        "examiner_department": "Department of Management",
    }
    review["external_assessment"] = prepare_external_assessment(
        raw_report(), metadata, review
    )
    return review


def docx_text(data: bytes) -> str:
    with ZipFile(BytesIO(data)) as archive:
        return archive.read("word/document.xml").decode("utf-8")



def test_external_assessment_schema_covers_full_examiner_report() -> None:
    validated = ExternalAssessmentReport.model_validate(raw_report())
    assert validated.chapter_one_gate_status == "fundamentally_deficient"
    assert validated.corrections_verification_assessment

def test_chapter_one_critical_gate_blocks_unqualified_pass() -> None:
    review = prepared_review()
    assessment = review["external_assessment"]
    assert assessment["final_recommendation"] == "revise_and_resubmit_for_re_examination"
    assert assessment["recommendation_consistency_adjusted"] is True
    assert assessment["corrections"][0]["number"] == 1


def test_all_four_external_examination_outputs_are_valid_docx() -> None:
    review = prepared_review()
    outputs = [
        build_external_examination_report(review),
        build_corrections_schedule(review),
        build_confidential_recommendation(review),
        build_oral_examination_questions(review),
    ]
    for output in outputs:
        assert output.startswith(b"PK")
        assert "Candidate" in docx_text(output)
    assert "EXTERNAL EXAMINATION REPORT" in docx_text(outputs[0])
    assert "Evidence references" in docx_text(outputs[0])
    assert "CONFIDENTIAL RECOMMENDATION" in docx_text(outputs[2])


def test_external_assessment_fields_are_accepted_by_api() -> None:
    signature = inspect.signature(main_module.create_review)
    for name in (
        "workflow_type",
        "assessment_stage",
        "candidate_name",
        "candidate_number",
        "degree_programme",
        "candidate_department",
        "institution",
        "thesis_title",
        "prior_examiner_files",
        "prior_examiner_comments_text",
        "prior_version_file",
    ):
        assert name in signature.parameters


def test_external_assessment_routes_are_registered() -> None:
    paths = {route.path for route in main_module.app.routes}
    assert "/api/review/{review_id}/external-report.docx" in paths
    assert "/api/review/{review_id}/corrections-schedule.docx" in paths
    assert "/api/review/{review_id}/confidential-recommendation.docx" in paths
    assert "/api/review/{review_id}/oral-questions.docx" in paths


def test_limited_source_coverage_withholds_academic_recommendation() -> None:
    report = raw_report()
    manifest = build_document_manifest(
        [
            {
                "paragraph": 1,
                "chapter_number": 1,
                "heading": "Introduction",
                "text": "A short introduction and statement of the problem.",
                "is_heading": False,
            }
        ],
        summary={"academic_level": "PhD"},
    )
    review = {
        "summary": {
            "filename": "incomplete.docx",
            "academic_level": "PhD",
            "research_approach": "quantitative",
        }
    }
    prepared = prepare_external_assessment(
        report,
        {"assessment_stage": "initial_examination"},
        review,
        manifest,
    )
    assert prepared["final_recommendation"] == "assessment_withheld_incomplete_extraction"
    assert prepared["recommendation_confidence"] == "low"
    assert prepared["report_status"] == "Assessment withheld pending source verification"
    assert prepared["source_evidence_register"]
    review["external_assessment"] = prepared
    report_xml = docx_text(build_external_examination_report(review))
    assert "Source Evidence Register" in report_xml
    assert "P1" in report_xml
