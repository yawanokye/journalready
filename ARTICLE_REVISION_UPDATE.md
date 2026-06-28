# Article Polishing and Revision Update

## New module

A separate Article Polishing and Revision module is available at `/article-revision`. It accepts an existing article, target-journal guidance, confirmed method and results information, revision goals and optional reviewer comments.

## Revision scope

The module can strengthen conceptualisation, contribution, method fit, analysis logic, discussion, implications and recommendations. It produces a separate Revision and Publishability Report and, when review comments are supplied, a response-to-reviewers matrix.

## Evidence safeguards

- Confirmed numerical results and study facts must be preserved.
- Additional analyses are suggested but never presented as completed.
- Missing evidence is marked as an author action.
- Source records pass the existing relevance and retraction filters.
- The report does not guarantee acceptance or publication.

## DOCX revision colour

The revision export compares the existing article with the revised manuscript. Added or changed wording is displayed in Word blue (`#0070C0`). Exact unchanged wording remains black. The revision report and reviewer-response matrix are appended after a page break.

## New routes

- `POST /api/articles/revise`
- `POST /api/articles/revision/export`
- `GET /article-revision`

## Configuration

- `OPENAI_ARTICLE_REVISION_MODEL=gpt-5.5`
- `ARTICLEREADY_REVISION_USE_AI=1`
