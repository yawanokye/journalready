# ArticleReady AI Changelog

## 2.2.1, incomplete-response and section-truncation recovery

- Treats `status=incomplete` Responses API output as unfinished for revision, report and reviewer-response tasks.
- Retries Terra at lower reasoning effort before escalating.
- Separates top-level Results and Discussion batches and reduces the default section batch size to 1,400 words.
- Automatically splits a failed section into progressively smaller recovery batches and validates the reassembled section.
- Raises the default section output allowance to 24,000 tokens because the limit covers visible and reasoning tokens.
- Reserves Sol for exceptional escalation after repeated smaller Terra attempts.
- Labels OpenAlex and Semantic Scholar failures as non-blocking source warnings.
- Retries OpenAlex HTTP 400 queries with a compact plain-text query.
- Adds regression tests for incomplete responses, Results-Discussion boundaries and recursive split recovery.

## 2.2.0, GPT-5.6 cost-controlled batched revision

- Replaced all GPT-5, GPT-5.1 and GPT-5-mini defaults with GPT-5.6 routing.
- Assigned Terra `xhigh` to substantive drafting and revision, Terra `high` to recovery, Luna `high` to revision planning and response support, and Sol `high` to exceptional escalation.
- Added reasoning-effort parameters to Responses API calls.
- Increased the default provider and revision timeout to 600 seconds.
- Disabled Chat Completions fallback by default.
- Added heading-led section batching for manuscripts above the configured word threshold.
- Separated manuscript revision, revision reporting and reviewer-response generation into distinct calls.
- Preserved reference sections during batched revision to reduce bibliographic alteration risk.
- Added privacy-preserving provider timing and failure logs.
- Added revision batch, model and reasoning metadata to the browser result panel.
- Removed unrelated legacy test fixtures and local database files from the distribution.

## 2.1.0, security and revision recovery

- Added bounded OpenAI retries and provider recovery.
- Added `store=false` to manuscript requests.
- Prevented failed paid revisions from returning the original manuscript as completed work.
- Added retryable 503 responses with entitlement rollback.
- Added Semantic Scholar API-key support and 429 cooldown.
- Added trusted hosts, restricted CORS, rate limits, request limits and security headers.
- Added favicon, robots, sitemap and security contact files.

## 2.0.0, review evidence and article workflow

- Added the Review Evidence Workspace.
- Added full synthesis-article workflows.
- Added DOCX export for topic ideas and article revisions.
- Added the ThesisReady-derived preservation-gated scholarly humanizer.
- Increased citation-density guidance and scholarly source context.
