# ArticleReady AI 2.1.0

ArticleReady AI supports journal-article topic development, scholarly-source discovery, full article drafting, article revision, DOCX export and an auditable Review Evidence Workspace.

## Main modules

- **Article Topic Ideas**: develops article-ready topic portfolios and exports them to DOCX.
- **Article Writer**: produces staged empirical articles and complete conceptual, systematic, scoping, integrative and bibliometric manuscripts when the required evidence is available.
- **Article Revision**: substantively revises an existing article, prepares a publication-readiness report and creates a reviewer-response matrix.
- **Review Evidence Workspace**: imports database records, manages duplicate decisions and screening, calculates verified record-flow counts and exports the evidence ledger and protocol audit.
- **Payments and developer access**: supports Paystack, Stripe and restricted developer testing.

## Revision reliability in 2.1.0

ArticleReady no longer returns the original manuscript as though a paid revision was completed when the model is unavailable.

The revision workflow now:

- accepts model IDs configured for the operator's OpenAI project;
- retries transient provider errors with bounded exponential backoff;
- tries a configured model fallback chain;
- can recover through Chat Completions when the Responses endpoint is temporarily unavailable;
- sends OpenAI requests with `store=false` by default;
- returns a retryable `503 revision_service_unavailable` response when no substantive revision is produced;
- allows the payment entitlement claim to roll back on that failure.

Keep this production setting:

```env
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0
```

## Source-provider resilience

Semantic Scholar can use an API key through:

```env
SEMANTIC_SCHOLAR_API_KEY=<secret>
```

Metadata providers use bounded retries and temporary cooldown after HTTP 429. A temporary failure from one source provider is recorded as a warning and does not by itself disable the revision model.

## Security controls

- Explicit host allow-list and restricted CORS origins
- Route-specific rate limiting
- Request and upload-size limits
- DOCX/XLSX archive-bomb and unsafe-path checks
- PDF page-count limit
- Content Security Policy
- HSTS on HTTPS
- Clickjacking, MIME-sniffing, referrer and permissions headers
- `no-store` for API and private workspace responses
- API documentation disabled by default
- Developer token stored only for the browser session
- `robots.txt`, `sitemap.xml`, favicon and `security.txt`
- `noindex` on developer, payment-recovery and review-workspace pages

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## Essential production variables

```env
OPENAI_API_KEY=<secret>
OPENAI_ARTICLE_STANDARD_MODEL=gpt-5-mini
OPENAI_ARTICLE_ADVANCED_MODEL=gpt-5.1
OPENAI_ARTICLE_REVISION_MODEL=gpt-5.1
OPENAI_ARTICLE_FALLBACK_MODELS=gpt-5.1,gpt-5,gpt-5-mini
ARTICLEREADY_REVISION_USE_AI=1
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0

ARTICLEREADY_SQLITE_DB_PATH=/var/data/articleready_payments.db
ARTICLEREADY_REVIEW_DB_PATH=/var/data/articleready_review_workspace.db

ARTICLEREADY_ALLOWED_HOSTS=articlereadyai.com,www.articlereadyai.com,*.onrender.com
ARTICLEREADY_ALLOWED_ORIGINS=https://articlereadyai.com,https://www.articlereadyai.com
ARTICLEREADY_RATE_LIMIT_ENABLED=1
ARTICLEREADY_HSTS_ENABLED=1
ARTICLEREADY_ENABLE_API_DOCS=0
```

Set model variables to model IDs that are actually available to the OpenAI project. The older `OPENAI_ARTICLE_TERRA_MODEL` and `OPENAI_ARTICLE_SOL_MODEL` names remain accepted for backward compatibility.

## Validation

```bash
PYTHONPATH=. pytest -q \
  tests/test_article_workflows.py \
  tests/test_developer_access.py \
  tests/test_humanisation_layer.py \
  tests/test_humanizer_citation_topic_export.py \
  tests/test_payments.py \
  tests/test_review_protocol.py \
  tests/test_review_workspace.py \
  tests/test_security_hardening.py

python -m compileall -q app
node --check app/static/article_revision.js
node --check app/static/articleready_payments.js
```

See `DEPLOYMENT.md` and `SECURITY_AND_REVISION_RECOVERY_UPDATE.md` for deployment details.
