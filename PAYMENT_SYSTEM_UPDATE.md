# ArticleReady AI Payment System Update

This update adds a ProjectReady-style payment and entitlement system to ArticleReady AI.

## Provider routing

- African billing countries route to Paystack.
- All other billing countries route to Stripe Checkout.
- Routing is based on the customer-selected billing country, not IP location.

## Plans

| Plan key | Public plan | Price | Included actions |
|---|---|---:|---|
| `article_ideas` | Article Ideas | US$2.99 | 1 idea run, up to 20 ideas |
| `stage1_article` | Stage 1 Article Builder | US$6.99 | 1 draft and 1 DOCX export |
| `standard_full_article` | Standard Full Article | US$14.99 | 1 draft, 1 revision entitlement and 1 DOCX export |
| `long_article_plus` | Long Article Plus | US$19.99 | 1 long/batch draft, 1 revision entitlement and 1 DOCX export |
| `review_conceptual_scoping` | Review / Conceptual / Scoping Article | US$24.99 | 1 source-heavy draft, 1 revision entitlement and 1 DOCX export |
| `article_revision` | Article Polishing and Revision | US$7.99 | 1 revision and 1 DOCX export |
| `reviewer_comment_revision` | Reviewer Comment Revision | US$9.99 | 1 reviewer-comment revision and 1 DOCX export |
| `extra_revision_pass` | Extra Revision Pass | US$4.99 | 1 extra revision and 1 DOCX export |

## Main routes added

- `GET /api/payments/plans`
- `POST /api/payments/checkout`
- `POST /api/payments/entitlement-status`
- `POST /api/payments/redeem-handoff`
- `POST /api/payments/recover-access`
- `GET /payment/paystack/callback`
- `POST /payment/paystack/webhook`
- `GET /payment/stripe/success`
- `POST /payment/stripe/webhook`

## Entitlement enforcement

The following routes now require paid access unless `ARTICLEREADY_PAYMENT_REQUIRED=0`:

- `POST /api/article-ideas`, except the free trial of 3 ideas without source search
- `POST /api/articles/draft`
- `POST /api/articles/export`
- `POST /api/articles/revise`
- `POST /api/articles/revision/export`

Paid access is passed through headers:

```text
x-articleready-purchase-id: <purchase_id>
x-articleready-access-token: <access_token>
```

The browser stores the opaque access credential in local storage after a successful one-time handoff. The server stores only its hash, and the credential is rotated whenever payment access is restored.

## Required production environment variables

```text
ARTICLEREADY_PAYMENT_REQUIRED=1
APP_BASE_URL=https://articlereadyai.com
ARTICLEREADY_SQLITE_DB_PATH=/var/data/articleready_payments.db
PAYSTACK_SECRET_KEY=sk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Optional fixed GHS prices may be set per plan. If they are not set, the app converts the USD plan price with `ARTICLEREADY_PAYSTACK_USD_TO_GHS_RATE`.


## Payment return and recovery

Successful provider callbacks create a short-lived, single-use handoff. The browser redeems the handoff, rotates the access token and stores the new credential. This avoids losing paid access when local storage is cleared or isolated during checkout. Customers can also use `/payment/recover` with their payment email and Purchase ID.
