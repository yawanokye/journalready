import pytest

from app.document_parser import (
    detect_chapter_number,
    detect_standard_chapter_coverage,
)
from app.review_engine import _partition_submission_for_review


def paragraph(text, chapter, heading=True, number=1):
    return {
        "text": text,
        "chapter_number": chapter,
        "is_heading": heading,
        "heading": text if heading else "",
        "paragraph": number,
    }


def complete_standard_paragraphs():
    headings = [
        ("CHAPTER ONE INTRODUCTION", 1),
        ("CHAPTER TWO LITERATURE REVIEW", 2),
        ("CHAPTER THREE RESEARCH METHODS", 3),
        ("CHAPTER FOUR RESULTS AND DISCUSSION", 4),
        ("CHAPTER FIVE SUMMARY, CONCLUSIONS AND RECOMMENDATIONS", 5),
    ]
    return [
        paragraph(text, chapter, number=index)
        for index, (text, chapter) in enumerate(headings, start=1)
    ]


def test_optional_chapter_numbers_are_detected():
    assert detect_chapter_number("CHAPTER SIX DISCUSSION") == 6
    assert detect_chapter_number("CHAPTER 7 ADDITIONAL ANALYSIS") == 7


def test_standard_five_chapter_coverage_is_complete():
    coverage = detect_standard_chapter_coverage(
        complete_standard_paragraphs()
    )
    assert coverage["complete"] is True
    assert coverage["missing_functions"] == []


def test_results_and_discussion_may_be_separated_with_final_chapter_shifted():
    rows = [
        paragraph("CHAPTER ONE INTRODUCTION", 1, number=1),
        paragraph("CHAPTER TWO LITERATURE REVIEW", 2, number=2),
        paragraph("CHAPTER THREE RESEARCH METHODS", 3, number=3),
        paragraph("CHAPTER FOUR RESULTS", 4, number=4),
        paragraph("CHAPTER FIVE DISCUSSION", 5, number=5),
        paragraph(
            "CHAPTER SIX SUMMARY, CONCLUSIONS AND RECOMMENDATIONS",
            6,
            number=6,
        ),
    ]
    coverage = detect_standard_chapter_coverage(rows)
    assert coverage["complete"] is True
    assert coverage["optional_chapters"] == [6]


def test_incomplete_full_thesis_is_rejected_before_review():
    rows = complete_standard_paragraphs()[:-1]
    with pytest.raises(ValueError, match="not complete"):
        _partition_submission_for_review(
            rows,
            selected_chapter=None,
            full_thesis=True,
            filename="thesis.docx",
        )


def test_selected_chapter_is_isolated_and_others_become_context():
    rows = complete_standard_paragraphs()
    rows.extend([
        paragraph("Chapter Two paragraph", 2, heading=False, number=6),
        paragraph("Chapter Three paragraph", 3, heading=False, number=7),
    ])
    partition = _partition_submission_for_review(
        rows,
        selected_chapter=3,
        full_thesis=False,
        filename="composite.docx",
    )
    assert {
        row["chapter_number"] for row in partition["review_paragraphs"]
    } == {3}
    assert {
        row["chapter_number"]
        for row in partition["embedded_context_paragraphs"]
    } == {1, 2, 4, 5}
    assert partition["reviewed_chapters"] == [3]
