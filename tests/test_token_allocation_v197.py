from __future__ import annotations

import io
from pathlib import Path

from docx import Document
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, ReviewRecord, TokenLedger, User
from app.token_budget import (
    TOKENS_PER_PAGE,
    adjust_allocation,
    estimate_document_pages,
    estimate_review_tokens,
    page_capacity,
    reserve_review_tokens,
    settle_review_tokens,
    usage_token_total,
)


def _docx_with_words(count: int) -> bytes:
    document = Document()
    document.add_paragraph(" ".join(f"word{i}" for i in range(count)))
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def _record(user_id: int) -> ReviewRecord:
    return ReviewRecord(
        job_id="quota-job",
        lecturer_id=user_id,
        filename="chapter.docx",
        academic_level="Research Masters (MPhil)",
        research_approach="Quantitative",
        review_scope="chapter",
        review_depth="standard",
        submission_stage="initial",
        workflow_type="supervisory_review",
        status="queued",
        progress=2,
        estimated_pages=2,
        token_estimate=9000,
        token_reserved=9000,
        token_accounting_status="reserved",
    )


def test_docx_pages_and_workflow_estimate_are_exposed() -> None:
    pages = estimate_document_pages(_docx_with_words(900), "chapter.docx")
    assert pages == 2
    estimate = estimate_review_tokens(pages, "supervisory_review", "standard")
    assert estimate.tokens_per_page == TOKENS_PER_PAGE["supervisory_standard"]
    assert estimate.base_tokens == 7000
    assert estimate.reserved_tokens == 9000
    assert page_capacity(4_025_000, "supervisory_standard") == 1000


def test_allocation_reservation_and_actual_usage_reconciliation() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        user = User(
            username="supervisor",
            password_hash="hash",
            role="lecturer",
            full_name="Test Supervisor",
            must_change_password=False,
            token_balance=0,
            token_allocated_total=0,
        )
        db.add(user)
        db.flush()
        adjust_allocation(
            db,
            user=user,
            token_amount=50_000,
            mode="add",
            note="Annual allocation",
            created_by_user_id=None,
        )
        assert user.token_balance == 50_000
        assert reserve_review_tokens(
            db,
            user=user,
            token_amount=9_000,
            pages=2,
            workflow_label="supervisory review",
            job_id="quota-job",
        )
        assert user.token_balance == 41_000
        assert user.token_reserved_total == 9_000

        record = _record(user.id)
        db.add(record)
        db.flush()
        settle_review_tokens(db, record=record, user=user, actual_tokens=7_500)
        assert user.token_balance == 42_500
        assert user.token_reserved_total == 0
        assert user.token_used_total == 7_500
        assert record.tokens_used == 7_500
        assert record.token_accounting_status == "settled"
        assert db.query(TokenLedger).count() == 3


def test_usage_total_counts_input_and_output_once() -> None:
    assert usage_token_total({"usage": [
        {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 250},
        {"input_tokens": 800, "output_tokens": 200},
    ]}) == 2250


def test_admin_dashboard_contains_individual_and_bulk_allocation_controls() -> None:
    template = Path("app/templates/admin_dashboard.html").read_text(encoding="utf-8")
    main = Path("app/main.py").read_text(encoding="utf-8")
    database = Path("app/database.py").read_text(encoding="utf-8")
    assert "/admin/tokens/bulk" in template
    assert "/tokens\"" in template
    assert "Expected standard pages" in template
    assert "reserve_review_tokens" in main
    assert "settle_review_tokens" in main
    assert 'APP_VERSION = "2.6.1"' in main
    assert "class TokenLedger" in database
