from __future__ import annotations

import uuid

from app.ai_providers import ProviderResult
from app.ai_schemas import AIUsageRecord
from app.checkpointing import (
    CheckpointManager,
    load_job_payload,
    payload_available,
    save_job_payload,
)
from app.database import ReviewCheckpoint, SessionLocal, init_db


def test_saved_job_payload_round_trips_all_uploaded_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.checkpointing.storage_root",
        lambda: tmp_path,
    )
    job_id = uuid.uuid4().hex
    payload = {
        "filename": "thesis.docx",
        "data": b"main-thesis",
        "academic_level": "PhD",
        "workflow_type": "external_assessment",
        "context_documents": [
            {"filename": "chapter-one.docx", "data": b"context-one"}
        ],
        "supervisor_comment_documents": [
            {"filename": "examiner.docx", "data": b"examiner-report"}
        ],
        "original_document": {
            "filename": "earlier.docx",
            "data": b"earlier-thesis",
        },
    }

    manifest = save_job_payload(job_id, payload)
    restored = load_job_payload(job_id)

    assert manifest["document_hash"]
    assert manifest["payload_hash"]
    assert payload_available(job_id) is True
    assert restored["data"] == b"main-thesis"
    assert restored["context_documents"][0]["data"] == b"context-one"
    assert (
        restored["supervisor_comment_documents"][0]["data"]
        == b"examiner-report"
    )
    assert restored["original_document"]["data"] == b"earlier-thesis"
    assert restored["payload_hash"] == manifest["payload_hash"]


def test_provider_checkpoint_is_reused_without_another_model_call(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.checkpointing.storage_root",
        lambda: tmp_path,
    )
    init_db()
    job_id = uuid.uuid4().hex
    manager = CheckpointManager(job_id, "document-hash")
    result = ProviderResult(
        data={"reviews": [{"section_key": "chapter-one"}]},
        usage=AIUsageRecord(
            provider="openai",
            model="o3-mini",
            purpose="test",
            input_tokens=100,
            output_tokens=25,
        ),
    )

    manager.save_provider_result(
        "academic-primary-test",
        result,
        input_hash="input-hash",
        progress=50,
        message="Saved",
    )
    restored = manager.load_provider_result(
        "academic-primary-test",
        expected_input_hash="input-hash",
    )

    assert restored is not None
    assert restored.data == result.data
    assert restored.usage.input_tokens == 100
    assert manager.completed_count() == 1

    with SessionLocal() as db:
        db.query(ReviewCheckpoint).filter(
            ReviewCheckpoint.job_id == job_id
        ).delete()
        db.commit()


def test_checkpoint_input_hash_prevents_stale_reuse(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.checkpointing.storage_root",
        lambda: tmp_path,
    )
    init_db()
    job_id = uuid.uuid4().hex
    manager = CheckpointManager(job_id)
    manager.save(
        "document-analysis",
        {"review": {"review_id": "one"}},
        input_hash="old-input",
    )

    assert (
        manager.load(
            "document-analysis",
            expected_input_hash="new-input",
        )
        is None
    )

    with SessionLocal() as db:
        db.query(ReviewCheckpoint).filter(
            ReviewCheckpoint.job_id == job_id
        ).delete()
        db.commit()
