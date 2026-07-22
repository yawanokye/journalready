import app.review_engine as review_engine
from app.statistical_review import build_statistical_review


def test_review_engine_imports_statistical_review_builder():
    assert review_engine.build_statistical_review is build_statistical_review


def test_statistical_review_builder_runs_for_empty_chapter():
    result = build_statistical_review([], chapter_numbers=[3])
    assert result["chapter_numbers"] == [3]
    assert result["warning_count"] == 0
    assert result["diagnostic_inventory"]["any_diagnostics_present"] is False
