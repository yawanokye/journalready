# Article Writer Source Attachment Update

The article writer now supports the same explicit source-search and attachment workflow used in the thesis workspace.

## User workflow

1. Enter the article title, research area, extraction focus, or custom search terms.
2. Select the maximum number of records and whether older foundational literature should be included.
3. Click **Find and attach sources**.
4. Review the returned metadata records.
5. Draft the article. The full deduplicated attached source bank is sent with the request.

## Drafting rules

- Attached sources enrich the supplied thesis, study material, results, and verified notes. They do not replace them.
- Every source passes a relevance gate before citation.
- Internal source keys such as S1 are not used as citations.
- Metadata and abstracts are not treated as proof that the full paper was read.
- Retracted, withdrawn, removed, and expression-of-concern records are excluded where detectable.
- The manuscript prompt requests a **Source Use Audit** after the References section.

## Changed files

- `app/schemas.py`
- `app/article_service.py`
- `app/routers.py`
- `app/main.py`
- `app/static/article_writer.html`
- `app/static/article_writer.js`
- `app/static/styles.css`
- `tests/test_article_workflows.py`
- `README.md`
