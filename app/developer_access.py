from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["Developer access"])

_FAILED_ATTEMPTS: Dict[str, Deque[float]] = defaultdict(deque)
_ATTEMPT_LOCK = threading.Lock()


class DeveloperLoginRequest(BaseModel):
    email: str = Field(default="", max_length=254)
    access_code: str = Field(min_length=8, max_length=512)


class DeveloperStatusRequest(BaseModel):
    developer_token: str = Field(min_length=20, max_length=4096)


def _enabled() -> bool:
    return os.getenv("ARTICLEREADY_DEVELOPER_ACCESS_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _configured_email() -> str:
    return os.getenv("ARTICLEREADY_DEVELOPER_ACCESS_EMAIL", "").strip().lower()


def _configured_code() -> str:
    return os.getenv("ARTICLEREADY_DEVELOPER_ACCESS_CODE", "").strip()


def _configured_code_hash() -> str:
    return os.getenv("ARTICLEREADY_DEVELOPER_ACCESS_CODE_SHA256", "").strip().lower()


def _session_hours() -> int:
    try:
        value = int(os.getenv("ARTICLEREADY_DEVELOPER_SESSION_HOURS", "12") or 12)
    except ValueError:
        value = 12
    return min(max(value, 1), 72)


def _signing_secret() -> bytes:
    explicit = os.getenv("ARTICLEREADY_DEVELOPER_ACCESS_SECRET", "").strip()
    if explicit:
        return explicit.encode("utf-8")
    fallback = _configured_code() or _configured_code_hash()
    if not fallback:
        return b""
    return hashlib.sha256((fallback + "|articleready-developer-session").encode("utf-8")).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _code_matches(candidate: str) -> bool:
    candidate = str(candidate or "")
    configured_hash = _configured_code_hash()
    if configured_hash:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, configured_hash)
    configured = _configured_code()
    return bool(configured) and hmac.compare_digest(candidate, configured)


def _email_matches(candidate: str) -> bool:
    required = _configured_email()
    return not required or hmac.compare_digest(str(candidate or "").strip().lower(), required)


def _client_key(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return str(request.client.host if request.client else "unknown")


def _rate_limited(client_key: str) -> bool:
    now = time.time()
    window_seconds = 15 * 60
    with _ATTEMPT_LOCK:
        attempts = _FAILED_ATTEMPTS[client_key]
        while attempts and now - attempts[0] > window_seconds:
            attempts.popleft()
        return len(attempts) >= 5


def _record_failure(client_key: str) -> None:
    with _ATTEMPT_LOCK:
        _FAILED_ATTEMPTS[client_key].append(time.time())


def _clear_failures(client_key: str) -> None:
    with _ATTEMPT_LOCK:
        _FAILED_ATTEMPTS.pop(client_key, None)


def issue_developer_token(email: str = "") -> Dict[str, Any]:
    if not _enabled():
        raise PermissionError("Developer access is disabled.")
    secret = _signing_secret()
    if not secret:
        raise RuntimeError("Developer access is enabled but no developer access code or signing secret is configured.")
    now = int(time.time())
    expires_at = now + (_session_hours() * 3600)
    payload = {
        "iss": "articleready-ai",
        "sub": "developer",
        "scope": "all_paid_actions",
        "email": str(email or "").strip().lower(),
        "iat": now,
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest())
    return {
        "developer_token": f"{encoded_payload}.{signature}",
        "expires_at": expires_at,
        "expires_in_seconds": expires_at - now,
        "email": payload["email"],
        "scope": payload["scope"],
    }


def validate_developer_token(token: str) -> Dict[str, Any] | None:
    if not _enabled() or not token:
        return None
    secret = _signing_secret()
    if not secret:
        return None
    try:
        encoded_payload, supplied_signature = str(token).split(".", 1)
        expected_signature = _b64encode(hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
        if payload.get("iss") != "articleready-ai" or payload.get("sub") != "developer":
            return None
        if payload.get("scope") != "all_paid_actions":
            return None
        if int(payload.get("exp") or 0) <= int(time.time()):
            return None
        required_email = _configured_email()
        if required_email and not hmac.compare_digest(str(payload.get("email") or "").lower(), required_email):
            return None
        return payload
    except Exception:
        return None


@router.post("/api/developer/login")
def developer_login(payload: DeveloperLoginRequest, request: Request) -> Dict[str, Any]:
    if not _enabled():
        raise HTTPException(status_code=404, detail="Developer access is not enabled.")
    client_key = _client_key(request)
    if _rate_limited(client_key):
        raise HTTPException(status_code=429, detail="Too many unsuccessful developer access attempts. Try again later.")
    if not _email_matches(payload.email) or not _code_matches(payload.access_code):
        _record_failure(client_key)
        raise HTTPException(status_code=401, detail="Developer access details are invalid.")
    _clear_failures(client_key)
    result = issue_developer_token(payload.email)
    return {
        "ok": True,
        "message": "Developer access is active on this browser.",
        **result,
    }


@router.post("/api/developer/status")
def developer_status(payload: DeveloperStatusRequest) -> Dict[str, Any]:
    claims = validate_developer_token(payload.developer_token)
    if not claims:
        return {"ok": False, "active": False, "message": "Developer access is inactive or expired."}
    return {
        "ok": True,
        "active": True,
        "message": "Developer access is active.",
        "email": claims.get("email") or "",
        "expires_at": int(claims.get("exp") or 0),
        "scope": claims.get("scope") or "",
    }
