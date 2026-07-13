# ArticleReady AI GPT-5.6, Humaniser and Payment Update

## Model routing

All OpenAI-backed workflows now use only:

- `gpt-5.6-terra` for standard drafting, cost-balanced work and the optional scholarly-humaniser model pass.
- `gpt-5.6-sol` for research-master's and doctoral depth, review/conceptual/systematic articles, long or batch articles, Stage 2 article completion and article revision.

Legacy GPT-5.4 and GPT-5.5 values are normalised away at runtime. Article Topic Ideas remains on DeepSeek V4 Pro.

## Scholarly humaniser

The ThesisReady `scholarly_humanizer.py` layer is now shared by Article Writer and Article Revision. It includes:

- deterministic academic-style diagnostics and local refinement;
- section-aware batching;
- optional GPT-5.6 Terra naturalisation;
- preservation checks for headings, citations, numbers, equations, tables, URLs, references and bracketed author actions;
- automatic rejection of a humanised candidate that changes evidence or exceeds the configured word-change threshold.

## Payment system

The ProjectReady-style payment and entitlement system is included with Paystack for African billing countries and Stripe elsewhere. It protects idea generation, article drafting, article revision and DOCX export according to the selected plan.

Payment continuity now includes:

- a short-lived, single-use handoff after a successful provider callback;
- automatic browser credential restoration and token rotation;
- `POST /api/payments/redeem-handoff`;
- self-service access restoration at `/payment/recover`;
- `POST /api/payments/recover-access` using the payment email and Purchase ID;
- direct provider re-verification when a callback was interrupted.

## Deployment

Copy the environment values from `.env.example`, especially:

```text
OPENAI_ARTICLE_TERRA_MODEL=gpt-5.6-terra
OPENAI_ARTICLE_SOL_MODEL=gpt-5.6-sol
OPENAI_ARTICLE_REVISION_MODEL=gpt-5.6-sol
OPENAI_ARTICLE_HUMANIZER_MODEL=gpt-5.6-terra
ARTICLEREADY_HUMANIZER_MODE=balanced
ARTICLEREADY_HUMANIZER_MODEL_PASS=1
ARTICLEREADY_PAYMENT_REQUIRED=1
APP_BASE_URL=https://articlereadyai.com
```

Configure `PAYSTACK_SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `OPENAI_API_KEY` and `DEEPSEEK_API_KEY` as secret Render variables. Use a persistent Render disk for `/var/data` or supply `DATABASE_URL` for PostgreSQL so entitlements survive redeployments.
