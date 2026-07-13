from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from app.payments.entitlements import action_columns, expiry_datetime, get_plan, normalise_email, normalise_work_id, quota_payload

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PAYMENT_DB = Path(os.environ.get("ARTICLEREADY_SQLITE_DB_PATH", "articleready_payments.db"))

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS articleready_purchases (
    id TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    work_id TEXT NOT NULL,
    module_key TEXT NOT NULL DEFAULT '',
    plan_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    display_amount REAL NOT NULL,
    display_currency TEXT NOT NULL,
    payment_provider TEXT NOT NULL,
    provider_reference TEXT NOT NULL UNIQUE,
    checkout_session_id TEXT,
    access_token_hash TEXT NOT NULL,
    ideas_total INTEGER NOT NULL DEFAULT 0,
    ideas_used INTEGER NOT NULL DEFAULT 0,
    drafts_total INTEGER NOT NULL DEFAULT 0,
    drafts_used INTEGER NOT NULL DEFAULT 0,
    revisions_total INTEGER NOT NULL DEFAULT 0,
    revisions_used INTEGER NOT NULL DEFAULT 0,
    exports_total INTEGER NOT NULL DEFAULT 0,
    exports_used INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    provider_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS articleready_entitlement_usage (
    id TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'claimed',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(purchase_id, action, idempotency_key),
    FOREIGN KEY(purchase_id) REFERENCES articleready_purchases(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS articleready_payment_events (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    raw_body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(provider, event_id)
);
CREATE TABLE IF NOT EXISTS articleready_access_handoffs (
    code_hash TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'payment_return',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    redeemed_at TEXT,
    FOREIGN KEY(purchase_id) REFERENCES articleready_purchases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_email ON articleready_purchases(user_email);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_work ON articleready_purchases(work_id);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_reference ON articleready_purchases(provider_reference);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_session ON articleready_purchases(checkout_session_id);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_status ON articleready_purchases(status);
CREATE INDEX IF NOT EXISTS idx_ar_handoff_purchase ON articleready_access_handoffs(purchase_id);
CREATE INDEX IF NOT EXISTS idx_ar_handoff_expiry ON articleready_access_handoffs(expires_at);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS articleready_purchases (
    id TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    work_id TEXT NOT NULL,
    module_key TEXT NOT NULL DEFAULT '',
    plan_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    amount NUMERIC(12,2) NOT NULL,
    currency TEXT NOT NULL,
    display_amount NUMERIC(12,2) NOT NULL,
    display_currency TEXT NOT NULL,
    payment_provider TEXT NOT NULL,
    provider_reference TEXT NOT NULL UNIQUE,
    checkout_session_id TEXT,
    access_token_hash TEXT NOT NULL,
    ideas_total INTEGER NOT NULL DEFAULT 0,
    ideas_used INTEGER NOT NULL DEFAULT 0,
    drafts_total INTEGER NOT NULL DEFAULT 0,
    drafts_used INTEGER NOT NULL DEFAULT 0,
    revisions_total INTEGER NOT NULL DEFAULT 0,
    revisions_used INTEGER NOT NULL DEFAULT 0,
    exports_total INTEGER NOT NULL DEFAULT 0,
    exports_used INTEGER NOT NULL DEFAULT 0,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    provider_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS articleready_entitlement_usage (
    id TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL REFERENCES articleready_purchases(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'claimed',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    UNIQUE(purchase_id, action, idempotency_key)
);
CREATE TABLE IF NOT EXISTS articleready_payment_events (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    raw_body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, event_id)
);
CREATE TABLE IF NOT EXISTS articleready_access_handoffs (
    code_hash TEXT PRIMARY KEY,
    purchase_id TEXT NOT NULL REFERENCES articleready_purchases(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL DEFAULT 'payment_return',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_email ON articleready_purchases(user_email);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_work ON articleready_purchases(work_id);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_reference ON articleready_purchases(provider_reference);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_session ON articleready_purchases(checkout_session_id);
CREATE INDEX IF NOT EXISTS idx_ar_purchase_status ON articleready_purchases(status);
CREATE INDEX IF NOT EXISTS idx_ar_handoff_purchase ON articleready_access_handoffs(purchase_id);
CREATE INDEX IF NOT EXISTS idx_ar_handoff_expiry ON articleready_access_handoffs(expires_at);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _is_postgres(database_url: Optional[str] = None) -> bool:
    value = str(database_url or DATABASE_URL or "").strip().lower()
    return value.startswith("postgresql://") or value.startswith("postgres://")


@contextmanager
def _postgres_connection(database_url: str = "") -> Iterator[Any]:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(database_url or DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _sqlite_connection() -> Iterator[sqlite3.Connection]:
    SQLITE_PAYMENT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PAYMENT_DB, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_payment_tables(database_url: str = "") -> None:
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(POSTGRES_SCHEMA)
            conn.commit()
        return
    with _sqlite_connection() as conn:
        conn.executescript(SQLITE_SCHEMA)


def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    data = dict(row)
    for key in ["metadata_json", "provider_payload_json"]:
        raw = data.get(key)
        if isinstance(raw, str):
            try:
                data[key] = json.loads(raw or "{}")
            except Exception:
                data[key] = {}
    return data


def make_provider_reference(provider: str) -> str:
    prefix = "ARAI-PS" if str(provider).lower() == "paystack" else "ARAI-ST"
    random_part = secrets.token_urlsafe(18).replace("-", "").replace("_", "")
    return f"{prefix}-{random_part[:24]}"


def create_pending_purchase(
    *,
    user_email: str,
    work_id: str,
    module_key: str,
    plan_key: str,
    amount: float,
    currency: str,
    display_amount: float,
    display_currency: str,
    payment_provider: str,
    provider_reference: str,
    metadata: Optional[Dict[str, Any]] = None,
    database_url: str = "",
) -> Dict[str, Any]:
    init_payment_tables(database_url)
    email = normalise_email(user_email)
    if not email or "@" not in email:
        raise ValueError("A valid customer email is required.")
    plan = get_plan(plan_key)
    quotas = quota_payload(plan_key)
    purchase_id = str(uuid.uuid4())
    access_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(access_token)
    now = _utc_now()
    expires_at = expiry_datetime(plan["validity_days"])
    values = {
        "id": purchase_id,
        "user_email": email,
        "work_id": normalise_work_id(work_id),
        "module_key": str(module_key or plan.get("module") or "").strip(),
        "plan_key": str(plan_key).strip().lower(),
        "amount": round(float(amount), 2),
        "currency": str(currency or "USD").upper(),
        "display_amount": round(float(display_amount), 2),
        "display_currency": str(display_currency or "USD").upper(),
        "payment_provider": str(payment_provider or "").lower(),
        "provider_reference": provider_reference,
        "access_token_hash": token_hash,
        "metadata_json": metadata or {},
        **quotas,
    }
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO articleready_purchases (
                        id, user_email, work_id, module_key, plan_key, amount, currency, display_amount, display_currency,
                        payment_provider, provider_reference, access_token_hash, ideas_total, drafts_total, revisions_total,
                        exports_total, metadata_json, expires_at
                    ) VALUES (
                        %(id)s, %(user_email)s, %(work_id)s, %(module_key)s, %(plan_key)s, %(amount)s, %(currency)s,
                        %(display_amount)s, %(display_currency)s, %(payment_provider)s, %(provider_reference)s,
                        %(access_token_hash)s, %(ideas_total)s, %(drafts_total)s, %(revisions_total)s, %(exports_total)s,
                        %(metadata_json)s::jsonb, %(expires_at)s
                    ) RETURNING *
                    """,
                    {**values, "metadata_json": _json(values["metadata_json"]), "expires_at": expires_at},
                )
                row = cur.fetchone()
            conn.commit()
    else:
        with _sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO articleready_purchases (
                    id, user_email, work_id, module_key, plan_key, amount, currency, display_amount, display_currency,
                    payment_provider, provider_reference, access_token_hash, ideas_total, drafts_total, revisions_total,
                    exports_total, metadata_json, created_at, expires_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["id"], values["user_email"], values["work_id"], values["module_key"], values["plan_key"],
                    values["amount"], values["currency"], values["display_amount"], values["display_currency"],
                    values["payment_provider"], values["provider_reference"], values["access_token_hash"],
                    values["ideas_total"], values["drafts_total"], values["revisions_total"], values["exports_total"],
                    _json(values["metadata_json"]), now.isoformat(), expires_at.isoformat(), now.isoformat(),
                ),
            )
            row = conn.execute("SELECT * FROM articleready_purchases WHERE id=?", (purchase_id,)).fetchone()
            conn.commit()
    purchase = _row_to_dict(row) or {}
    purchase["access_token"] = access_token
    return purchase


def set_checkout_session(purchase_id: str, checkout_session_id: str, *, database_url: str = "") -> None:
    if not checkout_session_id:
        return
    init_payment_tables(database_url)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE articleready_purchases SET checkout_session_id=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (checkout_session_id, purchase_id))
            conn.commit()
    else:
        with _sqlite_connection() as conn:
            conn.execute("UPDATE articleready_purchases SET checkout_session_id=?, updated_at=? WHERE id=?", (checkout_session_id, _utc_iso(), purchase_id))


def get_purchase_by_reference(provider_reference: str, *, database_url: str = "") -> Optional[Dict[str, Any]]:
    init_payment_tables(database_url)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM articleready_purchases WHERE provider_reference=%s", (provider_reference,))
                return _row_to_dict(cur.fetchone())
    with _sqlite_connection() as conn:
        return _row_to_dict(conn.execute("SELECT * FROM articleready_purchases WHERE provider_reference=?", (provider_reference,)).fetchone())


def get_purchase(purchase_id: str, *, database_url: str = "") -> Optional[Dict[str, Any]]:
    init_payment_tables(database_url)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM articleready_purchases WHERE id=%s", (purchase_id,))
                return _row_to_dict(cur.fetchone())
    with _sqlite_connection() as conn:
        return _row_to_dict(conn.execute("SELECT * FROM articleready_purchases WHERE id=?", (purchase_id,)).fetchone())


def get_purchase_by_session(checkout_session_id: str, *, database_url: str = "") -> Optional[Dict[str, Any]]:
    init_payment_tables(database_url)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM articleready_purchases WHERE checkout_session_id=%s", (checkout_session_id,))
                return _row_to_dict(cur.fetchone())
    with _sqlite_connection() as conn:
        return _row_to_dict(conn.execute("SELECT * FROM articleready_purchases WHERE checkout_session_id=?", (checkout_session_id,)).fetchone())


def activate_purchase(*, provider_reference: str, verified_amount: float, verified_currency: str, provider_payload: Dict[str, Any], database_url: str = "") -> Dict[str, Any]:
    purchase = get_purchase_by_reference(provider_reference, database_url=database_url)
    if not purchase:
        raise ValueError("No ArticleReady purchase matches this payment reference.")
    if str(purchase.get("status") or "").lower() == "active":
        return purchase
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE articleready_purchases SET status='active', provider_payload_json=%s::jsonb,
                    updated_at=CURRENT_TIMESTAMP WHERE provider_reference=%s RETURNING *
                    """,
                    (_json(provider_payload), provider_reference),
                )
                row = cur.fetchone()
            conn.commit()
    else:
        with _sqlite_connection() as conn:
            conn.execute(
                "UPDATE articleready_purchases SET status='active', provider_payload_json=?, updated_at=? WHERE provider_reference=?",
                (_json(provider_payload), _utc_iso(), provider_reference),
            )
            row = conn.execute("SELECT * FROM articleready_purchases WHERE provider_reference=?", (provider_reference,)).fetchone()
    return _row_to_dict(row) or {}


def record_event_once(*, provider: str, event_id: str, event_type: str, raw_body: bytes, database_url: str = "") -> bool:
    init_payment_tables(database_url)
    if not event_id:
        event_id = str(uuid.uuid4())
    row_id = str(uuid.uuid4())
    raw_text = raw_body.decode("utf-8", errors="replace") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body or "")
    try:
        if _is_postgres(database_url):
            with _postgres_connection(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO articleready_payment_events(id, provider, event_id, event_type, raw_body) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(provider, event_id) DO NOTHING",
                        (row_id, provider, event_id, event_type, raw_text),
                    )
                    inserted = cur.rowcount > 0
                conn.commit()
                return inserted
        with _sqlite_connection() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO articleready_payment_events(id, provider, event_id, event_type, raw_body, created_at) VALUES(?,?,?,?,?,?)",
                (row_id, provider, event_id, event_type, raw_text, _utc_iso()),
            )
            return cur.rowcount > 0
    except Exception:
        return False


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return _utc_now()


def _ensure_active_entitlement(purchase: Dict[str, Any], access_token: str, action: str) -> None:
    if not purchase:
        raise PermissionError("Paid access was not found.")
    if _hash_token(access_token) != str(purchase.get("access_token_hash") or ""):
        raise PermissionError("Paid access credentials are invalid.")
    if str(purchase.get("status") or "").lower() != "active":
        raise PermissionError("Payment has not been confirmed yet.")
    if _parse_dt(purchase.get("expires_at")) < _utc_now():
        raise PermissionError("This purchase has expired.")
    total_col, used_col = action_columns(action)
    if int(purchase.get(used_col) or 0) >= int(purchase.get(total_col) or 0):
        raise PermissionError(f"No remaining {action} entitlement is available for this purchase.")


def claim_entitlement(*, purchase_id: str, access_token: str, action: str, idempotency_key: str, metadata: Optional[Dict[str, Any]] = None, database_url: str = "") -> Dict[str, Any]:
    init_payment_tables(database_url)
    purchase = get_purchase(purchase_id, database_url=database_url)
    _ensure_active_entitlement(purchase or {}, access_token, action)
    total_col, used_col = action_columns(action)
    usage_id = str(uuid.uuid4())
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM articleready_purchases WHERE id=%s FOR UPDATE", (purchase_id,))
                    locked = _row_to_dict(cur.fetchone()) or {}
                    _ensure_active_entitlement(locked, access_token, action)
                    cur.execute(
                        "INSERT INTO articleready_entitlement_usage(id, purchase_id, action, idempotency_key, metadata_json) VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(purchase_id, action, idempotency_key) DO NOTHING RETURNING *",
                        (usage_id, purchase_id, action, idempotency_key, _json(metadata or {})),
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(f"UPDATE articleready_purchases SET {used_col}={used_col}+1, updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING *", (purchase_id,))
                        locked = _row_to_dict(cur.fetchone()) or locked
                conn.commit()
                return {"claimed": bool(row), "purchase": locked, "usage": _row_to_dict(row) if row else None}
            except Exception:
                conn.rollback()
                raise
    with _sqlite_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        locked = _row_to_dict(conn.execute("SELECT * FROM articleready_purchases WHERE id=?", (purchase_id,)).fetchone()) or {}
        _ensure_active_entitlement(locked, access_token, action)
        cur = conn.execute(
            "INSERT OR IGNORE INTO articleready_entitlement_usage(id, purchase_id, action, idempotency_key, metadata_json, created_at) VALUES(?,?,?,?,?,?)",
            (usage_id, purchase_id, action, idempotency_key, _json(metadata or {}), _utc_iso()),
        )
        claimed = cur.rowcount > 0
        usage = _row_to_dict(conn.execute("SELECT * FROM articleready_entitlement_usage WHERE purchase_id=? AND action=? AND idempotency_key=?", (purchase_id, action, idempotency_key)).fetchone())
        if claimed:
            conn.execute(f"UPDATE articleready_purchases SET {used_col}={used_col}+1, updated_at=? WHERE id=?", (_utc_iso(), purchase_id))
        locked = _row_to_dict(conn.execute("SELECT * FROM articleready_purchases WHERE id=?", (purchase_id,)).fetchone()) or locked
        conn.commit()
        return {"claimed": claimed, "purchase": locked, "usage": usage}


def complete_claim(usage_id: str, *, database_url: str = "") -> None:
    if not usage_id:
        return
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE articleready_entitlement_usage SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=%s", (usage_id,))
            conn.commit()
        return
    with _sqlite_connection() as conn:
        conn.execute("UPDATE articleready_entitlement_usage SET status='completed', completed_at=? WHERE id=?", (_utc_iso(), usage_id))


def rollback_claim(usage_id: str, *, database_url: str = "") -> None:
    if not usage_id:
        return
    init_payment_tables(database_url)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM articleready_entitlement_usage WHERE id=%s", (usage_id,))
                usage = _row_to_dict(cur.fetchone())
                if usage and usage.get("status") == "claimed":
                    _total, used_col = action_columns(str(usage.get("action") or ""))
                    cur.execute("UPDATE articleready_entitlement_usage SET status='rolled_back' WHERE id=%s", (usage_id,))
                    cur.execute(f"UPDATE articleready_purchases SET {used_col}=GREATEST({used_col}-1,0), updated_at=CURRENT_TIMESTAMP WHERE id=%s", (usage.get("purchase_id"),))
            conn.commit()
        return
    with _sqlite_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        usage = _row_to_dict(conn.execute("SELECT * FROM articleready_entitlement_usage WHERE id=?", (usage_id,)).fetchone())
        if usage and usage.get("status") == "claimed":
            _total, used_col = action_columns(str(usage.get("action") or ""))
            conn.execute("UPDATE articleready_entitlement_usage SET status='rolled_back' WHERE id=?", (usage_id,))
            conn.execute(f"UPDATE articleready_purchases SET {used_col}=MAX({used_col}-1,0), updated_at=? WHERE id=?", (_utc_iso(), usage.get("purchase_id")))
        conn.commit()




def rotate_access_token(purchase_id: str, *, database_url: str = "") -> Dict[str, Any]:
    """Issue a fresh opaque browser credential for an active purchase."""
    init_payment_tables(database_url)
    purchase = get_purchase(purchase_id, database_url=database_url)
    if not purchase:
        raise ValueError("The paid access record could not be found.")
    if str(purchase.get("status") or "").lower() not in {"paid", "active"}:
        raise PermissionError("The payment has not been activated.")
    new_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(new_token)
    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE articleready_purchases
                    SET access_token_hash=%s, updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s RETURNING *
                    """,
                    (token_hash, purchase_id),
                )
                row = cur.fetchone()
            conn.commit()
    else:
        with _sqlite_connection() as conn:
            now = _utc_iso()
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE articleready_purchases SET access_token_hash=?, updated_at=? WHERE id=?",
                (token_hash, now, purchase_id),
            )
            row = conn.execute("SELECT * FROM articleready_purchases WHERE id=?", (purchase_id,)).fetchone()
            conn.commit()
    refreshed = _row_to_dict(row)
    if not refreshed:
        raise ValueError("The paid access record could not be refreshed.")
    refreshed["access_token"] = new_token
    return refreshed


def create_access_handoff(
    purchase_id: str,
    *,
    purpose: str = "payment_return",
    ttl_minutes: int = 20,
    database_url: str = "",
) -> str:
    """Create a short-lived, single-use payment return code."""
    init_payment_tables(database_url)
    purchase = get_purchase(purchase_id, database_url=database_url)
    if not purchase or str(purchase.get("status") or "").lower() not in {"paid", "active"}:
        raise ValueError("A paid purchase is required before access can be restored in the browser.")

    raw_code = secrets.token_urlsafe(32)
    code_hash = _hash_token(raw_code)
    now = _utc_now()
    expires_at = now + timedelta(minutes=max(5, min(int(ttl_minutes or 20), 60)))
    safe_purpose = str(purpose or "payment_return")[:80]

    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM articleready_access_handoffs WHERE purchase_id=%s AND redeemed_at IS NULL",
                    (purchase_id,),
                )
                cur.execute(
                    """
                    INSERT INTO articleready_access_handoffs(code_hash, purchase_id, purpose, expires_at)
                    VALUES(%s, %s, %s, %s)
                    """,
                    (code_hash, purchase_id, safe_purpose, expires_at),
                )
            conn.commit()
    else:
        with _sqlite_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM articleready_access_handoffs WHERE purchase_id=? AND redeemed_at IS NULL",
                (purchase_id,),
            )
            conn.execute(
                """
                INSERT INTO articleready_access_handoffs(code_hash, purchase_id, purpose, created_at, expires_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (code_hash, purchase_id, safe_purpose, now.isoformat(), expires_at.isoformat()),
            )
            conn.commit()
    return raw_code


def redeem_access_handoff(code: str, *, database_url: str = "") -> Dict[str, Any]:
    """Redeem a payment return code once and rotate the browser access token."""
    init_payment_tables(database_url)
    raw_code = str(code or "").strip()
    if len(raw_code) < 20:
        raise PermissionError("The payment return code is missing or invalid.")
    code_hash = _hash_token(raw_code)
    new_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(new_token)
    now = _utc_now()

    if _is_postgres(database_url):
        with _postgres_connection(database_url) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT h.*, p.status AS purchase_status
                        FROM articleready_access_handoffs h
                        JOIN articleready_purchases p ON p.id=h.purchase_id
                        WHERE h.code_hash=%s
                        FOR UPDATE
                        """,
                        (code_hash,),
                    )
                    handoff = _row_to_dict(cur.fetchone())
                    if not handoff:
                        raise PermissionError("The payment return code is invalid.")
                    if handoff.get("redeemed_at"):
                        raise PermissionError("This payment return code has already been used.")
                    expires = handoff.get("expires_at")
                    if expires and getattr(expires, "tzinfo", None) is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if not expires or expires <= now:
                        raise PermissionError("The payment return code has expired.")
                    if str(handoff.get("purchase_status") or "").lower() not in {"paid", "active"}:
                        raise PermissionError("The payment has not been activated.")
                    cur.execute(
                        "UPDATE articleready_access_handoffs SET redeemed_at=CURRENT_TIMESTAMP WHERE code_hash=%s",
                        (code_hash,),
                    )
                    cur.execute(
                        """
                        UPDATE articleready_purchases
                        SET access_token_hash=%s, updated_at=CURRENT_TIMESTAMP
                        WHERE id=%s RETURNING *
                        """,
                        (token_hash, handoff["purchase_id"]),
                    )
                    row = cur.fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    else:
        with _sqlite_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                handoff = _row_to_dict(conn.execute(
                    """
                    SELECT h.*, p.status AS purchase_status
                    FROM articleready_access_handoffs h
                    JOIN articleready_purchases p ON p.id=h.purchase_id
                    WHERE h.code_hash=?
                    """,
                    (code_hash,),
                ).fetchone())
                if not handoff:
                    raise PermissionError("The payment return code is invalid.")
                if handoff.get("redeemed_at"):
                    raise PermissionError("This payment return code has already been used.")
                try:
                    expires = datetime.fromisoformat(str(handoff.get("expires_at") or "").replace("Z", "+00:00"))
                except Exception:
                    expires = None
                if expires and expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if not expires or expires <= now:
                    raise PermissionError("The payment return code has expired.")
                if str(handoff.get("purchase_status") or "").lower() not in {"paid", "active"}:
                    raise PermissionError("The payment has not been activated.")
                conn.execute(
                    "UPDATE articleready_access_handoffs SET redeemed_at=? WHERE code_hash=?",
                    (now.isoformat(), code_hash),
                )
                conn.execute(
                    "UPDATE articleready_purchases SET access_token_hash=?, updated_at=? WHERE id=?",
                    (token_hash, now.isoformat(), handoff["purchase_id"]),
                )
                row = conn.execute(
                    "SELECT * FROM articleready_purchases WHERE id=?",
                    (handoff["purchase_id"],),
                ).fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    purchase = _row_to_dict(row)
    if not purchase:
        raise ValueError("The paid access record could not be restored.")
    purchase["access_token"] = new_token
    return purchase


def entitlement_status(*, purchase_id: str, access_token: str, database_url: str = "") -> Dict[str, Any]:
    purchase = get_purchase(purchase_id, database_url=database_url)
    if not purchase:
        return {"ok": False, "active": False, "message": "Purchase not found."}
    if _hash_token(access_token) != str(purchase.get("access_token_hash") or ""):
        return {"ok": False, "active": False, "message": "Invalid access token."}
    active = str(purchase.get("status") or "").lower() == "active" and _parse_dt(purchase.get("expires_at")) >= _utc_now()
    return {
        "ok": True,
        "active": active,
        "purchase_id": purchase.get("id"),
        "plan_key": purchase.get("plan_key"),
        "module_key": purchase.get("module_key"),
        "work_id": purchase.get("work_id"),
        "status": purchase.get("status"),
        "expires_at": str(purchase.get("expires_at") or ""),
        "remaining": {
            "ideas": max(0, int(purchase.get("ideas_total") or 0) - int(purchase.get("ideas_used") or 0)),
            "drafts": max(0, int(purchase.get("drafts_total") or 0) - int(purchase.get("drafts_used") or 0)),
            "revisions": max(0, int(purchase.get("revisions_total") or 0) - int(purchase.get("revisions_used") or 0)),
            "exports": max(0, int(purchase.get("exports_total") or 0) - int(purchase.get("exports_used") or 0)),
        },
    }
