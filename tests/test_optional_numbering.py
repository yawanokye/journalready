import pytest

from app.document_parser import detect_document_chapter_profile
from app.review_engine import _partition_submission_for_review


def heading(text, chapter, title_chapter=None, number_chapter=None, paragraph=1):
    return {
        "text": text,
        "paragraph": paragraph,
        "page": None,
        "is_heading": True,
        "heading": text,
        "chapter_number": chapter,
        "chapter_marker_number": None,
        "chapter_title_number": title_chapter,
        "section_number_chapter": number_chapter,
        "section_number": None,
    }


def unnumbered_complete_thesis():
    return [
        heading("INTRODUCTION", 1, title_chapter=1, paragraph=1),
        heading("Background to the Study", 1, paragraph=2),
        heading("Statement of the Problem", 1, paragraph=3),
        heading("LITERATURE REVIEW", 2, title_chapter=2, paragraph=4),
        heading("Conceptual Review", 2, paragraph=5),
        heading("Theoretical Review", 2, paragraph=6),
        heading("Empirical Review", 2, paragraph=7),
        heading("RESEARCH METHODS", 3, title_chapter=3, paragraph=8),
        heading("Research Design", 3, paragraph=9),
        heading("Population", 3, paragraph=10),
        heading("Sampling Procedure", 3, paragraph=11),
        heading("RESULTS AND DISCUSSION", 4, title_chapter=4, paragraph=12),
        heading("Results", 4, paragraph=13),
        heading("Discussion of Findings", 4, paragraph=14),
        heading(
            "SUMMARY, CONCLUSIONS AND RECOMMENDATIONS",
            5,
            title_chapter=5,
            paragraph=15,
        ),
        heading("Summary of Findings", 5, paragraph=16),
        heading("Conclusions", 5, paragraph=17),
        heading("Recommendations", 5, paragraph=18),
    ]


def test_unnumbered_complete_thesis_is_accepted():
    partition = _partition_submission_for_review(
        unnumbered_complete_thesis(),
        selected_chapter=None,
        full_thesis=True,
        filename="complete-thesis.docx",
    )
    assert partition["coverage"]["complete"] is True
    assert partition["uploaded_chapters"] == [1, 2, 3, 4, 5]


def test_unnumbered_chapter_title_is_primary_detection_basis():
    profile = detect_document_chapter_profile(
        unnumbered_complete_thesis()
    )
    assert profile["numbering_used"] is False
    assert profile["primary_detection_basis"] == "chapter_title"


def test_selected_unnumbered_chapter_is_isolated():
    partition = _partition_submission_for_review(
        unnumbered_complete_thesis(),
        selected_chapter=3,
        full_thesis=False,
        filename="composite.docx",
    )
    assert {
        row["chapter_number"]
        for row in partition["review_paragraphs"]
    } == {3}


def test_numbering_remains_supported_but_optional():
    rows = [
        heading(
            "3.1 Research Design",
            3,
            number_chapter=3,
            paragraph=1,
        ),
        heading(
            "3.2 Population",
            3,
            number_chapter=3,
            paragraph=2,
        ),
        heading(
            "3.3 Sampling Procedure",
            3,
            number_chapter=3,
            paragraph=3,
        ),
    ]
    profile = detect_document_chapter_profile(rows)
    assert profile["numbering_used"] is True
    assert profile["detected_chapters"] == [3]
