# JournalReady AI

JournalReady AI is a standalone FastAPI application for developing journal article ideas and drafting manuscripts. It is intentionally separate from ProjectReady AI, which remains focused on theses, dissertations and project chapters.

## Main modules

### 1. Article Topic Ideas

The `/topic-ideas` page develops publication-focused ideas from a thesis, dissertation, research project, dataset or new study. Each proposed idea includes:

- focused article title and angle
- article-level literature gap
- one overall article objective
- tightly aligned research questions or hypotheses
- contribution and journal fit
- method and data route
- evidence still required
- readiness score
- warning against compressing the entire thesis or duplicating claims

The workflow is designed to distinguish legitimate separate papers from salami slicing. It does not treat a journal paper as a shortened thesis.

### 2. Journal Article Writer

The `/article-writer` page accepts:

- article title and type
- source thesis or study material
- article extraction focus
- target journal and author guidelines
- article-level problem, objective and contribution
- methods, actual results and verified source notes
- word limit and citation style

It returns a Markdown manuscript draft and supports DOCX export. Missing evidence is shown in bracketed attention placeholders. Detected retracted or withdrawn source records are excluded where metadata exposes their status.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/topic-ideas`
- `http://127.0.0.1:8000/article-writer`

## Render deployment

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Add `OPENAI_API_KEY` and the desired model variables from `.env.example` in Render.

## API routes

- `POST /api/article-ideas`
- `POST /api/articles/draft`
- `POST /api/articles/export`
- `GET /health`

## Separation from ProjectReady AI

Deploy this folder as its own Render web service and domain or subdomain. Recommended examples are `journalreadyai.com`, `article.projectreadyai.com`, or another dedicated publication brand. The accompanying cleaned ProjectReady archive no longer loads the journal writer route.
