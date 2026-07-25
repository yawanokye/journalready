# ArticleReady AI 2.2.0: GPT-5.6 Batched Revision Update

## Model routing

- GPT-5.6 Terra with xhigh reasoning performs substantive article drafting and revision.
- Terra high is the first recovery pass to reduce latency and cost.
- GPT-5.6 Luna prepares compact revision plans and reviewer-response support.
- GPT-5.6 Sol is used only as an exceptional escalation model.
- Old GPT-5, GPT-5.1 and GPT-5-mini defaults have been removed.

## Revision reliability

- Articles at or above the configured word threshold are revised in heading-led batches.
- Each section is validated against truncation before the manuscript is reassembled.
- The revision report and reviewer-response matrix are generated separately from the manuscript revision.
- Reference sections are retained unchanged during batched revision to prevent unverified bibliographic alterations.
- Provider calls include reasoning effort, request purpose, bounded retries, timeout controls and privacy-preserving logs.
- Paid revision claims continue to roll back when no substantive full-manuscript revision is produced.

## Default production settings

```env
OPENAI_ARTICLE_REVISION_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_REVISION_REASONING=xhigh
OPENAI_ARTICLE_REVISION_RECOVERY_REASONING=high
OPENAI_ARTICLE_REVISION_PLAN_MODEL=gpt-5.6-luna
OPENAI_ARTICLE_ESCALATION_MODEL=gpt-5.6-sol
OPENAI_ARTICLEREADY_TIMEOUT_SECONDS=600
ARTICLEREADY_REVISION_TIMEOUT_SECONDS=600
ARTICLEREADY_REVISION_BATCH_THRESHOLD_WORDS=4500
ARTICLEREADY_REVISION_SECTION_MAX_WORDS=2400
ARTICLEREADY_REVISION_SECTION_MAX_OUTPUT_TOKENS=14000
OPENAI_ARTICLEREADY_CHAT_FALLBACK=0
ARTICLEREADY_REVISION_SECOND_HUMANIZER_MODEL_PASS=0
```
