from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.article_ideas_service import generate_article_ideas
from app.article_service import draft_journal_article, export_article_docx, find_article_sources
from app.article_revision_service import export_revised_article_docx, revise_article
from app.file_extractor import extract_uploaded_text
from app.research_resources import discover_research_resources
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


@router.post("/article-ideas")
def create_article_ideas(payload: ArticleIdeaRequest) -> dict[str, Any]:
    try:
        return generate_article_ideas(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
def create_journal_article(payload: JournalArticleRequest) -> dict[str, Any]:
    try:
        return draft_journal_article(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Journal article drafting failed: {str(exc)[:240]}") from exc


@router.post("/articles/export")
def export_journal_article(payload: ArticleExportRequest) -> StreamingResponse:
    try:
        stream, filename = export_article_docx(payload.article_text, payload.article_title)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article export failed: {str(exc)[:240]}") from exc


@router.post("/articles/revise")
def revise_existing_article(payload: ArticleRevisionRequest) -> dict[str, Any]:
    try:
        return revise_article(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article revision failed: {str(exc)[:240]}") from exc


@router.post("/articles/revision/export")
def export_revised_article(payload: ArticleRevisionExportRequest) -> StreamingResponse:
    try:
        stream, filename = export_revised_article_docx(
            original_article_text=payload.original_article_text,
            revised_article_text=payload.revised_article_text,
            title=payload.article_title,
            revision_report=payload.revision_report,
            reviewer_response_matrix=payload.reviewer_response_matrix,
            include_revision_report=payload.include_revision_report,
        )
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Revision export failed: {str(exc)[:240]}") from exc
