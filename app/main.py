from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import router

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="ArticleReady AI",
    description="Journal article ideation, staged drafting, research-resource guidance, instrument planning, polishing and revision assistant.",
    version="1.4.2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/topic-ideas")
def topic_ideas_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "topic_ideas.html")


@app.get("/article-writer")
def article_writer_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_writer.html")


@app.get("/article")
def article_writer_alias() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_writer.html")


@app.get("/article-revision")
def article_revision_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_revision.html")


@app.get("/revise-article")
def article_revision_alias() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_revision.html")


@app.get("/pricing")
def pricing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "pricing.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": "ArticleReady AI"}
