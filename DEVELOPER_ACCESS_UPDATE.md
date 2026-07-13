# Developer Access Update

ArticleReady AI now supports secure developer access for internal testing.

- Disabled by default
- Optional email restriction
- Plain-code or SHA-256 code verification
- HMAC-signed, expiring browser session
- Five failed attempts per IP within 15 minutes before temporary lockout
- Bypasses payment and entitlement consumption for ideas, drafting, revision and export
- Direct page: `/developer-access`
- No developer secret is shipped in frontend files
