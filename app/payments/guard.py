from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional
import os
import uuid

from app.payments.store import claim_entitlement, complete_claim, rollback_claim
from app.developer_access import validate_developer_token

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PAYMENT_REQUIRED = os.environ.get("ARTICLEREADY_PAYMENT_REQUIRED", "1").strip().lower() not in {"0", "false", "no", "off"}


class PaymentRequiredError(PermissionError):
    pass


def credentials_from_headers(headers: Any) -> Dict[str, str]:
    return {
        "purchase_id": str(headers.get("x-articleready-purchase-id") or headers.get("x-projectready-purchase-id") or "").strip(),
        "access_token": str(headers.get("x-articleready-access-token") or headers.get("x-projectready-access-token") or "").strip(),
        "developer_token": str(headers.get("x-articleready-developer-token") or "").strip(),
    }


def make_payment_required_detail(action: str, recommended_plan: str = "") -> Dict[str, Any]:
    return {
        "code": "payment_required",
        "message": "Unlock the appropriate ArticleReady AI package to continue.",
        "action": action,
        "recommended_plan": recommended_plan,
    }


@contextmanager
def paid_article_action(
    *,
    purchase_id: str,
    access_token: str,
    developer_token: str = "",
    action: str,
    idempotency_key: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    database_url: str = "",
) -> Iterator[Dict[str, Any]]:
    developer_claims = validate_developer_token(developer_token) if developer_token else None
    if developer_claims:
        yield {
            "claimed": False,
            "purchase": None,
            "usage": None,
            "payment_bypass": True,
            "developer_access": True,
            "developer_email": developer_claims.get("email") or "",
        }
        return
    if not PAYMENT_REQUIRED:
        yield {"claimed": False, "purchase": None, "usage": None, "payment_bypass": True}
        return
    if not purchase_id or not access_token:
        raise PaymentRequiredError("Paid ArticleReady access is required for this action.")
    try:
        claim = claim_entitlement(
            purchase_id=purchase_id,
            access_token=access_token,
            action=action,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            metadata=metadata,
            database_url=database_url or DATABASE_URL,
        )
    except PermissionError as exc:
        raise PaymentRequiredError(str(exc)) from exc
    usage = claim.get("usage") or {}
    usage_id = usage.get("id")
    try:
        yield claim
    except Exception:
        if usage_id and claim.get("claimed"):
            rollback_claim(usage_id, database_url=database_url or DATABASE_URL)
        raise
    else:
        if usage_id and claim.get("claimed"):
            complete_claim(usage_id, database_url=database_url or DATABASE_URL)
