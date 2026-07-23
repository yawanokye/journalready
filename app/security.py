from __future__ import annotations

import os
import re
import secrets
import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_TRUE = {"1", "true", "yes", "on"}
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def env_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def allowed_origins() -> list[str]:
    values = env_csv(
        "ARTICLEREADY_ALLOWED_ORIGINS",
        "https://articlereadyai.com,https://www.articlereadyai.com,http://localhost:8000,http://127.0.0.1:8000",
    )
    # Wildcard origins cannot safely be combined with credentialed or private
    # application requests. Ignore them rather than silently weakening CORS.
    return [value for value in values if value != "*"]


def allowed_hosts() -> list[str]:
    return env_csv(
        "ARTICLEREADY_ALLOWED_HOSTS",
        "articlereadyai.com,www.articlereadyai.com,*.onrender.com,localhost,127.0.0.1,testserver",
    )


def _client_ip(request: Request) -> str:
    if env_bool("ARTICLEREADY_TRUST_PROXY_HEADERS", True):
        forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded[:128]
    return str(request.client.host if request.client else "unknown")[:128]


def _request_id(request: Request) -> str:
    supplied = str(request.headers.get("x-request-id") or "").strip()
    if supplied and _REQUEST_ID_RE.fullmatch(supplied):
        return supplied
    return secrets.token_hex(12)


@dataclass(frozen=True)
class RateRule:
    requests: int
    window_seconds: int


_RATE_RULES: dict[tuple[str, str], RateRule] = {
    ("POST", "/api/developer/login"): RateRule(5, 15 * 60),
    ("POST", "/api/payments/recover-access"): RateRule(5, 15 * 60),
    ("POST", "/api/payments/checkout"): RateRule(15, 5 * 60),
    ("POST", "/api/article-ideas"): RateRule(15, 60),
    ("POST", "/api/articles/find-sources"): RateRule(20, 60),
    ("POST", "/api/articles/research-resources"): RateRule(20, 60),
    ("POST", "/api/articles/draft"): RateRule(6, 5 * 60),
    ("POST", "/api/articles/revise"): RateRule(6, 5 * 60),
    ("POST", "/api/review-workspace/projects"): RateRule(10, 5 * 60),
}


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_prune = 0.0

    def check(self, key: str, rule: RateRule) -> tuple[bool, int, int]:
        now = time.monotonic()
        threshold = now - rule.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= threshold:
                events.popleft()
            if len(events) >= rule.requests:
                retry_after = max(1, int(rule.window_seconds - (now - events[0])))
                return False, retry_after, 0
            events.append(now)
            remaining = max(0, rule.requests - len(events))
            if now - self._last_prune > 300:
                self._prune(now)
            return True, 0, remaining

    def _prune(self, now: float) -> None:
        stale_before = now - 3600
        for key in list(self._events):
            events = self._events[key]
            while events and events[0] < stale_before:
                events.popleft()
            if not events:
                self._events.pop(key, None)
        self._last_prune = now


_LIMITER = _SlidingWindowLimiter()


class ArticleReadySecurityMiddleware(BaseHTTPMiddleware):
    """Apply practical security controls without changing application workflows."""

    async def dispatch(self, request: Request, call_next):
        request_id = _request_id(request)
        path = request.url.path
        method = request.method.upper()

        size_response = self._check_request_size(request, request_id)
        if size_response is not None:
            self._apply_headers(request, size_response, request_id)
            return size_response

        rule = _RATE_RULES.get((method, path))
        if rule and env_bool("ARTICLEREADY_RATE_LIMIT_ENABLED", True):
            identity = _client_ip(request)
            if path not in {"/api/developer/login", "/api/payments/recover-access"}:
                private_id = (
                    request.headers.get("x-articleready-purchase-id")
                    or request.headers.get("x-articleready-developer-token")
                    or request.headers.get("x-review-workspace-token")
                    or ""
                )
                if private_id:
                    identity = "credential:" + hashlib.sha256(str(private_id).encode("utf-8")).hexdigest()[:24]
            key = f"{identity}:{method}:{path}"
            allowed, retry_after, remaining = _LIMITER.check(key, rule)
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "rate_limited",
                            "message": "Too many requests. Wait briefly and try again.",
                            "retry_after_seconds": retry_after,
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["Retry-After"] = str(retry_after)
                self._apply_headers(request, response, request_id)
                return response
        else:
            remaining = None

        try:
            response = await call_next(request)
        except Exception:
            # Let FastAPI's exception handlers preserve the correct error response.
            raise

        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        self._apply_headers(request, response, request_id)
        return response

    @staticmethod
    def _check_request_size(request: Request, request_id: str) -> Response | None:
        raw_length = request.headers.get("content-length")
        if not raw_length:
            return None
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"detail": {"code": "invalid_content_length", "message": "Invalid request size header.", "request_id": request_id}},
            )

        path = request.url.path
        if path.startswith("/api/review-workspace/") and (path.endswith("/imports") or path.endswith("/full-text")):
            max_bytes = int(os.getenv("ARTICLEREADY_MAX_REVIEW_UPLOAD_BYTES", str(52 * 1024 * 1024)))
        elif path == "/api/articles/extract-file":
            max_bytes = int(os.getenv("ARTICLEREADY_MAX_UPLOAD_REQUEST_BYTES", str(17 * 1024 * 1024)))
        elif path.startswith("/api/"):
            max_bytes = int(os.getenv("ARTICLEREADY_MAX_JSON_REQUEST_BYTES", str(6 * 1024 * 1024)))
        else:
            max_bytes = int(os.getenv("ARTICLEREADY_MAX_REQUEST_BYTES", str(2 * 1024 * 1024)))

        if content_length <= max_bytes:
            return None
        return JSONResponse(
            status_code=413,
            content={
                "detail": {
                    "code": "request_too_large",
                    "message": f"The request exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                    "request_id": request_id,
                }
            },
        )

    @staticmethod
    def _apply_headers(request: Request, response: Response, request_id: str) -> None:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), payment=(self)"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-XSS-Protection"] = "0"
        forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
        is_https = request.url.scheme == "https" or forwarded_proto == "https"
        csp = os.getenv(
            "ARTICLEREADY_CONTENT_SECURITY_POLICY",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self' data:; connect-src 'self'; form-action 'self'",
        ).strip().rstrip(";")
        if is_https and env_bool("ARTICLEREADY_CSP_UPGRADE_INSECURE_REQUESTS", True):
            csp += "; upgrade-insecure-requests"
        response.headers["Content-Security-Policy"] = csp

        if is_https and env_bool("ARTICLEREADY_HSTS_ENABLED", True):
            response.headers["Strict-Transport-Security"] = os.getenv(
                "ARTICLEREADY_HSTS_VALUE",
                "max-age=31536000; includeSubDomains",
            )

        sensitive = (
            request.url.path.startswith("/api/")
            or request.url.path in {"/developer-access", "/review-evidence", "/payment/recover"}
        )
        if sensitive:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
