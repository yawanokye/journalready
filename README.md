# ArticleReady AI

ArticleReady AI is a standalone FastAPI application for article-topic development, staged manuscript writing, article polishing and revision, research-resource guidance and DOCX export. It remains separate from ProjectReady AI, which is focused on theses, dissertations and project chapters.

## Main workflows

### 1. Article Topic Ideas

The `/topic-ideas` page develops publication-focused ideas from a thesis, dissertation, completed project, existing dataset or a new independent study. Each idea includes:

- focused article title, angle and article-level gap
- one overall objective with aligned questions or hypotheses
- contribution, journal fit and method route
- readiness score and evidence still needed
- identified research route
- possible official secondary datasets where secondary research is suitable
- possible questionnaire, scale, interview-guide or instrument sources where primary or qualitative research is suitable
- warnings on access, licensing, adaptation, validity and salami slicing

Candidate resources are not automatic endorsements. Users must verify variable coverage, time and geographic coverage, population fit, access conditions, copyright or licence terms, ethics and validation requirements.

For a **new independent article**, thesis and dissertation fields are hidden and removed from the backend payload. The topic-idea prompt and structured fallback use proposal language only. Macroeconomic, financial-market, interest-rate, yield-curve, bond and exchange-rate topics default to secondary or archival data unless the user explicitly selects another route.

Scholarly records now pass a conservative topic-relevance gate before they are shown or sent to the idea model. Country-only matches, records sharing only one broad word, and discipline-mismatched ERIC results are excluded. The app prefers a short relevant list to a long noisy list.

#### AI provider for article ideas

Article Topic Ideas use **DeepSeek V4 Pro** through the official DeepSeek OpenAI-compatible API. This provider is isolated to `app/article_ideas_service.py`. The Article Writer continues to use the configured OpenAI models. If `DEEPSEEK_API_KEY` is missing or a DeepSeek request fails, the topic-idea workflow uses its structured fallback rather than switching silently to OpenAI.

### 2. Article Writer

The `/article-writer` page now supports three writing stages:

1. **Full article from a completed study**
2. **Stage 1: Develop a new article up to Methods**
3. **Stage 2: Complete the article after results or analysis**

When **Develop as a new independent article** is selected:

- thesis, dissertation and project source fields are disabled
- PhD is selected as the default research depth
- the default workflow changes to Stage 1
- the manuscript body is limited to Title through Methods
- Results, Discussion and Conclusion are withheld until evidence is supplied
- possible secondary data sources or instrument sources are listed
- an optional provisional questionnaire, interview guide or measurement plan can be produced separately

For Stage 2, users can upload or paste the earlier article sections and completed analysis. Supported uploads are DOCX, text-based PDF, XLSX, CSV, TXT, MD, RTF, LOG and JSON. The app extracts the text for review, then integrates the previous sections and confirmed results into a completed article.

#### Long article and batch writing

The Article Writer includes a length and structure control. Users can set a target word count, enter a journal-specific article structure with section word targets, and choose between Auto, Single pass and Batch writing. Auto uses batch drafting when the target manuscript is long, currently 6,500 words or more. Batch writing drafts the article section by section so a 7,000-9,000 word manuscript can be developed with stronger depth and less risk of ending as a short outline.

The backend returns `article_length_plan`, `token_budget_estimate`, `batch_drafting_applied` and `drafting_passes` with each draft response. These values support token-based pricing and usage display.

### 3. Scholarly source attachment

Users can search OpenAlex, Crossref and Semantic Scholar before drafting. ERIC is searched only for education-related topics. Returned records are deduplicated, filtered for detected retractions or withdrawals, attached to the evidence bank and passed through a relevance gate. Attached sources enrich the user's evidence rather than replacing it.

### 4. Article Polishing and Revision

The `/article-revision` page revises an existing manuscript at PhD-level depth while preserving confirmed evidence. Users can upload or paste the article, add target-journal requirements and optionally paste or upload reviewer comments. The module can:

- strengthen conceptualisation, theoretical framing and construct logic
- clarify theoretical, empirical, methodological, contextual and practical contribution
- assess alignment among the problem, objectives, design, sampling, measurement and claims
- assess whether the analysis is appropriate for the stated claims
- recommend additional diagnostics, robustness, sensitivity, endogeneity, mediation, moderation, heterogeneity, validity or trustworthiness analysis where suitable
- rebuild the Discussion around mechanisms, competing explanations, boundaries and literature comparison
- sharpen implications and recommendations so they follow from confirmed findings
- produce a revision and publishability report without guaranteeing acceptance
- produce a response-to-reviewers matrix when comments are supplied
- export a DOCX in which added or changed wording is blue and exact unchanged wording remains black

Suggested additional analyses are never presented as completed. Missing evidence is identified as an author action. Confirmed statistics, quotations, tables and findings must not be silently changed.

## API routes

- `POST /api/article-ideas`
- `POST /api/articles/research-resources`
- `POST /api/articles/find-sources`
- `POST /api/articles/extract-file`
- `POST /api/articles/draft`
- `POST /api/articles/export`
- `POST /api/articles/revise`
- `POST /api/articles/revision/export`
- `GET /health`

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/topic-ideas`
- `http://127.0.0.1:8000/article-writer`
- `http://127.0.0.1:8000/article-revision`

## Render deployment

Use:

- Python version: `3.12.11`
- Build command: `python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Add these Render environment variables:

- `DEEPSEEK_API_KEY`: your DeepSeek API key
- `DEEPSEEK_ARTICLE_IDEA_MODEL`: `deepseek-v4-pro`
- `DEEPSEEK_ARTICLE_IDEA_THINKING`: `1`
- `DEEPSEEK_ARTICLE_IDEA_REASONING_EFFORT`: `high`
- `OPENAI_API_KEY`: used for article drafting, article revision and the optional model-assisted humanisation pass
- `OPENAI_ARTICLE_TERRA_MODEL`: `gpt-5.6-terra`, used for standard drafting and humanisation
- `OPENAI_ARTICLE_SOL_MODEL`: `gpt-5.6-sol`, used for doctoral, research-heavy, review, long and revision workflows
- `OPENAI_ARTICLE_REVISION_MODEL`: `gpt-5.6-sol`
- `OPENAI_ARTICLE_HUMANIZER_MODEL`: `gpt-5.6-terra`
- `ARTICLEREADY_REVISION_USE_AI`: set to `1` to enable article revision
- `ARTICLEREADY_HUMANIZER_MODE`: `balanced` by default; supported values are `off`, `light`, `balanced` and `deep`
- `ARTICLEREADY_HUMANIZER_MODEL_PASS`: set to `1` to enable the preservation-gated Terra pass
- `ARTICLEREADY_BATCH_DRAFT_WORD_THRESHOLD`: default `6500`; auto batch drafting begins at or above this target
- `ARTICLEREADY_ARTICLE_MAX_OUTPUT_TOKENS`: default `24000`; output ceiling for one article-generation call
- `ARTICLEREADY_ARTICLE_MATERIAL_CHARS`, `ARTICLEREADY_ARTICLE_CONTINUATION_CHARS` and `ARTICLEREADY_ARTICLE_DATA_CHARS`: input extraction limits used before drafting

The additional upload dependencies are already listed in `requirements.txt`:

- `python-multipart`
- `pypdf`
- `openpyxl`

After replacing the repository files, use **Clear build cache & deploy** on Render so the new dependencies are installed.

## Tests

```bash
PYTHONPATH=. pytest -q
```

The test suite covers article ideas, strict topic-source filtering, duplicate-query control, secondary-data guidance, independent-article wording, independent-article Stage 1, instrument drafting, Stage 2 validation, file extraction, article revision fallback, revision-package parsing and blue-revision DOCX export.

## ThesisReady-derived scholarly humanisation layer

Article drafting and article revision use the same preservation-gated scholarly humaniser adopted from ThesisReady. A deterministic pass improves formulaic phrasing, rhythm, paragraph variation and lexical repetition. An optional section-batched GPT-5.6 Terra pass is applied only where the diagnostic score indicates that further naturalisation is useful. Every candidate revision is rejected unless headings, citations, numbers, equations, tables, URLs, references and bracketed author-action items are preserved. Configure it with `ARTICLEREADY_HUMANIZER_MODE`, `ARTICLEREADY_HUMANIZER_MODEL_PASS`, `ARTICLEREADY_HUMANIZER_BATCH_WORDS` and the other humaniser variables in `.env.example`.

## GPT-5.6 routing

All OpenAI-backed ArticleReady workflows are restricted to the GPT-5.6 family. GPT-5.6 Terra handles standard and cost-balanced article work. GPT-5.6 Sol handles research-master's and doctoral articles, review/conceptual/systematic articles, long or batch articles, Stage 2 completion and article revision. Legacy GPT-5.4 or GPT-5.5 environment values are ignored by the runtime model normaliser. Article Topic Ideas remains on DeepSeek V4 Pro as a separate provider choice.


## Pricing plans

The public pricing page is available at `/pricing`. Current package structure:

| Package | Price | Main entitlement | Internal token allowance |
|---|---:|---|---:|
| Free Trial | Free | 3 article ideas, no DOCX export | 5,000 |
| Article Ideas | US$2.99 | Up to 20 article ideas with readiness score, contribution angle, possible data/instrument sources and overlap warnings | 20,000 |
| Stage 1 Article Builder | US$6.99 | New independent article up to Methods with framework, methods, data-source or instrument guidance and DOCX export | 45,000 |
| Standard Full Article | US$14.99 | 7,000-9,000 word source-supported article with DOCX export and one polishing pass | 80,000 |
| Long Article Plus | US$19.99 | 10,000-13,000 word article with batch drafting and one polishing pass | 120,000 |
| Review / Conceptual / Scoping Article | US$24.99 | Source-heavy review, scoping, conceptual or theory article with DOCX export and one polishing pass | 150,000 |
| Article Polishing and Revision | US$7.99 | Existing article revision with blue revised text and red action items | 60,000 |
| Reviewer Comment Revision | US$9.99 | Revision using reviewer/editor/supervisor comments with response matrix | 75,000 |
| Extra Revision Pass | US$4.99 | Additional polishing pass on a prior output | 35,000 |

Each paid package should include one successful generation and one DOCX export within the selected plan scope. If the user exceeds the word, source or token allowance, the interface should request an upgrade before continuing.

## Payment system

Successful Paystack and Stripe callbacks create a short-lived, single-use payment-return handoff. The browser redeems it and rotates the access token, so payment access survives blocked or cleared pre-checkout local storage. A self-service recovery page is available at `/payment/recover` for customers who have the payment email and Purchase ID.


ArticleReady AI includes a one-off package payment system similar to ProjectReady AI. African billing countries use Paystack, while all other billing countries use Stripe Checkout. Paid actions are enforced through ArticleReady purchase credentials saved after checkout.

Set `ARTICLEREADY_PAYMENT_REQUIRED=1` in production. For local testing, set it to `0`.

See `PAYMENT_SYSTEM_UPDATE.md` for plan keys, checkout routes, entitlement rules and required environment variables.
