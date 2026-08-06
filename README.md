# ArticleReady AI 2.3.0

ArticleReady AI supports journal-article topic development, scholarly-source discovery, full article drafting, article revision, DOCX export and an auditable Review Evidence Workspace.

## Main modules

- **Article Topic Ideas**: develops article-ready topic portfolios and exports them to DOCX.
- **Article Writer**: produces staged empirical articles and complete conceptual, systematic, scoping, integrative and bibliometric manuscripts when the required evidence is available.
- **Article Revision**: substantively revises an existing article, prepares a publication-readiness report and creates a reviewer-response matrix.
- **Review Evidence Workspace**: imports database records, manages duplicate decisions and screening, calculates verified record-flow counts and exports the evidence ledger and protocol audit.
- **Payments and developer access**: supports Paystack, Stripe and restricted developer testing.

## Hybrid scholarly voice routing in 2.3.0

ArticleReady separates analytical work from final scholarly prose:

- GPT-5.5 with `high` reasoning performs substantive article drafting, conceptual writing and manuscript revision.
- GPT-5.4 with `medium` reasoning performs the selective preservation-gated final naturalness pass.
- GPT-5.6 Terra performs analytical recovery and revision reporting.
- GPT-5.6 Luna prepares compact revision plans and reviewer-response support.
- GPT-5.6 Sol is reserved for exceptional escalation after smaller recovery batches fail.

The startup validator accepts approved aliases and dated snapshots from the GPT-5.4, GPT-5.5 and GPT-5.6 families. Long manuscripts are revised section by section, but every batch receives the same global author-voice profile plus boundary context from adjacent sections. This reduces abrupt changes in tone, repeated transitions and the assembled-section effect.

Keep these production safeguards:

```env
ARTICLEREADY_ALLOWED_MODEL_FAMILIES=gpt-5.4,gpt-5.5,gpt-5.6
ARTICLEREADY_ALLOW_UNAPPROVED_MODELS=0
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0
OPENAI_ARTICLEREADY_CHAT_FALLBACK=0
```

## Truncation recovery

- Results and Discussion are not packed into the same revision request.
- Section batches default to 1,400 words and cannot cross a top-level heading family.
- A response with `status=incomplete` is rejected and retried through the recovery path.
- Incomplete or truncated sections are divided automatically into smaller recovery batches and reassembled only after validation.
- GPT-5.6 Sol is used only after repeated smaller recovery batches fail.
- OpenAlex and Semantic Scholar failures remain non-blocking source warnings.

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

ARTICLEREADY_REVISION_USE_AI=1
ARTICLEREADY_REVISION_SECOND_HUMANIZER_MODEL_PASS=1
ARTICLEREADY_ALLOW_REVISION_FALLBACK=0

ARTICLEREADY_SQLITE_DB_PATH=/var/data/articleready_payments.db
ARTICLEREADY_REVIEW_DB_PATH=/var/data/articleready_review_workspace.db

ARTICLEREADY_ALLOWED_HOSTS=articlereadyai.com,www.articlereadyai.com,*.onrender.com
ARTICLEREADY_ALLOWED_ORIGINS=https://articlereadyai.com,https://www.articlereadyai.com
ARTICLEREADY_RATE_LIMIT_ENABLED=1
ARTICLEREADY_HSTS_ENABLED=1
ARTICLEREADY_ENABLE_API_DOCS=0
```

Use dated GPT-5.4 or GPT-5.5 snapshots only after confirming that the deployed OpenAI project can access the exact model ID.

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
