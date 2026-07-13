from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from app.payments.entitlements import get_price
from app.payments.store import activate_purchase, get_purchase_by_reference, record_event_once

PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")
CANCEL_PATH = os.environ.get("ARTICLEREADY_PAYMENT_CANCEL_PATH", "/pricing").strip() or "/pricing"
PAYSTACK_USER_AGENT = os.environ.get("PAYSTACK_USER_AGENT", "ArticleReadyAI/1.0 (+https://articlereadyai.com; payments@articlereadyai.com)").strip()

PLAN_GHS_ENV = {
    "article_ideas": "ARTICLEREADY_PAYSTACK_ARTICLE_IDEAS_GHS",
    "stage1_article": "ARTICLEREADY_PAYSTACK_STAGE1_GHS",
    "standard_full_article": "ARTICLEREADY_PAYSTACK_STANDARD_ARTICLE_GHS",
    "long_article_plus": "ARTICLEREADY_PAYSTACK_LONG_ARTICLE_GHS",
    "review_conceptual_scoping": "ARTICLEREADY_PAYSTACK_REVIEW_ARTICLE_GHS",
    "article_revision": "ARTICLEREADY_PAYSTACK_ARTICLE_REVISION_GHS",
    "reviewer_comment_revision": "ARTICLEREADY_PAYSTACK_REVIEWER_REVISION_GHS",
    "extra_revision_pass": "ARTICLEREADY_PAYSTACK_EXTRA_REVISION_GHS",
}


class PaystackError(RuntimeError):
    pass


def _require_secret_key() -> str:
    if not PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured.")
    return PAYSTACK_SECRET_KEY


def _positive_float(raw: Any, *, name: str) -> float:
    try:
        value = float(str(raw).strip())
    except Exception as exc:
        raise PaystackError(f"{name} must be a valid positive number.") from exc
    if value <= 0:
        raise PaystackError(f"{name} must be greater than zero.")
    return value


def amount_to_subunit(amount: float) -> int:
    return int(round(float(amount) * 100))


def get_paystack_charge(plan_key: str) -> Dict[str, Any]:
    price = get_price(plan_key)
    fixed_env = PLAN_GHS_ENV.get(str(plan_key).strip().lower())
    fixed_raw = os.environ.get(fixed_env, "").strip() if fixed_env else ""
    if fixed_raw:
        charged_amount = round(_positive_float(fixed_raw, name=fixed_env or "fixed GHS price"), 2)
        calculation = "fixed_ghs_plan_price"
        exchange_rate: Optional[float] = None
    else:
        rate = _positive_float(os.environ.get("ARTICLEREADY_PAYSTACK_USD_TO_GHS_RATE", "15.00"), name="ARTICLEREADY_PAYSTACK_USD_TO_GHS_RATE")
        charged_amount = round(float(price["amount"]) * rate, 2)
        calculation = "usd_price_converted_with_configured_rate"
        exchange_rate = rate
    return {
        "selected_amount": float(price["amount"]),
        "selected_currency": "USD",
        "selected_display": price["display"],
        "amount": charged_amount,
        "currency": "GHS",
        "amount_subunit": amount_to_subunit(charged_amount),
        "charged_display": f"GHS {charged_amount:,.2f}",
        "calculation": calculation,
        "exchange_rate": exchange_rate,
    }


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    secret = _require_secret_key()
    url = f"{PAYSTACK_BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": PAYSTACK_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PaystackError(f"Paystack HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise PaystackError(f"Paystack request failed: {exc}") from exc


def initialize_paystack_payment(purchase: Dict[str, Any], *, callback_path: str = "/payment/paystack/callback") -> Dict[str, Any]:
    metadata = {
        "product": "ArticleReady AI",
        "purchase_id": purchase["id"],
        "work_id": purchase["work_id"],
        "module_key": purchase["module_key"],
        "plan_key": purchase["plan_key"],
        "display_amount": float(purchase.get("display_amount") or 0),
        "display_currency": purchase.get("display_currency") or "USD",
        "charged_amount": float(purchase["amount"]),
        "charged_currency": purchase["currency"],
        "cancel_action": f"{APP_BASE_URL}{CANCEL_PATH}?payment=cancelled&purchase_id={purchase['id']}",
    }
    payload = {
        "email": purchase["user_email"],
        "amount": str(amount_to_subunit(float(purchase["amount"]))),
        "currency": purchase["currency"],
        "reference": purchase["provider_reference"],
        "callback_url": f"{APP_BASE_URL}{callback_path}",
        "metadata": metadata,
    }
    response = _request("POST", "/transaction/initialize", payload)
    if not response.get("status"):
        raise PaystackError(response.get("message") or "Paystack initialization failed.")
    data = response.get("data") or {}
    return {
        "ok": True,
        "provider": "paystack",
        "checkout_url": data.get("authorization_url"),
        "authorization_url": data.get("authorization_url"),
        "access_code": data.get("access_code"),
        "provider_reference": data.get("reference") or purchase["provider_reference"],
        "purchase_id": purchase["id"],
        "amount": float(purchase["amount"]),
        "currency": purchase["currency"],
        "display_amount": float(purchase.get("display_amount") or 0),
        "display_currency": purchase.get("display_currency") or "USD",
        "access_token": purchase.get("access_token"),
    }


def verify_paystack_transaction(reference: str) -> Dict[str, Any]:
    safe_reference = urllib.parse.quote(str(reference or "").strip(), safe="")
    if not safe_reference:
        raise PaystackError("Payment reference is required.")
    response = _request("GET", f"/transaction/verify/{safe_reference}")
    if not response.get("status"):
        return {"ok": False, "verified": False, "message": response.get("message") or "Paystack verification failed."}
    data = response.get("data") or {}
    return {
        "ok": True,
        "verified": str(data.get("status") or "").lower() == "success",
        "status": str(data.get("status") or "").lower(),
        "reference": data.get("reference"),
        "amount_subunit": int(data.get("amount") or 0),
        "amount": round(int(data.get("amount") or 0) / 100, 2),
        "currency": str(data.get("currency") or "").upper(),
        "customer_email": ((data.get("customer") or {}).get("email") or "").lower(),
        "data": data,
    }


def verify_and_activate_purchase(reference: str, *, database_url: str = "") -> Dict[str, Any]:
    verification = verify_paystack_transaction(reference)
    if not verification.get("verified"):
        return {"ok": False, "activated": False, "message": "The Paystack transaction is not successful.", "verification": verification}
    purchase = get_purchase_by_reference(reference, database_url=database_url)
    if not purchase:
        return {"ok": False, "activated": False, "message": "Payment was verified, but its ArticleReady purchase was not found."}
    expected = amount_to_subunit(float(purchase["amount"]))
    if verification["amount_subunit"] != expected or verification["currency"] != str(purchase["currency"]).upper():
        return {"ok": False, "activated": False, "message": "The verified Paystack amount or currency does not match the purchase.", "verification": verification}
    if verification.get("customer_email") and verification["customer_email"] != str(purchase["user_email"]).lower():
        return {"ok": False, "activated": False, "message": "The Paystack customer email does not match the purchase."}
    activated = activate_purchase(provider_reference=reference, verified_amount=verification["amount"], verified_currency=verification["currency"], provider_payload=verification["data"], database_url=database_url)
    return {"ok": True, "activated": True, "purchase": activated, "verification": verification}


def handle_paystack_webhook(*, raw_body: bytes, signature: str, database_url: str = "") -> Dict[str, Any]:
    secret = _require_secret_key()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, str(signature or "")):
        return {"ok": False, "status_code": 400, "message": "Invalid Paystack signature."}
    try:
        event = json.loads(raw_body.decode("utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "status_code": 400, "message": "Invalid Paystack JSON."}
    event_type = str(event.get("event") or "")
    data = event.get("data") or {}
    event_id = str(data.get("id") or data.get("reference") or "")
    if event_type != "charge.success":
        first = record_event_once(provider="paystack", event_id=event_id or event_type, event_type=event_type, raw_body=raw_body, database_url=database_url)
        return {"ok": True, "status_code": 200, "activated": False, "duplicate": not first, "event": event_type}
    reference = str(data.get("reference") or "")
    result = verify_and_activate_purchase(reference, database_url=database_url)
    if result.get("ok"):
        first = record_event_once(provider="paystack", event_id=event_id or reference, event_type=event_type, raw_body=raw_body, database_url=database_url)
        result["duplicate"] = not first
    return {**result, "status_code": 200 if result.get("ok") else 400, "event": event_type}
