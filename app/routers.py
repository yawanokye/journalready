from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.article_ideas_service import generate_article_ideas
from app.article_service import draft_journal_article, export_article_docx, find_article_sources
from app.article_revision_service import export_revised_article_docx, revise_article
from app.file_extractor import extract_uploaded_text
from app.research_resources import discover_research_resources
from app.payments.guard import PaymentRequiredError, credentials_from_headers, make_payment_required_detail, paid_article_action
from app.schemas import (
    ArticleExportRequest,
    ArticleIdeaRequest,
    ArticleRevisionExportRequest,
    ArticleRevisionRequest,
    ArticleSourceSearchRequest,
    JournalArticleRequest,
    ResearchResourceRequest,
)

router = APIRouter(prefix="/api", tags=["ArticleReady AI"])


def _payment_exception(action: str, plan_key: str, message: str = "") -> HTTPException:
    detail = make_payment_required_detail(action, plan_key)
    if message:
        detail["message"] = message
    return HTTPException(status_code=402, detail=detail)


def _recommended_draft_plan(data: dict[str, Any]) -> str:
    article_type = str(data.get("article_type") or "").lower()
    stage = str(data.get("draft_stage") or "")
    target_words = int(data.get("target_word_count") or 0)
    if stage == "initial_to_methods":
        return "stage1_article"
    if any(term in article_type for term in ["review", "scoping", "conceptual", "theory", "systematic"]):
        return "review_conceptual_scoping"
    if target_words and target_words > 9000:
        return "long_article_plus"
    return "standard_full_article"


def _recommended_revision_plan(data: dict[str, Any]) -> str:
    comments = str(data.get("review_comments") or "").strip()
    level = str(data.get("revision_level") or "")
    if comments:
        return "reviewer_comment_revision"
    if "extra" in level.lower():
        return "extra_revision_pass"
    return "article_revision"


@router.post("/article-ideas")
def create_article_ideas(payload: ArticleIdeaRequest, request: Request) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        creds = credentials_from_headers(request.headers)
        free_trial = int(data.get("max_ideas") or 0) <= 3 and not ((creds["purchase_id"] and creds["access_token"]) or creds["developer_token"])
        if free_trial:
            # The free trial deliberately excludes live scholarly/resource searches.
            # Paid access is required for source-supported portfolios and for more than three ideas.
            data["include_source_search"] = False
            data["include_research_resource_search"] = False
            return generate_article_ideas(data)
        try:
            with paid_article_action(
                purchase_id=creds["purchase_id"],
                access_token=creds["access_token"],
                developer_token=creds["developer_token"],
                action="idea",
                metadata={"plan_recommended": "article_ideas", "max_ideas": data.get("max_ideas")},
            ):
                return generate_article_ideas(data)
        except PaymentRequiredError as exc:
            raise _payment_exception("idea", "article_ideas", str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article topic generation failed: {str(exc)[:240]}") from exc


@router.post("/articles/research-resources")
def search_research_resources(payload: ResearchResourceRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        return discover_research_resources(
            data,
            extra_text=" ".join([data.get("objective", ""), data.get("objectives", ""), data.get("extraction_focus", "")]),
            max_results=int(data.get("max_results") or 6),
            include_live_search=bool(data.get("include_live_search", True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Research resource search failed: {str(exc)[:240]}") from exc


@router.post("/articles/find-sources")
def search_article_sources(payload: ArticleSourceSearchRequest) -> dict[str, Any]:
    try:
        return find_article_sources(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article source search failed: {str(exc)[:240]}") from exc


@router.post("/articles/extract-file")
async def extract_article_file(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        content = await file.read()
        return extract_uploaded_text(file.filename or "upload", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"File extraction failed: {str(exc)[:240]}") from exc


@router.post("/articles/draft")
def create_journal_article(payload: JournalArticleRequest, request: Request) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        plan_key = _recommended_draft_plan(data)
        creds = credentials_from_headers(request.headers)
        try:
            with paid_article_action(
                purchase_id=creds["purchase_id"],
                access_token=creds["access_token"],
                developer_token=creds["developer_token"],
                action="draft",
                metadata={"plan_recommended": plan_key, "article_title": data.get("article_title"), "draft_stage": data.get("draft_stage")},
            ):
                return draft_journal_article(data)
        except PaymentRequiredError as exc:
            raise _payment_exception("draft", plan_key, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Journal article drafting failed: {str(exc)[:240]}") from exc


@router.post("/articles/export")
def export_journal_article(payload: ArticleExportRequest, request: Request) -> StreamingResponse:
    try:
        creds = credentials_from_headers(request.headers)
        try:
            with paid_article_action(
                purchase_id=creds["purchase_id"],
                access_token=creds["access_token"],
                developer_token=creds["developer_token"],
                action="export",
                metadata={"article_title": payload.article_title, "export_type": "article_draft"},
            ):
                stream, filename = export_article_docx(payload.article_text, payload.article_title)
        except PaymentRequiredError as exc:
            raise _payment_exception("export", "standard_full_article", str(exc)) from exc
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article export failed: {str(exc)[:240]}") from exc


@router.post("/articles/revise")
def revise_existing_article(payload: ArticleRevisionRequest, request: Request) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        plan_key = _recommended_revision_plan(data)
        creds = credentials_from_headers(request.headers)
        try:
            with paid_article_action(
                purchase_id=creds["purchase_id"],
                access_token=creds["access_token"],
                developer_token=creds["developer_token"],
                action="revision",
                metadata={"plan_recommended": plan_key, "article_title": data.get("article_title"), "has_review_comments": bool(str(data.get("review_comments") or "").strip())},
            ):
                return revise_article(data)
        except PaymentRequiredError as exc:
            raise _payment_exception("revision", plan_key, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article revision failed: {str(exc)[:240]}") from exc


@router.post("/articles/revision/export")
def export_revised_article(payload: ArticleRevisionExportRequest, request: Request) -> StreamingResponse:
    try:
        creds = credentials_from_headers(request.headers)
        try:
            with paid_article_action(
                purchase_id=creds["purchase_id"],
                access_token=creds["access_token"],
                developer_token=creds["developer_token"],
                action="export",
                metadata={"article_title": payload.article_title, "export_type": "revised_article"},
            ):
                stream, filename = export_revised_article_docx(
                    original_article_text=payload.original_article_text,
                    revised_article_text=payload.revised_article_text,
                    title=payload.article_title,
                    revision_report=payload.revision_report,
                    reviewer_response_matrix=payload.reviewer_response_matrix,
                    include_revision_report=payload.include_revision_report,
                )
        except PaymentRequiredError as exc:
            raise _payment_exception("export", "article_revision", str(exc)) from exc
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Revision export failed: {str(exc)[:240]}") from exc
