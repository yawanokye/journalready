# Payment access and structured error fix

Version 1.6.1 corrects the browser message `Error: [object Object]`.

Changes:
- Structured FastAPI and Pydantic errors are converted into readable messages.
- Checkout, payment return, idea generation, article drafting, revision, file extraction and export use the same safe error formatting.
- Static JavaScript version identifiers were changed so browsers cannot reuse the older cached payment script.
- HTML and JavaScript responses use no-cache headers for payment-sensitive pages.
- Payment-required API objects continue to open the correct package checkout instead of being printed as an object.

After deployment, use **Clear build cache and deploy**, then hard-refresh the browser once.
