# ArticleReady AI 2.3.0 Deployment Guide

## Render service

Deploy one Python web service from the repository.

```text
Build command: python -m pip install --upgrade pip && python -m pip install -r requirements.txt
Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
Health check: /health
```

The included `render.yaml` defines a Starter service named `journalready` and a 1 GB persistent disk mounted at `/var/data`.

## Persistent storage

Use:

```env
ARTICLEREADY_SQLITE_DB_PATH=/var/data/articleready_payments.db
ARTICLEREADY_REVIEW_DB_PATH=/var/data/articleready_review_workspace.db
```

Only data written below the disk mount persists across deploys.

## OpenAI configuration

Set:

```env
OPENAI_API_KEY=<secret>
ARTICLEREADY_ALLOWED_MODEL_FAMILIES=gpt-5.4,gpt-5.5,gpt-5.6
ARTICLEREADY_ALLOW_UNAPPROVED_MODELS=0

OPENAI_ARTICLE_WRITING_MODEL=gpt-5.5
OPENAI_ARTICLE_CONCEPTUAL_MODEL=gpt-5.5
OPENAI_ARTICLE_REVISION_MODEL=gpt-5.5
OPENAI_ARTICLE_HUMANIZER_MODEL=gpt-5.4
OPENAI_ARTICLE_ANALYSIS_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_AUDIT_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_REVISION_RECOVERY_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_FAST_MODEL=gpt-5.6-luna
OPENAI_ARTICLE_REVISION_PLAN_MODEL=gpt-5.6-luna
OPENAI_ARTICLE_ESCALATION_MODEL=gpt-5.6-sol
OPENAI_ARTICLE_FALLBACK_MODELS=gpt-5.6-terra,gpt-5.6-sol

OPENAI_ARTICLE_WRITING_REASONING=high
OPENAI_ARTICLE_CONCEPTUAL_REASONING=high
OPENAI_ARTICLE_REVISION_REASONING=high
OPENAI_ARTICLE_REVISION_RECOVERY_REASONING=high
OPENAI_ARTICLE_HUMANIZER_REASONING=medium
OPENAI_ARTICLE_ANALYSIS_REASONING=xhigh
OPENAI_ARTICLE_ANALYSIS_RECOVERY_REASONING=high
OPENAI_ARTICLE_FAST_REASONING=high
OPENAI_ARTICLE_ESCALATION_REASONING=high

OPENAI_ARTICLEREADY_TIMEOUT_SECONDS=600
ARTICLEREADY_REVISION_TIMEOUT_SECONDS=600
OPENAI_ARTICLEREADY_SDK_RETRIES=1
OPENAI_ARTICLEREADY_ATTEMPTS_PER_MODEL=1
OPENAI_ARTICLEREADY_CHAT_FALLBACK=0
ARTICLEREADY_REVISION_BATCH_THRESHOLD_WORDS=4500
ARTICLEREADY_REVISION_SECTION_MAX_WORDS=1400
ARTICLEREADY_REVISION_SECOND_HUMANIZER_MODEL_PASS=1
ARTICLEREADY_REVISION_USE_AI=1
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0
```

The writing pipeline uses GPT-5.5 for substantive scholarly prose and GPT-5.4 for the selective final naturalness pass. GPT-5.6 Terra handles analysis and recovery, Luna handles planning, and Sol is reserved for exceptional escalation. Aliases may be replaced with dated snapshots that the deployed project can access.

`ARTICLEREADY_ALLOW_REVISION_FALLBACK=0` is important. When no substantive revision is produced, the API returns 503 and the paid entitlement claim is rolled back instead of returning the original manuscript as completed work.

## Scholarly metadata providers

Recommended:

```env
SEMANTIC_SCHOLAR_API_KEY=<secret>
OPENALEX_MAILTO=aadam@ucc.edu.gh
CROSSREF_MAILTO=aadam@ucc.edu.gh
ARTICLEREADY_METADATA_MAX_ATTEMPTS=3
ARTICLEREADY_METADATA_429_COOLDOWN_SECONDS=60
```

A Semantic Scholar 429 is treated as a temporary provider warning. OpenAlex and Crossref results can still support the source bank while the cooldown is active.

## Payments

```env
ARTICLEREADY_PAYMENT_REQUIRED=1
APP_BASE_URL=https://articlereadyai.com
PAYSTACK_SECRET_KEY=<secret>
STRIPE_SECRET_KEY=<secret>
STRIPE_WEBHOOK_SECRET=<secret>
```

Provider callbacks and webhook URLs remain those configured for the ArticleReady payment routes.

## Developer access

```env
ARTICLEREADY_DEVELOPER_ACCESS_ENABLED=1
ARTICLEREADY_DEVELOPER_ACCESS_EMAIL=aadam@ucc.edu.gh
ARTICLEREADY_DEVELOPER_ACCESS_CODE_SHA256=<64-character-sha256>
ARTICLEREADY_DEVELOPER_ACCESS_SECRET=<separate-long-random-secret>
ARTICLEREADY_DEVELOPER_SESSION_HOURS=12
```

The signing secret must be separate from the six-digit code hash. The browser stores the developer token in `sessionStorage`, so closing the browser session removes it.

## Security configuration

```env
ARTICLEREADY_ALLOWED_HOSTS=articlereadyai.com,www.articlereadyai.com,*.onrender.com,localhost,127.0.0.1,testserver
ARTICLEREADY_ALLOWED_ORIGINS=https://articlereadyai.com,https://www.articlereadyai.com
ARTICLEREADY_TRUST_PROXY_HEADERS=1
ARTICLEREADY_RATE_LIMIT_ENABLED=1
ARTICLEREADY_HSTS_ENABLED=1
ARTICLEREADY_ENABLE_API_DOCS=0
ARTICLEREADY_SECURITY_CONTACT=mailto:aadam@ucc.edu.gh
```

Do not use `*` for allowed CORS origins. Add a staging domain explicitly when needed.

## Deployment sequence

1. Attach the disk at `/var/data`.
2. Add the required environment variables and secrets.
3. Commit the updated source.
4. Use **Manual Deploy → Clear build cache & deploy**.
5. Confirm `/health`, `/robots.txt` and `/favicon.ico` return `200`.
6. Open `/article-revision` and hard-refresh once.
7. Run a developer-access revision test.
8. Confirm a provider failure returns `503 revision_service_unavailable` and does not consume the revision entitlement.
9. Confirm a successful revision returns `mode: ai_revision` and enables DOCX export.

## Validation before deployment

```bash
python -m compileall -q app
node --check app/static/article_revision.js
node --check app/static/articleready_payments.js
PYTHONPATH=. pytest -q tests/test_article_workflows.py tests/test_developer_access.py tests/test_humanisation_layer.py tests/test_humanizer_citation_topic_export.py tests/test_payments.py tests/test_review_protocol.py tests/test_review_workspace.py tests/test_security_hardening.py
```
