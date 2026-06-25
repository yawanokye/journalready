# Staged article and research-resource update

## Article Topic Ideas

- Added research-route selection and automatic route detection.
- Added candidate official secondary-data sources for secondary and archival research.
- Added candidate questionnaire, scale, interview-guide and instrument sources for primary, qualitative, mixed-methods and experimental research.
- Added instrument-publication searches through the existing scholarly metadata providers.
- Added resource guidance to each article idea and an aggregate research-resource section.
- Added access, licensing, adaptation and validation cautions.

## Article Writer

- Added `full_article`, `initial_to_methods` and `continuation_after_results` stages.
- Independent article mode disables thesis, dissertation and project fields.
- Independent article mode defaults to PhD depth and Stage 1.
- Stage 1 stops the manuscript body at Methods.
- Added separate research-resource search and display.
- Added optional separate questionnaire, interview-guide or measurement-plan drafting.
- Added Stage 2 upload fields for previous sections and completed analysis.
- Added DOCX, PDF, XLSX, CSV, TXT, MD, RTF, LOG and JSON text extraction.
- Added separate copy and DOCX export controls for the instrument package.

## Files added

- `app/research_resources.py`
- `app/file_extractor.py`
- `STAGED_ARTICLE_UPDATE.md`

## Main files updated

- `app/article_ideas_service.py`
- `app/article_service.py`
- `app/schemas.py`
- `app/routers.py`
- `app/main.py`
- `app/static/topic_ideas.html`
- `app/static/topic_ideas.js`
- `app/static/article_writer.html`
- `app/static/article_writer.js`
- `app/static/styles.css`
- `requirements.txt`
- `.env.example`
- `README.md`
- `tests/test_article_workflows.py`
