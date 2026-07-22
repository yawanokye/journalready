from pathlib import Path


def test_external_assessment_is_a_separate_workflow() -> None:
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert 'name="workflow_type" value="supervisory_review"' in html
    assert 'name="workflow_type" value="external_assessment"' in html
    assert 'id="assessmentMetadataFields"' in html
    assert 'id="thesisTitle"' in html
    assert 'value="corrected_thesis_verification"' in html


def test_external_assessment_outputs_are_available_in_interface() -> None:
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    for button_id in (
        "externalReportButton",
        "correctionsScheduleButton",
        "confidentialRecommendationButton",
        "oralQuestionsButton",
    ):
        assert f'id="{button_id}"' in html


def test_external_workflow_forces_complete_thesis_and_level_standard() -> None:
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'selectedWorkflow() === "external_assessment"' in js
    assert 'body.set("review_scope", "full_thesis")' in js
    assert 'External Assessment automatically applies the examination standard' in js
    assert 'Submit thesis for external assessment' in js


def test_chapter_one_is_a_critical_external_assessment_gate() -> None:
    prompt = Path("app/external_assessment.py").read_text(encoding="utf-8")
    assert "Chapter One or the equivalent foundational chapter is a critical examination" in prompt
    assert "no_pass_without_corrections_when_chapter_one_materially_deficient" in prompt
