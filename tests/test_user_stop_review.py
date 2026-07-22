from pathlib import Path


def test_portal_allows_active_reviews_to_be_stopped_and_resumed():
    html = Path("app/templates/portal.html").read_text(encoding="utf-8")
    assert "item.status in ['queued', 'processing']" in html
    assert "/api/review/jobs/{{ item.job_id }}/stop" in html
    assert "Stop review" in html
    assert "item.status in ['paused', 'stopped', 'failed']" in html


def test_stop_endpoint_preserves_checkpoints_and_disables_auto_resume():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/review/jobs/{job_id}/stop"' in source
    assert 'record.status = "stopped"' in source
    assert 'record.recoverable = bool(saved_payload_available)' in source
    assert 'task.cancel()' in source
    assert 'Review stopped by the user. Completed checkpoints were retained.' in source
    assert 'ReviewRecord.status.in_(["queued", "processing", "paused"])' in source


def test_workspace_exposes_stop_control_for_active_job():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    javascript = Path("app/static/app.js").read_text(encoding="utf-8")
    assert 'id="stopReviewButton"' in html
    assert "requestJobStop" in javascript
    assert 'job.status === "stopped"' in javascript
    assert 'window.location.assign("/portal")' in javascript
