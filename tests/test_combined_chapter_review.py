import pytest

from app.review_engine import (
    _candidate_paragraphs,
    _partition_submission_for_review,
    _select_rules,
)


def heading(text, chapter, paragraph):
    return {
        "text": text,
        "heading": text,
        "chapter_number": chapter,
        "chapter_marker_number": chapter,
        "chapter_title_number": None,
        "section_number_chapter": None,
        "section_number": None,
        "paragraph": paragraph,
        "page": None,
        "is_heading": True,
    }


def body(text, chapter, heading_text, paragraph):
    return {
        "text": text,
        "heading": heading_text,
        "chapter_number": chapter,
        "chapter_marker_number": None,
        "chapter_title_number": None,
        "section_number_chapter": None,
        "section_number": None,
        "paragraph": paragraph,
        "page": None,
        "is_heading": False,
    }


def chapters_one_to_five():
    rows = []
    titles = {
        1: "CHAPTER ONE INTRODUCTION",
        2: "CHAPTER TWO LITERATURE REVIEW",
        3: "CHAPTER THREE RESEARCH METHODS",
        4: "CHAPTER FOUR RESULTS AND DISCUSSION",
        5: "CHAPTER FIVE SUMMARY, CONCLUSIONS AND RECOMMENDATIONS",
    }
    paragraph = 1
    for chapter, title in titles.items():
        rows.append(heading(title, chapter, paragraph))
        paragraph += 1
        rows.append(
            body(
                f"Substantive content for chapter {chapter}.",
                chapter,
                title,
                paragraph,
            )
        )
        paragraph += 1
    return rows


def test_chapters_one_to_three_are_reviewed_together():
    partition = _partition_submission_for_review(
        chapters_one_to_five(),
        selected_chapter=3,
        combined_chapter_end=3,
        full_thesis=False,
        filename="combined.docx",
        academic_level="Research Masters / MPhil",
    )
    assert partition["structure_mode"] == "combined_chapters"
    assert partition["reviewed_chapters"] == [1, 2, 3]
    assert {
        row["chapter_number"]
        for row in partition["review_paragraphs"]
    } == {1, 2, 3}
    assert {
        row["chapter_number"]
        for row in partition["embedded_context_paragraphs"]
    } == {4, 5}


def test_missing_preceding_chapter_rejects_combined_review():
    rows = [
        row
        for row in chapters_one_to_five()
        if row["chapter_number"] != 2
    ]
    with pytest.raises(ValueError, match="Missing from the selected range"):
        _partition_submission_for_review(
            rows,
            selected_chapter=3,
            combined_chapter_end=3,
            full_thesis=False,
            filename="chapters-1-and-3.docx",
            academic_level="Research Masters / MPhil",
        )


def test_combined_rule_selection_covers_every_submitted_chapter():
    rules = _select_rules(
        selected_chapter=4,
        full_thesis=False,
        current_chapters={1, 2, 3, 4},
        combined_scope=True,
    )
    chapter_keys = {rule["chapter_key"] for rule in rules}
    assert {"B", "C", "D", "E"}.issubset(chapter_keys)
    assert "F" not in chapter_keys
    assert {"A1", "A2", "A3", "A4"}.issubset(
        {rule["code"] for rule in rules}
    )


def test_combined_rule_search_uses_its_own_chapter():
    paragraphs = chapters_one_to_five()
    method_rule = {
        "chapter_number": 3,
        "headings": ["research methods"],
    }
    candidates = _candidate_paragraphs(
        paragraphs,
        method_rule,
        selected_chapter=4,
        full_thesis=False,
        review_chapters={1, 2, 3, 4},
    )
    assert candidates
    assert {
        row["chapter_number"] for row in candidates
    } == {3}


def test_invalid_combined_range_is_rejected():
    with pytest.raises(ValueError, match="1–2, 1–3, 1–4 or 1–5"):
        _partition_submission_for_review(
            chapters_one_to_five(),
            selected_chapter=None,
            combined_chapter_end=1,
            full_thesis=False,
            filename="combined.docx",
            academic_level="Bachelors",
        )
