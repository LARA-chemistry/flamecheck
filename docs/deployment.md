(deployment)=

# Deployment (DevOps)

This chapter covers running FlameCheck as a service: the Docker deployment
options, production environment configuration, backups, scaling, and how to
place the stack behind a **load-balancer or TLS-terminating reverse proxy**
(Nginx / Caddy). Getting the stack running itself is covered in
{ref}`Installation <installation>`.

## The Docker deployment options

| Variant | Compose file | Image | Database | Demo data | When to use |
|---------|--------------|-------|----------|-----------|-------------|
| Production | `docker-compose.yaml` | built from `docker/Dockerfile` | SQLite volume (default) | none | the real lab system |
| Production + Postgres | `docker-compose.yaml --profile postgres` | same | `postgres:16-alpine` container | none | several courses / higher load |
| Staging | `docker-compose-staging.yaml` | pre-built registry image | SQLite volume | seeded on boot (`SEED_DEMO`) | demos, acceptance testing |
| Development | `docker-compose-dev.yaml` | built, dev settings | SQLite | none | containerised dev work |
| Dev full stack | `docker/docker-compose.dev-full.yaml` | built, dev settings | Postgres (published :5432) | none | developing against Postgres |

The production image is a multi-stage build: the Vue app is compiled in a Node
stage, the Python project is installed with `uv` (editable workspace layout
under `/opt`), and the final stage is a slim `python:3.13-slim` with the
virtualenv, the source, `gnupg` (for the PGP e-mails) and a **non-root**
`appuser`. The entrypoint (`docker/entrypoint.production.sh`) runs
`migrate` → `check_migrations` (self-heals a crashed migration state) →
optional `seed_demo` (staging only) → `collectstatic` → Gunicorn on port 8000
(`GUNICORN_WORKERS`, default 3).

## Production environment configuration

Everything is read from a `.env` file (`django-environ`); every variable has a
safe default documented in `.env-template`. The ones you **must** set for
production:

| Variable | Why |
|----------|-----|
| `DJANGO_SECRET_KEY` | long, random; signs sessions, the e-mail-confirmation tokens and (by default) the JWTs |
| `DJANGO_ALLOWED_HOSTS` | the public hostname(s) the server responds to (comma-separated) |
| `ENV=production` | selects the production defaults (DEBUG off) |

Recommended:

| Variable | Guidance |
|----------|----------|
| `DJANGO_CSRF_TRUSTED_ORIGINS` | only needed for cross-origin API calls (same-origin SPA needs none) |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` when the proxy handles HTTP→HTTPS (see below) |
| `DJANGO_SECURE_HSTS_SECONDS` | default 1 year; keep |
| `DATABASE_URL` | leave unset for SQLite, or `postgres://user:pw@db:5432/flamecheck` |
| `JWT_SIGNING_KEY` | optionally independent of the secret key (for rotation) |
| `SOCIALACCOUNT_PROVIDERS` | the OAuth/Keycloak configuration (see {ref}`Registration & authentication <registration>`) |
| `ALLOW_EMAILS` | `true` only on instances that may send the submission e-mails; leave unset/false everywhere else (staging, demo) |
| `SEED_DEMO` | keep **unset** in production (never seed demo data into a live DB) |
| `GUNICORN_WORKERS` | 2–4 for a typical lab; Gunicorn does the blocking (SQLite lock) work, so more workers do not help SQLite |

## Database in production

**SQLite (default).** The database file lives in the `flamecheck_db` named
volume (`/opt/db/db.sqlite3`). Because the file is in a volume, container
rebuilds are safe. Concurrency is single-writer — fine for a lab where
submissions arrive one at a time during a window. Backups use the built-in
feature (below).

**PostgreSQL (opt-in).** Activate the `postgres` profile, set
`DATABASE_URL=postgres://flamecheck:flamecheck@db:5432/flamecheck`, and the
app waits for the healthy database before starting. Use it for multiple
courses in parallel, larger student bodies, or when you want point-in-time
recovery. Backups are then `pg_dump` (or your DBA's tooling) against the
`db_data` volume — the in-app backup feature is SQLite-only by design.

## Backups

- **SQLite (built-in):** Admin → **Settings → Database** — enable the
  scheduler (`backup_enabled`), choose interval, location and how many backups
  to keep. Backups are consistent snapshots taken with SQLite's online backup
  API (safe against live writers); restore swaps the file atomically and
  reloads the connections. Backup files are named `flamecheck-YYYYMMDD-HHMMSS.sqlite3`.
  Note: with the default in-process scheduler the backups run *inside the app
  process*; for extra safety, also snapshot the `flamecheck_db` volume.
- **PostgreSQL:** `pg_dump -Fc` on a schedule (cron / the database container's
  `docker exec`), or volume-level snapshots. Test your restore!

## Scaling & load

- The app is **stateless for the API** (JWT bearer tokens, no server session)
  — the only state is the database, the static files volume and the media
  volume. You can therefore run multiple app containers behind a load
  balancer as long as they share the database and the media/static volumes.
- The OAuth callback uses a short-lived Django session (database-backed by
  default), which also works across containers with a shared database.
- With **SQLite**, keep a **single** app instance: SQLite serialises writes,
  and parallel Gunicorn workers across containers will hit lock timeouts under
  concurrent submissions. Move to PostgreSQL before scaling horizontally.
- Static files are served by WhiteNoise from the `flamecheck_static` volume;
  the reverse proxy can also serve them directly if you prefer (see below).

## Behind a load-balancer / reverse proxy with TLS

FlameCheck speaks plain HTTP on port 8000 and is designed to run behind a
TLS-terminating proxy. The production settings already assume one:

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` — Django
  trusts the proxy's `X-Forwarded-Proto` header for HTTPS detection,
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` — cookies are only sent over
  HTTPS,
- HSTS is enabled by default.

### Nginx (manual certificates or ACME)

```nginx
upstream flamecheck {
    server 127.0.0.1:8000;   # or the container: `server flamecheck:8000;` in the same network
}

server {
    listen 80;
    server_name flamecheck.example.org;
    return 301 https://$host$request_uri;      # or rely on DJANGO_SECURE_SSL_REDIRECT
}

server {
    listen 443 ssl;
    http2 on;
    server_name flamecheck.example.org;

    ssl_certificate     /etc/letsencrypt/live/flamecheck.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/flamecheck.example.org/privkey.pem;

    # Proxy headers Django needs (SECURE_PROXY_SSL_HEADER + client IPs).
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Long-enough timeouts for the (rarely slow) Gunicorn requests.
    proxy_read_timeout 60s;

    location / {
        proxy_pass http://flamecheck;
        proxy_redirect off;
    }

    # Optional: serve the built frontend + static files directly (they are
    # immutable, fingerprinted assets) to keep the app containers busy only
    # with API + dynamic routes:
    # location /static/ { alias /var/www/flamecheck/staticfiles/; expires 1y; }
}
```

Set `DJANGO_ALLOWED_HOSTS=flamecheck.example.org` and
`DJANGO_SECURE_SSL_REDIRECT=true` in `.env` so Django itself redirects the
stray plain-HTTP requests and validates the `Host` header.

### Caddy (automatic Let's Encrypt)

```
flamecheck.example.org {
    reverse_proxy / 127.0.0.1:8000 {
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Caddy obtains and renews the TLS certificate automatically and sets the
forwarded headers for you.

### Load-balancer specifics

- **Health check:** there is no dedicated `/health` endpoint; use a TCP check
  on port 8000, or an HTTP check against `/` (it returns the SPA shell with
  HTTP 200 and needs no authentication).
- **Sticky sessions:** not required — API state is in the JWTs. The only
  session is the few-second OAuth callback exchange, which completes on the
  container that received it.
- **TLS termination:** do it at the proxy (as above), *not* inside the
  container — the image does not ship TLS tooling, and the proxy is where
  certificates and HSTS belong.
- **Multiple instances:** with PostgreSQL, put as many app containers as you
  need behind the balancer (shared `db`, `flamecheck_static`, `flamecheck_media`
  volumes or object storage). Keep the `X-Forwarded-For` chain intact if you
  nest proxies — the login rate limiting keys on the client IP.

## Security checklist

- [ ] `DJANGO_SECRET_KEY` (and `JWT_SIGNING_KEY`) long, random, unique per instance
- [ ] `DJANGO_ALLOWED_HOSTS` set to the real hostnames (no wildcards)
- [ ] TLS at the proxy; HSTS enabled; HTTP → HTTPS redirect
- [ ] `ALLOW_EMAILS` unset (or `false`) on any staging/demo instance
- [ ] `SEED_DEMO` unset in production
- [ ] Container runs as the non-root `appuser` (image default — don't `--user root`)
- [ ] Volumes (`flamecheck_db`, `db_data`, media) backed up **and restore-tested**
- [ ] Regular image rebuilds (the base images get security updates)
- [ ] Rate limiting is on by default (5 logins / 10 barcode scans per minute);
      `LOGIN_MAX_ATTEMPTS` for lockout

## See also

- {ref}`Installation <installation>` — every compose variant, step by step.
- {ref}`Registration & authentication <registration>` — OAuth/Keycloak for SSO deployments.
- [Architecture, §9 Settings & environments](development/architecture.md#9-settings--environments) —
  the full settings module hierarchy.
