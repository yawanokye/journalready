from pathlib import Path


def test_previous_chapter_upload_is_optional_for_composite_files():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "previousFilesInput.required = false" in js
    assert "main upload does not already contain" in js
    assert "Other chapters are used for alignment only" in js
    assert "before running the review" not in js


def test_alignment_context_badge_is_not_misleading():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert "Alignment context" in html
    assert "Required for alignment" not in html
