from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.article_ideas_service import generate_article_ideas
from app.article_service import draft_journal_article, export_article_docx
from app.schemas import ArticleExportRequest, ArticleIdeaRequest, JournalArticleRequest

router = APIRouter(prefix="/api", tags=["JournalReady AI"])


@router.post("/article-ideas")
def create_article_ideas(payload: ArticleIdeaRequest) -> dict[str, Any]:
    try:
        return generate_article_ideas(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Article topic generation failed: {str(exc)[:240]}") from exc


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
