# Restricted Developer Access

ArticleReady AI includes a private, signed developer session that unlocks all paid actions without creating a purchase or consuming a customer entitlement.

## Render configuration

Set the following environment variables:

```text
ARTICLEREADY_DEVELOPER_ACCESS_ENABLED=1
ARTICLEREADY_DEVELOPER_ACCESS_EMAIL=aadam@ucc.edu.gh
ARTICLEREADY_DEVELOPER_ACCESS_CODE_SHA256=<SHA-256 hash of the private access code>
ARTICLEREADY_DEVELOPER_ACCESS_SECRET=<a separate long random signing secret>
ARTICLEREADY_DEVELOPER_SESSION_HOURS=12
```

Generate the access-code hash locally:

```bash
python -c "import hashlib; print(hashlib.sha256(b'YOUR-PRIVATE-CODE').hexdigest())"
```

Generate a signing secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For simpler setup, `ARTICLEREADY_DEVELOPER_ACCESS_CODE` can contain the plain private code instead of the SHA-256 variable. The hash option is preferred.

## Use

Open:

```text
https://articlereadyai.com/developer-access
```

Enter the configured email and the original private code. The browser receives an HMAC-signed, expiring token. The token is automatically attached to Article Ideas, Article Writer, Article Revision and DOCX export requests.

The developer page is excluded from search indexing and is not linked in the public navigation. Five failed login attempts from the same IP within 15 minutes trigger a temporary lockout.

## End access

Use **End session** on the developer-access page, clear site storage, or wait for the configured expiry. Disable the feature in Render by setting:

```text
ARTICLEREADY_DEVELOPER_ACCESS_ENABLED=0
```
