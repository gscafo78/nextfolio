# Nextfolio

> Self-hosted wealth management and portfolio tracker for the Italian market.

**Stack:** React + TypeScript · FastAPI · PostgreSQL · Redis · Celery · Docker

---

## Features

- **Multi-asset tracking** — Stocks, ETFs, Bonds, Crypto, Cash
- **Real-time prices** — Yahoo Finance, CoinGecko, Borsa Italiana API, ECB FX rates
- **FIFO P&L engine** — Realized and unrealized P&L with FIFO lot matching
- **Italian tax engine** — Capital gains, dividends, and withholding tax calculations
- **Portfolio analytics** — Allocation charts, performance history, geographic breakdown
- **Dividend tracking** — Income history and projections
- **Import / Export** — CSV import, Ghostfolio-compatible import, PDF export
- **Zen Mode** — Masks all EUR amounts for privacy (screenshots, screen sharing)
- **Two-factor authentication** — TOTP (Google Authenticator, Aegis, etc.)
- **Role-based access** — Superadmin and User roles
- **WebSocket price streaming** — Live price updates pushed to all connected clients
- **Alerts** — Price and P&L threshold notifications
- **i18n** — Italian and English UI

---

## Quick Start (Docker)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/) v2

### Development

```bash
# 1. Clone the repository
git clone https://github.com/gscafo78/nextfolio.git
cd nextfolio

# 2. Copy environment variables
cp .env.example .env
# No changes needed for local dev — defaults are pre-filled in docker-compose.dev.yml

# 3. Start all services
docker compose -f docker-compose.dev.yml up -d

# 4. Follow logs (optional)
docker compose -f docker-compose.dev.yml logs -f
```

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:5173      |
| API      | http://localhost:8000      |
| API docs | http://localhost:8000/docs |

> **First run:** register the first user via `POST /api/v1/auth/register` — it becomes **Superadmin** automatically. Subsequent registrations are locked; new users are created from the **Administration** page inside the app.

### Production

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full instructions covering:

- Cloudflare Tunnel (recommended — no open ports required)
- HTTPS with Let's Encrypt
- Environment variable reference

---

## Architecture

```
nextfolio/
├── frontend/               # React + Vite + TypeScript
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/       # API clients
│       └── store/          # Zustand state
│
├── backend/                # FastAPI + Python
│   └── app/
│       ├── api/            # Route handlers + WebSocket
│       ├── models/         # SQLAlchemy ORM models
│       ├── schemas/        # Pydantic I/O schemas
│       ├── services/       # Business logic (portfolio, tax, market data)
│       └── tasks/          # Celery async tasks
│
├── docker-compose.yml          # Production compose
├── docker-compose.dev.yml      # Development compose
└── docker-compose.https.yml    # HTTPS override (Let's Encrypt)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full system diagram and service breakdown.

---

## Price Sources

| Source             | Assets                          | Frequency                   |
| ------------------ | ------------------------------- | --------------------------- |
| Yahoo Finance      | Stocks (.MI), ETFs, Bonds (MOT) | Every 15 min (market hours) |
| CoinGecko          | Crypto                          | Every 5 min                 |
| Borsa Italiana API | ISIN on MIL / EuroTLX / MOT     | Every 15 min (market hours) |
| ECB (Frankfurter)  | FX exchange rates               | On demand                   |

Prices are cached in Redis (5 min for equities, 1 min for crypto) and streamed in real time to clients via WebSocket at `/ws/prices`.

---

## Authentication & Roles

| Role       | Permissions                                                   |
| ---------- | ------------------------------------------------------------- |
| SUPERADMIN | Full access: create/edit/delete users, reset other users' 2FA |
| USER       | Personal settings (currency, theme), own 2FA                  |

### Two-Factor Authentication (TOTP)

2FA is optional and configured from the **Settings** page:

1. Click "Configure 2FA" → scan the QR code with any TOTP app
2. Enter the 6-digit code to activate
3. On subsequent logins the TOTP code is requested after email + password

---

## Remote Access via SSH

If the app runs on a remote server, forward ports locally:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@server-ip
```

Then open http://localhost:5173 in your local browser.

---

## Useful Commands

```bash
# Rebuild a single service (e.g. after editing requirements.txt)
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d backend

# Install an npm package inside the running frontend container
docker exec nextfolio_frontend npm install <package>

# Run database migrations manually
docker exec nextfolio_backend alembic upgrade head

# Run backend tests
docker exec nextfolio_backend pytest -v --cov=app

# Start Celery worker (not included in dev compose by default)
cd backend && celery -A app.tasks.celery_app:celery_app worker --loglevel=info
```

---

## Documentation

| Document                                   | Description                                 |
| ------------------------------------------ | ------------------------------------------- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md)    | System design, service breakdown, data flow |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md)        | Production deployment guide                 |
| [CONFIGURATION.md](docs/CONFIGURATION.md)  | All environment variables explained         |
| [API.md](docs/API.md)                      | REST API and WebSocket reference            |
| [CONTRIBUTING.md](.github/CONTRIBUTING.md) | How to contribute                           |
| [SECURITY.md](.github/SECURITY.md)         | Security policy and vulnerability reporting |
| [CHANGELOG.md](CHANGELOG.md)               | Release history                             |

---

## License

[MIT](LICENSE)
