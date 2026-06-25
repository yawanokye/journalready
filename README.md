# JournalReady AI

JournalReady AI is a standalone FastAPI application for article-topic development, staged manuscript writing, research-resource guidance and DOCX export. It remains separate from ProjectReady AI, which is focused on theses, dissertations and project chapters.

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

Users can search OpenAlex, Crossref, Semantic Scholar and ERIC before drafting. Returned records are deduplicated, filtered for detected retractions or withdrawals, attached to the evidence bank and passed through a relevance gate. Attached sources enrich the user's evidence rather than replacing it.

## API routes

- `POST /api/article-ideas`
- `POST /api/articles/research-resources`
- `POST /api/articles/find-sources`
- `POST /api/articles/extract-file`
- `POST /api/articles/draft`
- `POST /api/articles/export`
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

## Render deployment

Use:

- Python version: `3.12.11`
- Build command: `python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

The additional upload dependencies are already listed in `requirements.txt`:

- `python-multipart`
- `pypdf`
- `openpyxl`

After replacing the repository files, use **Clear build cache & deploy** on Render so the new dependencies are installed.

## Tests

```bash
PYTHONPATH=. pytest -q
```

The test suite covers article ideas, source-bank filtering, secondary-data guidance, independent-article Stage 1, instrument drafting, Stage 2 validation, file extraction and DOCX export.
