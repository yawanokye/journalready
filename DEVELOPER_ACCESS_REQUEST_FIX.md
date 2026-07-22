# Developer Access Request Fix

This update repairs the developer-access page and ensures every paid ArticleReady AI request carries the active developer token.

## Changes

- Six-digit developer code validation is enforced consistently in HTML, JavaScript and FastAPI.
- Removed accidental Markdown fences from the developer-access HTML and JavaScript files.
- Added `ArticleReadyPayments.authorisedFetch()` to attach developer and paid-access headers consistently.
- Article Ideas, Article Writer, Article Revision and their DOCX export calls now use the shared authorised request helper.
- Payment JavaScript loads before each page-specific script.
- Static asset versions were changed to avoid stale browser files.
- Added regression tests for six-digit login, clean assets and developer-token request wiring.
