from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
import re

DEFAULT_DISPLAY_CURRENCY = "USD"
PURCHASE_VALIDITY_DAYS = 90

ACTION_FIELDS: Dict[str, Tuple[str, str]] = {
    "idea": ("ideas_total", "ideas_used"),
    "draft": ("drafts_total", "drafts_used"),
    "revision": ("revisions_total", "revisions_used"),
    "export": ("exports_total", "exports_used"),
}

ARTICLE_PLANS: Dict[str, Dict[str, Any]] = {
    "article_ideas": {
        "name": "Article Ideas",
        "description": "Up to 20 focused article topic ideas with readiness scores and data or instrument guidance.",
        "price_usd": 2.99,
        "per": "idea run",
        "module": "topic_ideas",
        "ideas": 1,
        "drafts": 0,
        "revisions": 0,
        "exports": 0,
        "max_ideas": 20,
        "token_allowance": 20000,
        "display_order": 1,
    },
    "stage1_article": {
        "name": "Stage 1 Article Builder",
        "description": "Develop a new independent article from Title through Methods, with data-source or instrument guidance and DOCX export.",
        "price_usd": 6.99,
        "per": "article",
        "module": "article_writer",
        "ideas": 0,
        "drafts": 1,
        "revisions": 0,
        "exports": 1,
        "max_words": 6500,
        "token_allowance": 45000,
        "display_order": 2,
    },
    "standard_full_article": {
        "name": "Standard Full Article",
        "description": "Full empirical article of about 7,000-9,000 words with source-supported writing, DOCX export and one polishing pass.",
        "price_usd": 14.99,
        "per": "article",
        "module": "article_writer",
        "ideas": 0,
        "drafts": 1,
        "revisions": 1,
        "exports": 1,
        "max_words": 9000,
        "token_allowance": 80000,
        "display_order": 3,
    },
    "long_article_plus": {
        "name": "Long Article Plus",
        "description": "Long article of about 10,000-13,000 words using batch drafting, richer source integration, DOCX export and one polishing pass.",
        "price_usd": 19.99,
        "per": "article",
        "module": "article_writer",
        "ideas": 0,
        "drafts": 1,
        "revisions": 1,
        "exports": 1,
        "max_words": 13000,
        "token_allowance": 120000,
        "display_order": 4,
    },
    "review_conceptual_scoping": {
        "name": "Review / Conceptual / Scoping Article",
        "description": "Review, conceptual, scoping or theory article with deeper literature synthesis, DOCX export and one polishing pass.",
        "price_usd": 24.99,
        "per": "article",
        "module": "article_writer",
        "ideas": 0,
        "drafts": 1,
        "revisions": 1,
        "exports": 1,
        "token_allowance": 150000,
        "display_order": 5,
    },
    "article_revision": {
        "name": "Article Polishing and Revision",
        "description": "Revise an existing article, strengthen contribution, method fit, analysis alignment, discussion and recommendations.",
        "price_usd": 7.99,
        "per": "article",
        "module": "article_revision",
        "ideas": 0,
        "drafts": 0,
        "revisions": 1,
        "exports": 1,
        "token_allowance": 60000,
        "display_order": 6,
    },
    "reviewer_comment_revision": {
        "name": "Reviewer Comment Revision",
        "description": "Revise using reviewer, supervisor or editor comments and produce a response matrix.",
        "price_usd": 9.99,
        "per": "article",
        "module": "article_revision",
        "ideas": 0,
        "drafts": 0,
        "revisions": 1,
        "exports": 1,
        "token_allowance": 75000,
        "display_order": 7,
    },
    "extra_revision_pass": {
        "name": "Extra Revision Pass",
        "description": "One additional polishing or correction pass on a previously generated or revised article.",
        "price_usd": 4.99,
        "per": "article",
        "module": "article_revision",
        "ideas": 0,
        "drafts": 0,
        "revisions": 1,
        "exports": 1,
        "token_allowance": 35000,
        "display_order": 8,
    },
}


def normalise_email(email: str) -> str:
    return str(email or "").strip().lower()


def normalise_work_id(work_id: Any = "") -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(work_id or "").strip())
    return value[:120] or "general"


def ordered_plans() -> List[Tuple[str, Dict[str, Any]]]:
    return sorted(ARTICLE_PLANS.items(), key=lambda item: item[1].get("display_order", 999))


def get_plan(plan_key: str) -> Dict[str, Any]:
    key = str(plan_key or "").strip().lower()
    plan = ARTICLE_PLANS.get(key)
    if not plan:
        raise ValueError(f"Unknown ArticleReady AI plan: {plan_key}")
    result = deepcopy(plan)
    result["plan_key"] = key
    result["currency"] = DEFAULT_DISPLAY_CURRENCY
    result["amount"] = float(result["price_usd"])
    result["price_display"] = f"US${result['price_usd']:.2f}"
    result["validity_days"] = PURCHASE_VALIDITY_DAYS
    return result


def get_price(plan_key: str) -> Dict[str, Any]:
    plan = get_plan(plan_key)
    return {"amount": float(plan["price_usd"]), "currency": "USD", "display": f"US${float(plan['price_usd']):.2f}"}


def quota_payload(plan_key: str) -> Dict[str, int]:
    plan = get_plan(plan_key)
    return {
        "ideas_total": int(plan.get("ideas") or 0),
        "drafts_total": int(plan.get("drafts") or 0),
        "revisions_total": int(plan.get("revisions") or 0),
        "exports_total": int(plan.get("exports") or 0),
    }


def expiry_datetime(validity_days: int = PURCHASE_VALIDITY_DAYS) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=max(1, int(validity_days or PURCHASE_VALIDITY_DAYS)))


def build_plans_payload() -> Dict[str, Any]:
    plans: List[Dict[str, Any]] = []
    for key, _ in ordered_plans():
        plan = get_plan(key)
        plans.append({
            "plan_key": key,
            "name": plan["name"],
            "description": plan["description"],
            "amount": plan["amount"],
            "currency": plan["currency"],
            "price_display": plan["price_display"],
            "per": plan.get("per", "article"),
            "module": plan.get("module"),
            "token_allowance": int(plan.get("token_allowance") or 0),
            "max_ideas": plan.get("max_ideas"),
            "max_words": plan.get("max_words"),
            "includes": {
                "idea_runs": int(plan.get("ideas") or 0),
                "drafts": int(plan.get("drafts") or 0),
                "revisions": int(plan.get("revisions") or 0),
                "docx_exports": int(plan.get("exports") or 0),
            },
            "validity_days": plan["validity_days"],
        })
    return {
        "product": "ArticleReady AI",
        "billing_model": "one-off per article package",
        "display_currency": DEFAULT_DISPLAY_CURRENCY,
        "plans": plans,
        "free_trial": {
            "price_display": "US$0",
            "entitlement": "3 article ideas only",
            "limits": {"max_ideas": 3, "docx_export": False, "source_attachment": False, "full_article_writing": False},
        },
        "routing_note": "African billing countries use Paystack. Other billing countries use Stripe.",
    }


def action_columns(action: str) -> Tuple[str, str]:
    action_key = str(action or "").strip().lower()
    if action_key not in ACTION_FIELDS:
        raise ValueError(f"Unknown entitlement action: {action}")
    return ACTION_FIELDS[action_key]
