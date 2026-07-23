from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.developer_access import router as developer_access_router
from app.payments.api import api_router as payments_router
from app.payments.store import init_payment_tables
from app.review_workspace_api import router as review_workspace_router
from app.review_workspace_store import init_review_workspace_tables
from app.routers import router
from app.security import ArticleReadySecurityMiddleware, allowed_hosts, allowed_origins, env_bool

load_dotenv()

LOGGER = logging.getLogger("articleready")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_payment_tables()
    init_review_workspace_tables()
    if env_bool("ARTICLEREADY_DEVELOPER_ACCESS_ENABLED", False) and not os.getenv(
        "ARTICLEREADY_DEVELOPER_ACCESS_SECRET", ""
    ).strip():
        LOGGER.warning(
            "Developer access is enabled without ARTICLEREADY_DEVELOPER_ACCESS_SECRET. "
            "Configure a separate long random signing secret before production use."
        )
    yield


app = FastAPI(
    title="ArticleReady AI",
    description="Journal article ideation, auditable review-evidence management, staged drafting, research-resource guidance, instrument planning, polishing and revision assistant.",
    version="2.1.0",
    docs_url="/docs" if env_bool("ARTICLEREADY_ENABLE_API_DOCS", False) else None,
    redoc_url="/redoc" if env_bool("ARTICLEREADY_ENABLE_API_DOCS", False) else None,
    openapi_url="/openapi.json" if env_bool("ARTICLEREADY_ENABLE_API_DOCS", False) else None,
    lifespan=lifespan,
)

# Validate Host before application routing. Include testserver and local hosts in
# ARTICLEREADY_ALLOWED_HOSTS for tests and local development.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())

# Same-origin requests need no CORS permission. Only explicitly configured origins
# are allowed, and wildcard origins are deliberately ignored.
_origins = allowed_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-Requested-With",
            "X-ArticleReady-Purchase-Id",
            "X-ArticleReady-Access-Token",
            "X-ArticleReady-Developer-Token",
            "X-Review-Workspace-Token",
            "X-Request-ID",
            "X-Paystack-Signature",
            "Stripe-Signature",
        ],
        expose_headers=["Content-Disposition", "X-Request-ID", "Retry-After", "X-RateLimit-Remaining"],
        max_age=600,
    )

app.add_middleware(ArticleReadySecurityMiddleware)

app.include_router(router)
app.include_router(payments_router)
app.include_router(developer_access_router)
app.include_router(review_workspace_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def prevent_stale_sensitive_assets(request, call_next):
    response = await call_next(request)
    path = request.url.path.lower()
    no_cache_paths = {
        "/",
        "/topic-ideas",
        "/article-writer",
        "/article-revision",
        "/review-evidence",
        "/pricing",
        "/payment/recover",
        "/developer-access",
    }
    if path.endswith(".html") or path.endswith(".js") or path in no_cache_paths:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")


@app.get("/topic-ideas")
def topic_ideas_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "topic_ideas.html", media_type="text/html; charset=utf-8")


@app.get("/article-writer")
def article_writer_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_writer.html", media_type="text/html; charset=utf-8")


@app.get("/article")
def article_writer_alias() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_writer.html", media_type="text/html; charset=utf-8")


@app.get("/article-revision")
def article_revision_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_revision.html", media_type="text/html; charset=utf-8")


@app.get("/revise-article")
def article_revision_alias() -> FileResponse:
    return FileResponse(STATIC_DIR / "article_revision.html", media_type="text/html; charset=utf-8")


@app.get("/review-evidence")
def review_evidence_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "review_evidence.html", media_type="text/html; charset=utf-8")


@app.get("/pricing")
def pricing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "pricing.html", media_type="text/html; charset=utf-8")


@app.get("/payment/recover")
def payment_recovery_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "payment_recover.html", media_type="text/html; charset=utf-8")


@app.get("/developer-access")
def developer_access_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "developer_access.html", media_type="text/html; charset=utf-8")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "favicon.ico",
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.get("/robots.txt", include_in_schema=False)
def robots_txt() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "robots.txt",
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sitemap.xml",
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/.well-known/security.txt", include_in_schema=False)
def security_txt() -> PlainTextResponse:
    contact = os.getenv("ARTICLEREADY_SECURITY_CONTACT", "mailto:aadam@ucc.edu.gh").strip()
    canonical = os.getenv(
        "ARTICLEREADY_SECURITY_CANONICAL",
        "https://articlereadyai.com/.well-known/security.txt",
    ).strip()
    body = f"Contact: {contact}\nCanonical: {canonical}\nPreferred-Languages: en\n"
    return PlainTextResponse(body, headers={"Cache-Control": "public, max-age=3600"})



@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
