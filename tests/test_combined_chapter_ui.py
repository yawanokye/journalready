from pathlib import Path
import inspect

import app.main as main_module


def test_combined_chapter_scope_and_ranges_are_visible():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert 'value="chapter_range"' in html
    assert 'id="combinedChapterField"' in html
    assert 'value="2">Chapters One to Two' in html
    assert 'value="5">Chapters One to Five' in html


def test_combined_workflow_requires_the_ending_chapter():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'scope === "chapter_range"' in js
    assert "combinedChapterEnd.required = combined" in js
    assert "every chapter in the selected range" in js
    assert 'body.set("combined_chapter_end", String(rangeEnd))' in js


def test_api_accepts_combined_chapter_end():
    signature = inspect.signature(main_module.create_review)
    assert "combined_chapter_end" in signature.parameters
