from __future__ import annotations

import io

from docx import Document

from app.ai_schemas import AcademicIssue
from app.coverage_review import build_coverage_ledger, build_coverage_units
from app.professional_review_pipeline import attach_professional_review_package
from app.report_exporter import build_docx_report
from app.statistical_review import statistical_warnings_to_issues
from app.student_friendly_review import make_issue_student_friendly
from app.supervisory_review_algorithm import algorithm_contract


def paragraph(number: int, text: str, *, chapter: int = 4, heading: str = "Results"):
    return {
        "paragraph": number,
        "text": text,
        "chapter_number": chapter,
        "heading": heading,
        "section_path": [heading],
        "is_heading": False,
        "document_role": "current",
        "source_kind": "paragraph",
    }


def finding(number: int, chapter: int, severity: str = "major"):
    return {
        "finding_id": f"F{number}",
        "category": "statistical_accuracy" if chapter == 4 else "methodological_rigour",
        "section": "Regression Results" if chapter == 4 else "Research Methods",
        "chapter_number": chapter,
        "item": "The reported model values do not reconcile" if chapter == 4 else "The sampling procedure is not reproducible",
        "status": "does_not_meet_requirement",
        "severity": severity,
        "confidence": 0.99,
        "evidence": [{
            "paragraph": number,
            "paragraph_id": f"P{number}",
            "chapter_number": chapter,
            "section_reference": "Regression Results" if chapter == 4 else "Research Methods",
            "text": "R²=.40, F=77.98, B=.512, SE=.058, t=8.83" if chapter == 4 else "A simple random procedure was used.",
        }],
        "comment": "The values printed in this model cannot all come from the same regression output." if chapter == 4 else "The study does not explain how respondents were selected.",
        "required_action": "Re-run the model and reproduce all values from one software output." if chapter == 4 else "State the sampling frame, randomisation steps and treatment of absentees.",
        "illustrative_guidance": "For example, report R, R², adjusted R², F, degrees of freedom and p from the same output." if chapter == 4 else "For example, state who prepared the list and how the random numbers were generated.",
        "verification_status": "verified inconsistency" if chapter == 4 else "evidence-anchored",
    }


def test_algorithm_is_coverage_driven_and_has_no_comment_quota():
    contract = algorithm_contract()
    assert contract["predetermined_comment_count"] is False
    assert contract["allowed_target_statuses"] == ["PASS", "COMMENT", "VERIFY SOURCE", "RE-ANALYSE"]
    assert "Statistical audit" in contract["stages"]


def test_statistical_warning_converts_to_valid_academic_issue():
    review = {
        "consistency_warnings": [{
            "kind": "table_r2_f_n_mismatch",
            "message": "The reported R² and F statistic do not reconcile.",
            "severity": "critical",
            "verification": "verified inconsistency",
            "evidence": {
                "paragraph_id": "P4",
                "section_reference": "Regression Results",
                "text": "R²=.40 and F=77.98",
            },
            "required_action": "Re-run the model and reproduce the table from one output.",
        }]
    }
    issue = statistical_warnings_to_issues(review, academic_level="PhD")[0]
    validated = AcademicIssue.model_validate({key: value for key, value in issue.items() if key in AcademicIssue.model_fields})
    assert validated.category == "statistical_accuracy"
    assert validated.guidance_type == "statistical_verification"


def test_coverage_ledger_records_pass_comment_verify_and_reanalyse():
    rows = [paragraph(1, "Adequate paragraph."), paragraph(2, "A claim without source."), paragraph(3, "R²=.40 and F=77.98.")]
    units = build_coverage_units(rows, prose_paragraphs_per_unit=3)
    units[0]["section_key"] = "S001P01"
    reviews = [{
        "section_key": "S001P01",
        "assessed_paragraph_ids": ["P1", "P2", "P3"],
        "issues": [
            {"evidence_paragraph_ids": ["P2"], "category": "citations_and_sources", "source_verification_required": True, "required_action": "Verify the source."},
            {"evidence_paragraph_ids": ["P3"], "category": "statistical_accuracy", "verification_status": "verified inconsistency", "required_action": "Re-run the model."},
        ],
        "strengths": [],
    }]
    ledger = build_coverage_ledger(units, reviews)
    statuses = ledger["entries"][0]["target_statuses"]
    assert statuses == {"P1": "PASS", "P2": "VERIFY SOURCE", "P3": "RE-ANALYSE"}


def test_missing_section_comment_is_plain_and_direct():
    issue = {
        "category": "document_completeness",
        "section": "Chapter One",
        "issue_title": "Expected UCC thesis section is not evident: Definition of Terms",
        "missing_section_label": "Definition of Terms",
        "chapter_number": 1,
        "assessment": "Expected UCC thesis section is not evident.",
        "required_action": "Add the section.",
        "evidence": [],
    }
    result = make_issue_student_friendly(issue, "MPhil")
    assert result["issue_title"] == "Definition of Terms is missing from Chapter One"
    assert result["assessment"].startswith("Definition of Terms is missing from Chapter One.")
    assert "UCC thesis guidelines" in result["assessment"]
    assert "uploaded" not in " ".join(str(value) for value in result.values()).lower()


def test_report_follows_specification_sections_and_includes_statistical_audit(monkeypatch):
    monkeypatch.setenv("VPROF_SPEC_ALIGNED_SUPERVISORY_REPORT", "true")
    review = {
        "summary": {
            "review_scope": "full_thesis",
            "filename": "Study.docx",
            "document_label": "Complete thesis",
            "academic_level": "PhD",
            "review_depth": "advanced",
            "current_chapters_detected": [3, 4],
            "readiness_label": "Major revision required",
        },
        "academic_findings": [finding(2, 3), finding(4, 4, "critical")],
        "academic_section_reviews": [],
        "academic_strengths": [{"section": "Chapter One", "observation": "The topic is relevant to teacher education."}],
        "alignment_results": [],
        "statistical_review": {
            "consistency_warnings": [{
                "kind": "table_r2_f_n_mismatch",
                "message": "The reported R² and F statistic do not reconcile.",
                "severity": "critical",
                "verification": "verified inconsistency",
                "evidence": {"table_number": "6", "table_title": "Regression Model", "text": "R²=.40, F=77.98"},
                "required_action": "Re-run the model and reproduce the full table from one output.",
            }]
        },
        "overall_academic_assessment": "The study has a relevant topic, but the analysis must be corrected before the findings can be trusted.",
    }
    attach_professional_review_package(review)
    output = build_docx_report(review)
    doc = Document(io.BytesIO(output))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "1. Scope and limitation of the review" in text
    assert "2. Overall supervisory assessment" in text
    assert "3. Methods, Results and Discussion Accuracy Audit" in text
    assert "4. Chapter-by-chapter correction plan" in text
    assert "Numbered comments and detailed corrections" in text
    assert "uploaded" not in text.lower()


def test_measurement_audit_detects_item_map_and_blank_reliability():
    from app.statistical_review import audit_measurement_structure

    rows = [
        paragraph(1, "The Entitled Expectations subscale comprises 5 items.", chapter=3, heading="Instrument"),
        {
            **paragraph(2, "Scale | Items | Pilot Testing Reliability", chapter=3, heading="Reliability"),
            "source_kind": "table_row", "table_index": 1, "table_number": "1", "table_title": "Reliability", "table_row": 1,
        },
        {
            **paragraph(3, "Academic Entitlement | 15 | .", chapter=3, heading="Reliability"),
            "source_kind": "table_row", "table_index": 1, "table_number": "1", "table_title": "Reliability", "table_row": 2,
        },
        {
            **paragraph(4, "Entitled Expectations (AEE 1–8) | Engagement | -.42", chapter=4, heading="Results"),
            "source_kind": "table_row", "table_index": 2, "table_number": "3", "table_title": "Academic Entitlement Results", "table_row": 1,
        },
    ]
    kinds = {item["kind"] for item in audit_measurement_structure(rows)}
    assert "measurement_item_allocation_mismatch" in kinds
    assert "measurement_reliability_value_missing" in kinds
