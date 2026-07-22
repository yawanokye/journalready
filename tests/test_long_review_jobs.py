from pathlib import Path


def test_browser_polling_is_resumable():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "ACTIVE_REVIEW_JOB_KEY" in js
    assert "resumeActiveReviewJob" in js
    assert "2 * 60 * 60 * 1000" in js
    assert "fetchCompletedReview" in js
    assert "still taking longer than expected" not in js


def test_server_returns_result_url():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert "result_url" in source
    assert "AI_JOB_MAX_SECONDS" in source
    assert "asyncio.wait_for" in source
