# ArticleReady AI 2.2.0

ArticleReady AI supports journal-article topic development, scholarly-source discovery, full article drafting, article revision, DOCX export and an auditable Review Evidence Workspace.

## Main modules

- **Article Topic Ideas**: develops article-ready topic portfolios and exports them to DOCX.
- **Article Writer**: produces staged empirical articles and complete conceptual, systematic, scoping, integrative and bibliometric manuscripts when the required evidence is available.
- **Article Revision**: substantively revises an existing article, prepares a publication-readiness report and creates a reviewer-response matrix.
- **Review Evidence Workspace**: imports database records, manages duplicate decisions and screening, calculates verified record-flow counts and exports the evidence ledger and protocol audit.
- **Payments and developer access**: supports Paystack, Stripe and restricted developer testing.

## Revision reliability in 2.2.0

ArticleReady uses a cost-controlled GPT-5.6 workflow:

- GPT-5.6 Terra with `xhigh` reasoning performs substantive article drafting and revision.
- Terra with `high` reasoning is the first revision recovery pass.
- GPT-5.6 Luna prepares compact revision plans and reviewer-response support.
- GPT-5.6 Sol is reserved for exceptional escalation.
- Old GPT-5, GPT-5.1 and GPT-5-mini defaults are rejected unless a deliberate compatibility override is enabled.

Long manuscripts are revised section by section, then reassembled and validated before the revision report and reviewer-response matrix are produced separately. The workflow sends OpenAI requests with `store=false`, logs request purpose and timing without logging manuscript text, and returns a retryable `503 revision_service_unavailable` response when no substantive full-manuscript revision is produced. The paid entitlement claim then rolls back.

Keep these production settings:

```env
ARTICLEREADY_ALLOW_NON_GPT56_MODELS=0
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0
OPENAI_ARTICLEREADY_CHAT_FALLBACK=0
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
ARTICLEREADY_ALLOW_NON_GPT56_MODELS=0
OPENAI_ARTICLE_STANDARD_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_ADVANCED_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_REVISION_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_HUMANIZER_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_FAST_MODEL=gpt-5.6-luna
OPENAI_ARTICLE_REVISION_PLAN_MODEL=gpt-5.6-luna
OPENAI_ARTICLE_ESCALATION_MODEL=gpt-5.6-sol
OPENAI_ARTICLE_FALLBACK_MODELS=gpt-5.6-terra,gpt-5.6-sol
OPENAI_ARTICLE_ADVANCED_REASONING=xhigh
OPENAI_ARTICLE_REVISION_REASONING=xhigh
OPENAI_ARTICLE_REVISION_RECOVERY_REASONING=high
OPENAI_ARTICLE_FAST_REASONING=high
OPENAI_ARTICLE_ESCALATION_REASONING=high
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

The production default is restricted to the verified GPT-5.6 family. Terra handles substantive drafting and revision, Luna handles lower-cost planning and support tasks, and Sol is reserved for exceptional escalation. Set `ARTICLEREADY_ALLOW_NON_GPT56_MODELS=1` only for deliberate compatibility testing.

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
  tests/test_security_hardening.py \
  tests/test_gpt56_revision_pipeline.py

python -m compileall -q app
node --check app/static/article_revision.js
node --check app/static/articleready_payments.js
```

See `DEPLOYMENT.md` and `SECURITY_AND_REVISION_RECOVERY_UPDATE.md` for deployment details.
