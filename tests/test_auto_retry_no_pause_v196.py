from pathlib import Path


def test_transient_failures_queue_instead_of_pause():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert 'status="queued"' in source
    assert "_queue_automatic_retry(" in source
    assert 'record.status = "queued"' in source
    transient_block = source[source.index("except ExternalAssessmentValidationError"):source.index("finally:", source.index("except ExternalAssessmentValidationError"))]
    assert 'status="paused"' not in transient_block
    assert "retrying automatically" in transient_block.lower() or "automatically" in transient_block.lower()


def test_fresh_generation_is_used_for_automatic_retries():
    academic = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    external = Path("app/external_assessment.py").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")
    assert '"retry_generation": int(retry_generation or 0)' in academic
    assert '"retry_generation": int(retry_generation or 0)' in external
    assert "retry_generation=int(JOB_CACHE.get(job_id, {}).get(\"resume_count\") or 0)" in main


def test_last_mile_expert_rescue_prevents_empty_annotation_output():
    source = Path("app/academic_ai_engine.py").read_text(encoding="utf-8")
    assert "direct_grounded_comment_rescue" in source
    assert "direct_expert_rescue" in source
    assert "no factual, correctly placed" in source


def test_native_word_comments_remain_required():
    source = Path("app/main.py").read_text(encoding="utf-8")
    exporter = Path("app/annotated_exporter.py").read_text(encoding="utf-8")
    assert "actual_comments = native_comment_count(annotated_data)" in source
    assert "if actual_comments < 1" in source
    assert "document.add_comment" in exporter
    assert "2.6.0-final-generic-natural-reconciled-review" in exporter
