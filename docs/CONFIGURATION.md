# Configuration Reference

All configuration is done via environment variables, typically in a `.env` file at the project root.  
Copy `.env.example` to `.env` and fill in the required values before starting the stack.

---

## Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTGRES_USER` | No | `nextfolio` | PostgreSQL username |
| `POSTGRES_PASSWORD` | **Yes** | — | PostgreSQL password. Generate with: `openssl rand -hex 16` |
| `POSTGRES_DB` | No | `nextfolio` | PostgreSQL database name |

---

## Redis

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_PASSWORD` | **Yes** | — | Redis AUTH password. Generate with: `openssl rand -hex 16` |

---

## Security

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | Master key for JWT signing. Generate with: `openssl rand -hex 32` |
| `ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime in days (standard login) |
| `REFRESH_TOKEN_REMEMBER_ME_DAYS` | No | `30` | Refresh token lifetime when "Remember Me" is checked |

---

## Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_ENV` | No | `production` | Runtime environment. `development` enables API docs and debug logging |
| `DEBUG` | No | `false` | Set to `true` to enable verbose logging and FastAPI `/docs` endpoint |
| `APP_URL` | **Yes** | — | Public URL of the app (e.g. `https://nextfolio.example.com`). Used in password-reset and email verification links |
| `CORS_ORIGINS` | **Yes** | — | Comma-separated list of allowed CORS origins (e.g. `https://nextfolio.example.com`) |
| `ALLOWED_HOSTS` | No | `*` | Comma-separated list of trusted `Host` header values. Set to your domain to block host-header injection. Use `*` to disable the check |

---

## Deployment Modes

### Mode A — Cloudflare Tunnel

| Variable | Required | Description |
|---|---|---|
| `CLOUDFLARE_TUNNEL_TOKEN` | **Yes (mode A)** | Token from the Cloudflare Zero Trust dashboard. Start with: `COMPOSE_PROFILES=cloudflare docker compose up -d` |

### Mode B — HTTPS / Let's Encrypt

No additional variables required. Follow the steps in [DEPLOYMENT.md](DEPLOYMENT.md#3-production--https-with-lets-encrypt).

---

## Market Data APIs

| Variable | Required | Description |
|---|---|---|
| `COINGECKO_API_KEY` | No | CoinGecko API key. Without it, the free (rate-limited) tier is used. Get one at [coingecko.com/api](https://www.coingecko.com/en/api) |
| `OPENFIGI_APY_KEY` | No | OpenFIGI API key for higher rate limits on ISIN lookups. Get one at [openfigi.com](https://www.openfigi.com/api) |

---

## Email (SMTP)

Required for password-reset emails and email verification. If not configured, those flows are disabled.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SMTP_HOST` | No | — | SMTP server hostname (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | No | `587` | SMTP port (587 for STARTTLS, 465 for SSL) |
| `SMTP_USER` | No | — | SMTP username / email address |
| `SMTP_PASSWORD` | No | — | SMTP password or app-specific password |
| `EMAILS_FROM` | No | — | Sender address shown in outgoing emails (e.g. `noreply@nextfolio.example.com`) |

---

## Monitoring

| Variable | Required | Description |
|---|---|---|
| `SENTRY_DSN` | No | Sentry DSN for **backend** error tracking. Get one at [sentry.io](https://sentry.io) |
| `VITE_SENTRY_DSN` | No | Sentry DSN for **frontend** error tracking (must be set at build time for Vite to include it) |

---

## Generating Secrets

```bash
# SECRET_KEY (64 hex chars)
openssl rand -hex 32

# POSTGRES_PASSWORD or REDIS_PASSWORD (32 hex chars)
openssl rand -hex 16
```

---

## Development Defaults

The `docker-compose.dev.yml` file hard-codes sensible defaults so you don't need to touch `.env` for local development:

```
POSTGRES_PASSWORD = nextfolio
REDIS_PASSWORD    = (none — no auth in dev)
SECRET_KEY        = dev-secret-key-change-in-production
APP_URL           = http://localhost:5173
CORS_ORIGINS      = http://localhost:5173
```

Never use these values in production.
