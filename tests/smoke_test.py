"""Run with: python tests/smoke_test.py /path/to/sample.docx"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.annotated_exporter import build_annotated_docx
from app.report_exporter import build_docx_report
from app.review_engine import analyse


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Provide a sample DOCX path.")
    source = Path(sys.argv[1])
    data = source.read_bytes()
    review = analyse(
        data,
        source.name,
        academic_level="Research Masters / MPhil",
        research_approach="quantitative",
        selected_chapter=1,
        review_scope="chapter",
        document_type="chapter_one",
    )
    review.pop("_runtime_context", None)
    review["academic_findings"] = [{
        "review_type": "academic_finding",
        "category": "academic_writing",
        "section": "Introduction",
        "item": "Sentence construction requires correction",
        "status": "partly_meets_requirement",
        "status_label": "Minor correction",
        "severity": "minor",
        "confidence": 0.95,
        "evidence": [{
            "text": "Sample evidence",
            "page": None,
            "paragraph": 1,
            "page_paragraph": None,
            "heading": "Introduction",
            "chapter_number": 1,
            "is_heading": False,
            "source_filename": source.name,
            "document_role": "current",
            "document_index": 0,
            "paragraph_id": "P1",
            "matched_terms": [],
        }],
        "comment": "The sentence is grammatically incomplete and obscures the intended claim.",
        "required_action": "Rewrite the sentence with a clear subject, verb, and precise academic claim.",
        "problematic_quote": "",
        "headings": ["Introduction"],
    }]
    review["academic_strengths"] = []
    review["overall_academic_assessment"] = "Smoke-test academic assessment."
    review["summary"].update({
        "academic_review_score": 70.0,
        "academic_sections_reviewed": 1,
        "critical_issues": 0,
        "major_issues": 0,
        "moderate_issues": 0,
        "minor_issues": 1,
        "strengths_identified": 0,
    })
    assert build_docx_report(review)
    assert build_annotated_docx(data, review)
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
