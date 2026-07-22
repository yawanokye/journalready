import pytest

from app.document_parser import detect_document_chapter_profile, detect_standard_chapter_coverage
from app.review_engine import _partition_submission_for_review


def heading(text, chapter, paragraph, *, marker=None, section_chapter=None):
    return {
        "text": text,
        "paragraph": paragraph,
        "page": None,
        "is_heading": True,
        "heading": text,
        "chapter_number": chapter,
        "chapter_marker_number": marker,
        "section_number_chapter": section_chapter,
        "section_number": None,
    }


def chapters_four_and_five():
    return [
        heading("4.0 RESULTS AND DISCUSSION", 4, 1, section_chapter=4),
        heading("4.1 Introduction", 4, 2, section_chapter=4),
        heading("4.2 Results", 4, 3, section_chapter=4),
        heading("4.3 Discussion of Findings", 4, 4, section_chapter=4),
        heading("5.0 SUMMARY, CONCLUSIONS AND RECOMMENDATIONS", 5, 5, section_chapter=5),
        heading("5.1 Summary of Findings", 5, 6, section_chapter=5),
        heading("5.2 Conclusions", 5, 7, section_chapter=5),
        heading("5.3 Recommendations", 5, 8, section_chapter=5),
    ]


def test_complete_thesis_with_only_chapters_four_and_five_lists_one_two_three():
    coverage = detect_standard_chapter_coverage(chapters_four_and_five())
    assert "Chapter One: Introduction" in coverage["missing_functions"]
    assert "Chapter Two: Literature Review" in coverage["missing_functions"]
    assert "Chapter Three: Research Methods" in coverage["missing_functions"]


def test_chapter_one_selection_rejects_chapters_four_and_five():
    with pytest.raises(ValueError, match="selected Chapter One"):
        _partition_submission_for_review(
            chapters_four_and_five(),
            selected_chapter=1,
            full_thesis=False,
            filename="chapters-4-5.docx",
        )


def test_numbered_sections_identify_uploaded_chapters():
    profile = detect_document_chapter_profile(chapters_four_and_five())
    assert profile["detected_chapters"] == [4, 5]


def test_introduction_subheading_inside_chapter_four_does_not_create_chapter_one():
    profile = detect_document_chapter_profile(chapters_four_and_five())
    assert 1 not in profile["detected_chapters"]


def test_selected_chapter_four_is_isolated_from_chapter_five():
    partition = _partition_submission_for_review(
        chapters_four_and_five(),
        selected_chapter=4,
        full_thesis=False,
        filename="chapters-4-5.docx",
    )
    assert {row["chapter_number"] for row in partition["review_paragraphs"]} == {4}
    assert {row["chapter_number"] for row in partition["embedded_context_paragraphs"]} == {5}
