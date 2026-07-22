# V-Professor 2.6.1

## Administrator credential recovery

The administrator account is stored in PostgreSQL. `ADMIN_PASSWORD` is used to create the first administrator and is not reapplied during ordinary restarts. Changing the environment value therefore does not change the password hash already stored in the database.

This release adds a controlled one-time reset:

```env
VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP=true
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<new-strong-password>
```

Redeploy the web service, confirm the startup log says the administrator credential was reset, sign in, then immediately change `VPROF_RESET_ADMIN_PASSWORD_ON_STARTUP` back to `false` and redeploy.

A trusted Render Shell may instead run:

```bash
python scripts/reset_admin_password.py
```

The command reads the password from the environment and never prints it.

## Security corrections

- A password supplied through `ADMIN_PASSWORD` is no longer returned to the startup logger when the first administrator is created.
- Ordinary restarts never overwrite an administrator password selected in the portal.
- The one-time reset must be explicitly enabled.
- The reset may safely synchronise `ADMIN_USERNAME` with the stored administrator account when no username conflict exists.
- The administrator account is reactivated during an explicit reset.

## Validation

- 364 automated tests passed.
- Python compilation passed.
- Administrator reset, non-overwrite and username-sync tests passed.
