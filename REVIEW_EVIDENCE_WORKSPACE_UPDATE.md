# Review Evidence Workspace update

Version 2.0.0 adds `/review-evidence`, a persistent and auditable workspace for evidence-synthesis projects.

## What it does

- Creates private workspaces protected by a random browser-held access token.
- Registers each database, platform, search route, exact search string, search date, limits and reported result count.
- Imports RIS, BibTeX, CSV, TSV, XLSX and JSON database exports.
- Removes exact DOI and normalised title-year duplicates, while routing high-similarity title matches to manual confirmation.
- Supports title/abstract and full-text screening, exclusion reasons, reviewer notes and full-text extraction.
- Calculates record-flow counts directly from the ledger.
- Produces a final included-study corpus only from confirmed full-text inclusions.
- Exports the complete ledger, included corpus, audit JSON and a protocol/evidence-audit DOCX.
- Transfers verified review fields and counts to Article Writer through a one-time browser payload.

## Deployment

The workspace uses the same persistent Render disk already mounted at `/var/data`.

```text
ARTICLEREADY_REVIEW_DB_PATH=/var/data/articleready_review_workspace.db
```

The application derives this path from `ARTICLEREADY_SQLITE_DB_PATH` when the explicit workspace variable is absent.

## Evidence safeguard

ArticleReady metadata discovery remains separate from formal review evidence. A source becomes part of formal record flow only when it is imported through a documented search run and receives confirmed screening decisions.
