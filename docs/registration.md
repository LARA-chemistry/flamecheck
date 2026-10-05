(registration)=

# Registration & authentication

FlameCheck is a single-page app (Vue 3) on top of a Django REST API
(django-ninja). All API traffic is authenticated with **JWT bearer tokens**
(stateless, HS256-signed): a short-lived *access* token plus a longer-lived
*refresh* token.

There are two separate questions this page answers:

1. **How are accounts created in the first place?** — student accounts follow
   a single, switchable *registration mode*; assistants and admins are always
   created by an admin.
2. **How do people sign in?** — username/password, personal barcode,
   self-registration with e-mail confirmation, or OAuth / OpenID Connect
   (e.g. Keycloak).

## Roles

| Role | Accounts are created by | Sign-in methods |
|------|-------------------------|-----------------|
| Student | the active **registration mode** (manual / self-registration / OAuth) | password, barcode, or OAuth |
| Assistant | an admin (Admin → Courses → Members) | password |
| Admin | an admin / superuser | password |

Assistants and admins always sign in with a username and password. Students
may use any of the sign-in methods below — which ones are actually offered
depends on the registration mode of the deployment.

## How accounts are created

### Students — the registration mode

The singleton `AppSettings.registration` field decides **how student accounts
are created**. Exactly one mode is active at a time; it is changed in the
admin **Settings → Registration** card (or in the Django admin). It never
affects assistants or admins, who always use password login.

| Mode | Student accounts are created by |
|------|---------------------------------|
| `manual` (default) | An admin creates them (admin **Courses → Members**), optionally with an auto-generated password and a barcode. |
| `self_registration` | Students register themselves on the login page and confirm their e-mail. |
| `oauth` | Students sign in via the external identity provider, then complete a short registration page. |

The login page reads the active mode and the offered OAuth providers from the
public `GET /api/v1/registration/config` endpoint, so it automatically shows
the right controls (the password form, the "Register" link, and/or the OAuth
buttons) without any frontend change.

### Members (assistants & admins)

Assistants and admins are **never** self-registered:

- **Assistants** are created in the admin's **Courses → Members** view: the
  admin picks the course, chooses "assistant", supplies a username (the
  account is created with an auto-generated password that is shown once) and
  optionally a first/last name, e-mail and `labspace_id`. The assistant then
  sees exactly the courses they were linked to.
- **Admins** are users with the `admin` role. The bootstrap admin is created
  with `manage.py init_admin` (see {ref}`Installation <installation>`); further
  admins are promoted by setting the user's `role` (Django admin or shell).

Both roles sign in with username/password like every other account, and both
can change their password after the first login.

## Sign-in methods

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
  (`--reset` regenerates an existing one) or in the admin's course member
  list. They are shown per student in the assistant roster and in the course
  member list (a webcam via ZXing or a USB keyboard-wedge scanner both work).

### 3. Self-registration (students)

When the registration mode is **self-registration**, the login page shows a
"Register" link. A student registers with `POST /api/v1/auth/register` (first
and last name, e-mail, password and optional metadata). This creates an
*inactive* student account and sends a confirmation e-mail (printed to the
console in development).

- Opening the confirmation link (`/accounts/verify-email/<token>/`) verifies
  the signed, timestamped token and activates the account — no extra database
  table is required.
- After confirming, the student signs in with their username and password.
- Expired or invalid links are sent back to the login page with an error flag.

> The confirmation e-mail uses Django's e-mail backends: the console backend in
> development, and whatever SMTP backend you configure for production. It is
> *not* part of the PGP submission-confirmation feature.

### 4. OAuth / OpenID Connect (Keycloak)

When the registration mode is **OAuth**, students sign in through an external
identity provider. The shipped example is
[Keycloak](https://www.keycloak.org), integrated through django-allauth's
generic OpenID Connect provider.

1. The login page shows a "Continue with *Provider*" button for every
   configured provider.
2. The button redirects to the provider; after a successful sign-in the
   browser returns to `/oidc/<provider>/login/callback/` with a Django session
   set.
3. `POST /api/v1/auth/oauth/exchange` swaps that session for a JWT pair (the
   SPA is token-based, not session-based).
4. A brand-new OAuth student starts **unregistered**: they are confined to the
   registration page, where they pick a **course**, supply any metadata the
   provider did not send (first/last name, e-mail, …), and their course
   analyses are generated for them. Returning students skip straight to the
   app.

Providers are configured in the `SOCIALACCOUNT_PROVIDERS` environment variable
(see [Configuration](#configuration) below). The realm's valid redirect URI is
`https://<host>/oidc/<provider>/login/callback/`.

```{mermaid}
sequenceDiagram
    participant B as Student (browser)
    participant F as FlameCheck
    participant K as Keycloak (IdP)
    B->>F: click "Continue with Keycloak"
    F->>K: redirect to /realms/flamecheck/protocol/openid-connect/auth
    K->>B: sign-in form (SSO)
    B->>K: credentials / SSO session
    K->>F: redirect to /oidc/keycloak/login/callback/?code=…
    F->>K: token exchange (client_id + secret)
    K-->>F: ID token + profile claims
    F->>F: create/look up user, set Django session
    F-->>B: 302 to SPA callback (session cookie)
    B->>F: POST /api/v1/auth/oauth/exchange
    F-->>B: JWT access + refresh tokens
    Note over B,F: new student → registration page (course + metadata)
```

## Token lifecycle

| Token | Default lifetime | Environment variable |
|-------|------------------|----------------------|
| Access | 30 minutes | `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` |
| Refresh | 14 days | `JWT_REFRESH_TOKEN_LIFETIME_DAYS` |

- `POST /api/v1/auth/token/refresh` rotates a refresh token into a fresh pair.
- `POST /api/v1/auth/logout` bumps the user's `token_version`, which revokes
  **every** access and refresh token issued earlier (the version is checked on
  each request).
- Each token carries `sub` (user id), `jti`, `type`, `role`, `iat`, `exp`,
  `aud`, `iss` and `tv` (token version), and is signed with `JWT_SIGNING_KEY`
  (HS256).

## Configuration

All of the above is driven by environment variables (see the
`.env-template` in the repository root):

| Variable | Meaning | Default |
|----------|---------|---------|
| `JWT_SIGNING_KEY` | HS256 signing key for the JWTs | the `SECRET_KEY` |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Access-token lifetime (minutes) | `30` |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Refresh-token lifetime (days) | `14` |
| `JWT_AUDIENCE` / `JWT_ISSUER` | the `aud` / `iss` token claims | `flamecheck-api` / `flamecheck` |
| `SOCIALACCOUNT_PROVIDERS` | OAuth / OIDC providers (JSON, see below) | `{}` |
| `LOGIN_MAX_ATTEMPTS` | failed logins before a username is locked | `5` |

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

`provider_id` is what the login button and the `/oidc/<provider_id>/login/`
URLs use, so a realm configured this way appears on the login page as a
"Continue with Keycloak" button. Several providers/realm can be listed in
`APPS` (each gets its own button).

**Keycloak setup in a nutshell:**

1. In Keycloak: create a realm and a *confidential* client (e.g. "flamecheck"),
   enable the OpenID Connect protocol, and set the **valid redirect URI** to
   `https://<your-host>/oidc/keycloak/login/callback/`.
2. Copy the client id + secret into `SOCIALACCOUNT_PROVIDERS` (above) and set
   `server_url` to the realm's issuer URL
   (`https://keycloak.example.com/realms/flamecheck`).
3. Switch the registration mode to **OAuth** (Admin → Settings →
   Registration). The login page now offers the provider button; existing
   password logins keep working for assistants/admins.

## Security

- **Stateless JWTs** — there is no server-side session for the API; revocation
  works through the per-user `token_version` counter. (The OAuth callback
  itself uses a short-lived Django session that is exchanged for JWTs.)
- **Rate limiting** — 5 logins / 10 barcode scans per minute (per
  username + IP / per IP); on top of that, `LOGIN_MAX_ATTEMPTS` adds a
  persistent, IP-independent lockout after repeated failures (for
  `LOGIN_LOCKOUT_SECONDS`) that a successful login resets, so rotating source
  addresses cannot keep an account unlocked. Behind a reverse proxy the
  rate limits key on the *last* `X-Forwarded-For` entry (the one the trusted
  proxy appended), not on the client-forged first one.
- **Audit** — every password login attempt is stored in `LoginAttempt` with
  the client IP.
- **Opaque barcode errors** — an unknown barcode is indistinguishable from an
  inactive one, so the endpoint cannot be used to probe for valid barcodes.
- **OAuth** — the sign-in itself is delegated to django-allauth and the
  identity provider; the application only exchanges the resulting session for
  its own JWTs, so the client secret never reaches the browser.

## See also

- {ref}`Usage <usage>` — the day-to-day workflows for each role.
- {ref}`Installation <installation>` — creating the initial admin user and
  loading the demo accounts.
- [Architecture, §5 Authentication & authorisation](development/architecture.md#5-authentication--authorisation) —
  JWT design and role-based authorisation in depth.
