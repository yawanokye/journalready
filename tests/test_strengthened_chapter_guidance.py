from app.academic_review_guide import guide_for_heading
from app.academic_ai_engine import CHAPTER_DIMENSIONS


def test_problem_guide_contains_research_problem_characteristics():
    guide = " ".join(guide_for_heading("Statement of the Problem", 20)).lower()
    assert "specific" in guide
    assert "researchable" in guide
    assert "knowledge gap" in guide
    assert "actual study context" in guide


def test_literature_review_guide_requires_concepts_theory_and_synthesis():
    guide = " ".join(guide_for_heading("Literature Review", 30)).lower()
    assert "central concepts" in guide
    assert "theory" in guide
    assert "rather than enumerated study by study" in guide


def test_chapter_dimensions_include_required_strengthening():
    chapter_one = " ".join(CHAPTER_DIMENSIONS[1]).lower()
    chapter_four = " ".join(CHAPTER_DIMENSIONS[4]).lower()
    chapter_five = " ".join(CHAPTER_DIMENSIONS[5]).lower()
    assert "objectives that flow directly from the problem" in chapter_one
    assert "internal accuracy" in chapter_four
    assert "without repeating the analysis" in chapter_five
