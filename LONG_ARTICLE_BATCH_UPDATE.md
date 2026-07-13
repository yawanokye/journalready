# Long Article and Batch Writing Update

This update adds ProjectReady-style length and batching controls to the ArticleReady AI Article Writer.

## Added

- Target total words field
- User-defined article structure field, one section per line with optional word targets
- Long writing mode: Auto, Single pass, Batch
- Automatic batch drafting for long articles, default threshold 6,500 words
- Backend article-length plan and token-budget estimate
- Larger input limits for source material, continuation material and results fields
- `max_output_tokens` passed to the Responses API for article drafting
- Frontend token estimate and batch-status notes

## Backend response additions

- `article_length_plan`
- `token_budget_estimate`
- `batch_drafting_applied`
- `drafting_passes`

## Environment variables

```text
ARTICLEREADY_BATCH_DRAFT_WORD_THRESHOLD=6500
ARTICLEREADY_ARTICLE_MAX_OUTPUT_TOKENS=24000
ARTICLEREADY_ARTICLE_HARD_OUTPUT_CAP=60000
ARTICLEREADY_ARTICLE_MATERIAL_CHARS=120000
ARTICLEREADY_ARTICLE_CONTINUATION_CHARS=140000
ARTICLEREADY_ARTICLE_DATA_CHARS=120000
ARTICLEREADY_AUTHOR_GUIDELINE_CHARS=30000
```

## Token planning guide

A 7,000-9,000 word article usually needs about 9,500-12,500 output tokens for the article body. Total usage is higher because the model also reads the prompt, source records, uploaded material, author guidelines and results.

Typical planning ranges:

- Light source context, single pass: 20,000-40,000 total tokens
- Source-supported article with uploaded material: 35,000-75,000 total tokens
- Batch mode with repeated context: 60,000-140,000 total tokens

These are estimates. Actual usage depends on the article type, source-bank size, number of sections, tables, equations, references and amount of uploaded material.
