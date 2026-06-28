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
- `OPENAI_API_KEY`: used for article drafting and article revision
- `OPENAI_ARTICLE_REVISION_MODEL`: defaults to `gpt-5.5`
- `ARTICLEREADY_REVISION_USE_AI`: set to `1` to enable AI revision

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
