(authentication)=

# Authentication

FlameCheck is a single-page app (Vue 3) on top of a Django REST API
(django-ninja). All API traffic is authenticated with **JWT bearer tokens**
(stateless, HS256-signed): a short-lived *access* token plus a longer-lived
*refresh* token. There are several ways to *obtain* those tokens, and the way
student accounts are created in the first place is controlled by a single
**registration mode** setting.

## Roles

| Role      | Sign-in methods                                          |
|-----------|----------------------------------------------------------|
| Student   | Username/password, personal barcode, or OAuth (Keycloak) |
| Assistant | Username/password                                        |
| Admin     | Username/password                                        |

Assistants and admins always sign in with a username and password. Students may
use any of the three methods below — which ones are actually offered depends on
the registration mode of the deployment.

## Authentication methods

### 1. Username / password (default)

Every role signs in with a username and password on the login page
(`POST /api/v1/auth/login`). The response carries the token pair, the user
profile, and — for students — the list of assigned analyses with their current
window state.

- Rate-limited to **5 attempts per minute** per username + IP address.
- Every attempt (success or failure) is recorded in `LoginAttempt` for auditing.
- Inactive accounts are rejected with `403 — Account is disabled.`.

### 2. Barcode scan (students)

A student can also sign in by scanning their personal barcode (Code128 or QR)
via `POST /api/v1/auth/barcode/scan`. The barcode payload (e.g.
`FC-<user_id>-<uuid8>`) is resolved server-side; an unknown or inactive barcode
returns a generic `401`, so the endpoint never reveals whether a given barcode
exists.

- Rate-limited to **10 scans per minute** per IP.
- Barcodes are created with `uv run python manage.py init_barcode <username>`
  (`--reset` regenerates an existing one). They are shown per student in the
  assistant roster and in the course member list.

### 3. Self-registration (students)

When the registration mode is **self-registration**, the login page shows a
"Register" link. A student registers with `POST /api/v1/auth/register` (first
and last name, e-mail, password and optional metadata). This creates an
*inactive* student account and sends a confirmation e-mail (printed to the
console in development).

- Opening the confirmation link (`/accounts/verify-email/<token>/`) verifies the
  signed, timestamped token and activates the account — no extra database table
  is required.
- After confirming, the student signs in with their username and password.
- Expired or invalid links are sent back to the login page with an error flag.

### 4. OAuth / OpenID Connect (Keycloak)

When the registration mode is **OAuth**, students sign in through an external
identity provider. The shipped example is
[Keycloak](https://www.keycloak.org), integrated through django-allauth's
generic OpenID Connect provider.

1. The login page shows a "Continue with *Provider*" button for every
   configured provider.
2. The button redirects to the provider; after a successful sign-in the browser
   returns to `/oidc/<provider>/login/callback/` with a Django session set.
3. `POST /api/v1/auth/oauth/exchange` swaps that session for a JWT pair (the SPA
   is token-based, not session-based).
4. A brand-new OAuth student starts **unregistered**: they are confined to the
   registration page, where they pick a course, supply any metadata the provider
   did not send, and their course analyses are generated for them.

Providers are configured in the `SOCIALACCOUNT_PROVIDERS` environment variable
(see the Configuration section below). The realm's valid redirect URI is
`https://<host>/oidc/<provider>/login/callback/`.

## Token lifecycle

| Token    | Default lifetime | Environment variable                      |
|----------|------------------|-------------------------------------------|
| Access   | 30 minutes       | `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`       |
| Refresh  | 14 days          | `JWT_REFRESH_TOKEN_LIFETIME_DAYS`         |

- `POST /api/v1/auth/token/refresh` rotates a refresh token into a fresh pair.
- `POST /api/v1/auth/logout` bumps the user's `token_version`, which revokes
  **every** access and refresh token issued earlier (the version is checked on
  each request).
- Each token carries `sub` (user id), `jti`, `type`, `role`, `iat`, `exp`,
  `aud`, `iss` and `tv` (token version), and is signed with `JWT_SIGNING_KEY`
  (HS256).

## Registration mode

The singleton `AppSettings.registration` field decides **how student accounts
are created**. Exactly one mode is active at a time; it is changed in the admin
**Settings → Registration** card (or in the Django admin). It never affects
assistants or admins, who always use password login.

| Mode                | Student accounts are created by                                     |
|---------------------|---------------------------------------------------------------------|
| `manual` (default)  | An admin creates them (admin **Courses → Members**).                |
| `self_registration` | Students register themselves and confirm their e-mail.              |
| `oauth`             | Students sign in via the external identity provider, then complete the registration page. |

The login page reads the active mode and the offered OAuth providers from the
public `GET /api/v1/registration/config` endpoint, so it automatically shows the
right controls (the password form, the "Register" link, and/or the OAuth
buttons) without any frontend change.

## Configuration

All of the above is driven by environment variables (see the `.env-template` in
the repository root):

| Variable                             | Meaning                                    | Default              |
|--------------------------------------|--------------------------------------------|----------------------|
| `JWT_SIGNING_KEY`                    | HS256 signing key for the JWTs             | the `SECRET_KEY`     |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`  | Access-token lifetime (minutes)            | `30`                 |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS`    | Refresh-token lifetime (days)              | `14`                 |
| `JWT_AUDIENCE` / `JWT_ISSUER`        | the `aud` / `iss` token claims             | `flamecheck-api` / `flamecheck` |
| `SOCIALACCOUNT_PROVIDERS`            | OAuth / OIDC providers (JSON, see below)   | `{}`                 |

`SOCIALACCOUNT_PROVIDERS` is a JSON object. For a single Keycloak realm:

```json
{
  "openid_connect": {
    "APPS": [
      {
        "provider_id": "keycloak",
        "name": "Keycloak",
        "client_id": "flamecheck",
        "secret": "<realm client secret>",
        "settings": { "server_url": "https://keycloak.example.com/realms/flamecheck" }
      }
    ]
  }
}
```

`provider_id` is what the login button and the `/oidc/<provider_id>/login/` URLs
use, so a realm configured this way appears on the login page as a
"Continue with Keycloak" button.

## Security

- **Stateless JWTs** — there is no server-side session; revocation works through
  the per-user `token_version` counter.
- **Rate limiting** — 5 logins / 10 barcode scans per minute (per
  username + IP / per IP).
- **Audit** — every password login attempt is stored in `LoginAttempt` with the
  client IP.
- **Opaque barcode errors** — an unknown barcode is indistinguishable from an
  inactive one, so the endpoint cannot be used to probe for valid barcodes.
- **OAuth** — the sign-in itself is delegated to django-allauth and the identity
  provider; the application only exchanges the resulting session for its own
  JWTs.

## See also

- {ref}`Usage <usage>` — the day-to-day workflows for each role, including how a
  student submits an analysis.
- {ref}`Installation <installation>` — creating the initial admin user and
  loading the demo accounts.
