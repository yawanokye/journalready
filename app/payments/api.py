from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.payments.country_router import choose_payment_provider
from app.payments.entitlements import build_plans_payload, get_plan
from app.payments.paystack import PaystackError, get_paystack_charge, handle_paystack_webhook, initialize_paystack_payment, verify_and_activate_purchase
from app.payments.store import create_access_handoff, create_pending_purchase, entitlement_status, get_purchase, make_provider_reference, redeem_access_handoff, rotate_access_token
from app.payments.stripe_provider import StripePaymentError, handle_stripe_webhook, initialize_stripe_payment, verify_and_activate_stripe_session

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SUCCESS_PATH = os.environ.get("ARTICLEREADY_PAYMENT_SUCCESS_PATH", "/pricing").strip() or "/pricing"
CANCEL_PATH = os.environ.get("ARTICLEREADY_PAYMENT_CANCEL_PATH", "/pricing").strip() or "/pricing"

api_router = APIRouter(tags=["ArticleReady AI Payments"])


class CheckoutRequest(BaseModel):
    plan_key: str = Field(..., min_length=3)
    user_email: str = Field(..., min_length=5)
    billing_country: str = Field(..., min_length=2, max_length=2)
    work_id: str = "general"
    module_key: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EntitlementStatusRequest(BaseModel):
    purchase_id: str
    access_token: str


class PaymentHandoffRequest(BaseModel):
    handoff: str = Field(..., min_length=20, max_length=300)


class PaidAccessRecoveryRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    purchase_id: str = Field(..., min_length=10, max_length=100)


def _redirect(path: str, **params: str) -> RedirectResponse:
    query = urlencode({key: value for key, value in params.items() if value is not None})
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}{query}" if query else path, status_code=302)


def _successful_payment_redirect(purchase: Dict[str, Any], provider: str) -> RedirectResponse:
    params: Dict[str, str] = {
        "payment": "success",
        "provider": provider,
        "purchase_id": str(purchase.get("id") or ""),
        "plan_key": str(purchase.get("plan_key") or ""),
    }
    try:
        params["handoff"] = create_access_handoff(
            str(purchase.get("id") or ""),
            purpose=f"{provider}_payment_return",
            database_url=DATABASE_URL,
        )
    except Exception:
        params["handoff_status"] = "recovery_required"
    return _redirect(SUCCESS_PATH, **params)


@api_router.get("/api/payments/plans")
def payment_plans() -> Dict[str, Any]:
    payload = build_plans_payload()
    for plan in payload.get("plans", []):
        try:
            charge = get_paystack_charge(str(plan.get("plan_key") or ""))
            plan["paystack_amount"] = charge["amount"]
            plan["paystack_currency"] = charge["currency"]
            plan["paystack_price_display"] = charge["charged_display"]
        except Exception:
            plan["paystack_price_display"] = None
    return payload


@api_router.post("/api/payments/checkout")
def start_checkout(payload: CheckoutRequest) -> Dict[str, Any]:
    try:
        plan = get_plan(payload.plan_key)
        provider = choose_payment_provider(payload.billing_country)
        if provider == "paystack":
            charge = get_paystack_charge(plan["plan_key"])
            amount = charge["amount"]
            currency = charge["currency"]
            display_amount = float(plan["amount"])
            display_currency = "USD"
        else:
            amount = float(plan["amount"])
            currency = "USD"
            display_amount = amount
            display_currency = "USD"
        provider_reference = make_provider_reference(provider)
        purchase = create_pending_purchase(
            user_email=payload.user_email,
            work_id=payload.work_id or "general",
            module_key=payload.module_key or str(plan.get("module") or ""),
            plan_key=plan["plan_key"],
            amount=amount,
            currency=currency,
            display_amount=display_amount,
            display_currency=display_currency,
            payment_provider=provider,
            provider_reference=provider_reference,
            metadata={**(payload.metadata or {}), "billing_country": payload.billing_country.upper()},
            database_url=DATABASE_URL,
        )
        if provider == "paystack":
            checkout = initialize_paystack_payment(purchase)
        else:
            checkout = initialize_stripe_payment(purchase, database_url=DATABASE_URL)
        return {**checkout, "plan": {"plan_key": plan["plan_key"], "name": plan["name"], "price_display": plan["price_display"]}}
    except (ValueError, PaystackError, StripePaymentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Checkout could not be started: {str(exc)[:240]}") from exc


@api_router.get("/payment/paystack/callback")
def paystack_callback(reference: str = "", trxref: str = ""):
    ref = reference or trxref
    if not ref:
        return _redirect(SUCCESS_PATH, payment="failed", reason="missing_reference")
    try:
        result = verify_and_activate_purchase(ref, database_url=DATABASE_URL)
    except Exception:
        return _redirect(SUCCESS_PATH, payment="failed", provider="paystack")
    if not result.get("ok"):
        return _redirect(SUCCESS_PATH, payment="failed", provider="paystack")
    purchase = result.get("purchase") or {}
    return _successful_payment_redirect(purchase, "paystack")


@api_router.post("/payment/paystack/webhook")
async def paystack_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    try:
        result = handle_paystack_webhook(raw_body=raw_body, signature=signature, database_url=DATABASE_URL)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=int(result.get("status_code") or 400), detail=result.get("message") or "Webhook failed")
    return result


@api_router.get("/payment/stripe/success")
def stripe_success(session_id: str = ""):
    if not session_id:
        return _redirect(SUCCESS_PATH, payment="failed", reason="missing_session")
    try:
        result = verify_and_activate_stripe_session(session_id, database_url=DATABASE_URL)
    except Exception:
        return _redirect(SUCCESS_PATH, payment="failed", provider="stripe")
    if not result.get("ok"):
        return _redirect(SUCCESS_PATH, payment="failed", provider="stripe")
    purchase = result.get("purchase") or {}
    return _successful_payment_redirect(purchase, "stripe")


@api_router.post("/payment/stripe/webhook")
async def stripe_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        result = handle_stripe_webhook(raw_body=raw_body, signature=signature, database_url=DATABASE_URL)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=int(result.get("status_code") or 400), detail=result.get("message") or "Webhook failed")
    return result


@api_router.post("/api/payments/redeem-handoff")
def redeem_payment_handoff(payload: PaymentHandoffRequest) -> Dict[str, Any]:
    try:
        purchase = redeem_access_handoff(payload.handoff, database_url=DATABASE_URL)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "ok": True,
        "purchase_id": purchase.get("id"),
        "access_token": purchase.get("access_token"),
        "plan_key": purchase.get("plan_key"),
        "module_key": purchase.get("module_key"),
        "work_id": purchase.get("work_id"),
        "provider": purchase.get("payment_provider"),
        "expires_at": str(purchase.get("expires_at") or ""),
    }


@api_router.post("/api/payments/recover-access")
def recover_paid_access(payload: PaidAccessRecoveryRequest) -> Dict[str, Any]:
    email = str(payload.email or "").strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Enter the email address used for payment.")
    purchase = get_purchase(payload.purchase_id, database_url=DATABASE_URL)
    if not purchase:
        raise HTTPException(status_code=404, detail="No paid access record matches that Purchase ID.")
    if str(purchase.get("user_email") or "").strip().lower() != email:
        raise HTTPException(status_code=403, detail="The payment email does not match this Purchase ID.")

    # If a provider callback was interrupted, verify the transaction directly.
    if str(purchase.get("status") or "").lower() not in {"paid", "active"}:
        try:
            provider = str(purchase.get("payment_provider") or "").lower()
            if provider == "paystack":
                verified = verify_and_activate_purchase(str(purchase.get("provider_reference") or ""), database_url=DATABASE_URL)
                purchase = verified.get("purchase") or purchase
            elif provider == "stripe" and purchase.get("checkout_session_id"):
                verified = verify_and_activate_stripe_session(str(purchase.get("checkout_session_id") or ""), database_url=DATABASE_URL)
                purchase = verified.get("purchase") or purchase
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"The payment could not yet be verified: {str(exc)[:180]}") from exc

    if str(purchase.get("status") or "").lower() not in {"paid", "active"}:
        raise HTTPException(status_code=409, detail="The payment is still pending or was not completed.")
    try:
        refreshed = rotate_access_token(str(purchase.get("id") or ""), database_url=DATABASE_URL)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "ok": True,
        "purchase_id": refreshed.get("id"),
        "access_token": refreshed.get("access_token"),
        "plan_key": refreshed.get("plan_key"),
        "module_key": refreshed.get("module_key"),
        "work_id": refreshed.get("work_id"),
        "provider": refreshed.get("payment_provider"),
        "expires_at": str(refreshed.get("expires_at") or ""),
        "message": "Paid access restored on this device.",
    }


@api_router.post("/api/payments/entitlement-status")
def check_entitlement_status(payload: EntitlementStatusRequest) -> Dict[str, Any]:
    return entitlement_status(purchase_id=payload.purchase_id, access_token=payload.access_token, database_url=DATABASE_URL)
