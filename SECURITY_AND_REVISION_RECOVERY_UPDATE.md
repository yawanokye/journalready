# ArticleReady AI 2.1 Security and Revision Recovery Update

## Revision reliability

- Added the missing OpenAI SDK dependency.
- Removed hard restriction to account-specific Terra/Sol labels.
- Model routing now accepts operator-configured model IDs and tries a configured fallback chain.
- Added bounded retry with exponential backoff for transient OpenAI failures.
- Added a final Chat Completions recovery route when the Responses endpoint fails.
- OpenAI requests now set `store=false` for manuscript privacy.
- A failed paid revision now raises a retryable 503 response and rolls back the entitlement claim.
- The original manuscript is no longer returned as a completed revision unless the operator explicitly enables `ARTICLEREADY_ALLOW_REVISION_FALLBACK=1`.

## Scholarly-source resilience

- Semantic Scholar requests can use `SEMANTIC_SCHOLAR_API_KEY`.
- Metadata calls now respect bounded retry and provider cooldown after HTTP 429.
- One unavailable metadata provider no longer determines whether the revision model can run.

## Web security

- Restricted CORS to explicitly configured origins.
- Added trusted-host validation.
- Added route-specific rate limiting and request-size limits.
- Added CSP, HSTS, clickjacking, MIME-sniffing, referrer, permissions and cross-origin isolation headers.
- Disabled public API documentation by default.
- Added no-store handling for API and private workspace responses.
- Added `robots.txt`, `sitemap.xml`, favicon and `security.txt` routes.
- Added `noindex` to developer access, paid-access recovery and Review Evidence Workspace pages.

## Deployment

Deploy with a persistent disk mounted at `/var/data`. Set the OpenAI model variables to model IDs actually available to the OpenAI project. Keep `ARTICLEREADY_ALLOW_REVISION_FALLBACK=0` in production.
