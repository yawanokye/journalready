import pytest

from app.document_parser import detect_doctoral_functional_coverage
from app.review_engine import (
    _candidate_paragraphs,
    _partition_submission_for_review,
)


def row(text, heading, chapter, paragraph):
    return {
        "text": text,
        "heading": heading,
        "chapter_number": chapter,
        "paragraph": paragraph,
        "page": None,
        "is_heading": text == heading,
        "chapter_marker_number": chapter if text == heading else None,
        "chapter_title_number": None,
        "section_number_chapter": None,
        "section_number": None,
    }


def flexible_doctoral_thesis():
    return [
        row(
            "CHAPTER ONE ORIENTATION TO THE PRACTICE PROBLEM",
            "CHAPTER ONE ORIENTATION TO THE PRACTICE PROBLEM",
            1,
            1,
        ),
        row(
            "The background to the study, study context and rationale lead to the statement of the problem. Research objectives and research questions define the practice challenge. The significance of the study, scope of the study and definition of terms are stated.",
            "CHAPTER ONE ORIENTATION TO THE PRACTICE PROBLEM",
            1,
            2,
        ),
        row(
            "CHAPTER TWO PROFESSIONAL AND SCHOLARLY CONTEXT",
            "CHAPTER TWO PROFESSIONAL AND SCHOLARLY CONTEXT",
            2,
            3,
        ),
        row(
            "The literature review, theoretical framework and conceptual "
            "framework position the inquiry.",
            "CHAPTER TWO PROFESSIONAL AND SCHOLARLY CONTEXT",
            2,
            4,
        ),
        row(
            "CHAPTER THREE DESIGN OF THE INQUIRY",
            "CHAPTER THREE DESIGN OF THE INQUIRY",
            3,
            5,
        ),
        row(
            "The research methodology explains the research philosophy, research design, data collection, sampling procedure, measurement of variables and analysis method. Diagnostic tests, robustness, software and code support reproducibility. Ethical considerations and research integrity are addressed.",
            "CHAPTER THREE DESIGN OF THE INQUIRY",
            3,
            6,
        ),
        row(
            "CHAPTER FOUR PRACTICE-BASED EVIDENCE I",
            "CHAPTER FOUR PRACTICE-BASED EVIDENCE I",
            4,
            7,
        ),
        row(
            "The empirical findings and results are presented with model estimates.",
            "CHAPTER FOUR PRACTICE-BASED EVIDENCE I",
            4,
            8,
        ),
        row(
            "CHAPTER FIVE INTEGRATIVE SYNTHESIS",
            "CHAPTER FIVE INTEGRATIVE SYNTHESIS",
            5,
            9,
        ),
        row(
            "The integrative discussion interprets the findings and considers "
            "alternative explanations.",
            "CHAPTER FIVE INTEGRATIVE SYNTHESIS",
            5,
            10,
        ),
        row(
            "CHAPTER SIX CONTRIBUTIONS AND PROFESSIONAL IMPLICATIONS",
            "CHAPTER SIX CONTRIBUTIONS AND PROFESSIONAL IMPLICATIONS",
            6,
            11,
        ),
        row(
            "The conclusions explain the original contribution to knowledge, "
            "professional implications, recommendations and future research.",
            "CHAPTER SIX CONTRIBUTIONS AND PROFESSIONAL IMPLICATIONS",
            6,
            12,
        ),
    ]


def test_phd_custom_six_chapter_structure_is_accepted():
    partition = _partition_submission_for_review(
        flexible_doctoral_thesis(),
        selected_chapter=None,
        full_thesis=True,
        filename="custom-phd.docx",
        academic_level="PhD",
    )
    assert partition["structure_mode"] == "flexible_doctoral"
    assert partition["fixed_five_chapter_required"] is False
    assert partition["doctoral_coverage"]["complete"] is True


def test_professional_doctorate_custom_structure_is_rejected():
    with pytest.raises(ValueError, match="Missing standard coverage"):
        _partition_submission_for_review(
            flexible_doctoral_thesis(),
            selected_chapter=None,
            full_thesis=True,
            filename="professional-doctorate.docx",
            academic_level="Professional Doctorate",
        )


def test_same_nonstandard_structure_does_not_override_masters_rules():
    with pytest.raises(ValueError, match="Missing standard coverage"):
        _partition_submission_for_review(
            flexible_doctoral_thesis(),
            selected_chapter=None,
            full_thesis=True,
            filename="custom-mphil.docx",
            academic_level="Research Masters / MPhil",
        )


def test_incomplete_doctoral_upload_is_rejected_by_function_not_chapter_count():
    incomplete = [
        row(
            "CHAPTER FOUR FINDINGS",
            "CHAPTER FOUR FINDINGS",
            4,
            1,
        ),
        row(
            "The empirical results and findings are presented.",
            "CHAPTER FOUR FINDINGS",
            4,
            2,
        ),
        row(
            "CHAPTER FIVE CONCLUSIONS",
            "CHAPTER FIVE CONCLUSIONS",
            5,
            3,
        ),
        row(
            "The conclusions and recommendations are stated.",
            "CHAPTER FIVE CONCLUSIONS",
            5,
            4,
        ),
    ]
    with pytest.raises(ValueError, match="prescribed doctoral research elements"):
        _partition_submission_for_review(
            incomplete,
            selected_chapter=None,
            full_thesis=True,
            filename="incomplete-phd.docx",
            academic_level="PhD",
        )


def test_doctoral_functional_coverage_requires_essential_functions():
    coverage = detect_doctoral_functional_coverage(
        flexible_doctoral_thesis()
    )
    assert coverage["complete"] is True
    assert coverage["functions_covered_count"] == 6


def test_flexible_rule_search_is_not_tied_to_standard_chapter_number():
    paragraphs = flexible_doctoral_thesis()
    methodology_rule = {
        "chapter_number": 3,
        "headings": ["research methodology", "research methods"],
    }
    candidates = _candidate_paragraphs(
        paragraphs,
        methodology_rule,
        selected_chapter=None,
        full_thesis=True,
        flexible_structure=True,
    )
    assert any(
        "research methodology" in candidate["text"].lower()
        for candidate in candidates
    )
