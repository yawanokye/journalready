from pathlib import Path


def test_summary_is_defined_before_degree_contract_rescue():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    summary_index = source.rfind('summary = review.get("summary") or {}', 0, source.index('required_categories = _degree_required_public_categories'))
    required_index = source.index('required_categories = _degree_required_public_categories')
    assert summary_index >= 0
    assert summary_index < required_index
    between = source[summary_index:required_index]
    assert 'if not isinstance(summary, dict):' in between
