from pathlib import Path


def test_browser_uses_highest_progress_only():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "let highestDisplayedProgress = 2;" in js
    assert "highestDisplayedProgress = Math.max(" in js
    assert "progressBar.dataset.progress" in js


def test_reconnect_restores_saved_progress():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "highestProgress" in js
    assert "activeJob.highestProgress" in js
    assert "{ reset: true }" in js


def test_new_review_resets_progress():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert '"Uploading and queuing the external assessment"' in js
    assert "setProgress(" in js
