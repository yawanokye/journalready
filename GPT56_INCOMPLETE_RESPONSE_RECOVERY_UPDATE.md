# GPT-5.6 incomplete-response recovery update

ArticleReady AI 2.2.1 corrects long-section revision failures caused by incomplete Responses API output.

## Main corrections

- Completed-response enforcement for manuscript sections, revision plans, reports and reviewer matrices.
- Results and Discussion are never packed into one request.
- Default section batch size reduced to 1,400 words.
- Section output allowance increased to 24,000 tokens.
- Automatic recursive split and retry for incomplete or truncated sections.
- Terra high recovery before Sol escalation.
- OpenAlex compact-query retry and non-blocking source-provider warnings.

## Recommended production values

```env
ARTICLEREADY_REVISION_SECTION_MAX_WORDS=1400
ARTICLEREADY_REVISION_PACK_MAX_WORDS=1400
ARTICLEREADY_REVISION_PACK_SHORT_SECTIONS=1
ARTICLEREADY_REVISION_SECTION_MAX_OUTPUT_TOKENS=24000
ARTICLEREADY_REVISION_RETRY_SPLIT_MAX_DEPTH=3
ARTICLEREADY_REVISION_RETRY_MIN_WORDS=280
ARTICLEREADY_REVISION_MIN_SECTION_LENGTH_RATIO=0.58
```
