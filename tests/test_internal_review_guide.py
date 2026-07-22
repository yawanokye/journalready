from app.academic_review_guide import guide_for_heading


def test_guide_is_broad_and_has_no_codes():
    values = guide_for_heading("Statement of the Problem")
    assert values
    assert any("researchable" in value or "evidence" in value for value in values)
    assert all(not value.startswith(("A1", "B2", "D4")) for value in values)


def test_methods_guide_is_contextual():
    values = guide_for_heading("Sample Size Determination and Sampling Technique")
    assert any("sample-size" in value or "sampling" in value for value in values)
