# Architecture

## System Overview

Nextfolio is a self-hosted, multi-service application composed of six Docker containers that communicate over isolated Docker networks.

```
                        ┌─────────────────────────────────┐
                        │           Client Browser         │
                        └────────────┬──────┬─────────────┘
                                     │      │ WebSocket
                          HTTP/HTTPS │      │ /ws/prices
                                     ▼      ▼
                        ┌─────────────────────────────────┐
                        │    Frontend (React + Nginx)      │
                        │         :80 / :443               │
                        └──────────────┬──────────────────┘
                                       │ REST API proxy
                                       ▼
                        ┌─────────────────────────────────┐
                        │      Backend (FastAPI)           │
                        │            :8000                 │
                        └──┬───────────────────┬──────────┘
                           │                   │
              ┌────────────▼──┐         ┌──────▼───────────┐
              │  PostgreSQL   │         │      Redis         │
              │     :5432     │         │      :6379         │
              └───────────────┘         └──────┬────────────┘
                                               │ broker / cache
                                    ┌──────────┴──────────┐
                                    │                     │
                           ┌────────▼──────┐   ┌──────────▼──────┐
                           │  Celery Worker │   │  Celery Beat    │
                           │  (task exec)  │   │  (scheduler)    │
                           └───────────────┘   └─────────────────┘
```

---

## Services

### Frontend — React + Vite + TypeScript

- Served by **Nginx** in production; Vite dev server in development
- Communicates with the backend exclusively via the REST API and WebSocket
- State management: **Zustand**
- Server state & caching: **TanStack Query**
- Routing: **React Router v6**
- Charts: **Recharts**
- Forms: **React Hook Form** + **Zod**
- Internationalisation: **i18next** (Italian / English)

**Key pages:**

| Page | Description |
|---|---|
| Dashboard | Portfolio summary, allocation pie, recent transactions |
| Performance | Time-series P&L chart, benchmark comparison |
| Transazioni | Full transaction history with filters |
| Dividendi | Dividend income history and projections |
| Allocation | Geographic and asset-class breakdown |
| Fiscale | Italian tax report (capital gains, dividends) |
| Strumenti | Tools: FX calculator, import/export |
| Admin | User management (Superadmin only) |
| Impostazioni | Personal settings, 2FA configuration |

### Backend — FastAPI + Python

Async API server built with FastAPI, using SQLAlchemy async ORM over asyncpg.

```
backend/app/
├── api/
│   ├── v1/endpoints/       # Route handlers (one file per domain)
│   └── ws.py               # WebSocket price broadcaster
├── core/
│   ├── config.py           # Pydantic settings (reads env vars)
│   ├── database.py         # Async engine + session factory
│   ├── deps.py             # FastAPI dependency injection
│   └── security.py         # JWT, password hashing, TOTP
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic request/response schemas
├── services/
│   ├── market_data/        # Price fetchers (Yahoo, CoinGecko, Borsa Italiana)
│   ├── portfolio/
│   │   ├── positions.py    # FIFO P&L engine
│   │   └── performance.py  # Time-series performance calculator
│   └── tax/
│       └── calculator.py   # Italian tax engine
└── tasks/
    ├── celery_app.py        # Celery instance
    └── price_tasks.py       # Scheduled price fetch tasks
```

**Security hardening:**
- Rate limiting via **slowapi**
- Trusted host middleware (blocks Host header injection)
- `no-new-privileges` Docker security option on all containers
- Passwords hashed with **bcrypt**
- JWT signed with HS256; access tokens short-lived (30 min default)
- Refresh tokens stored as opaque hashes in the database
- Optional Sentry integration for error tracking

### PostgreSQL 15

Primary data store. Schema managed via **Alembic** migrations.

**Core tables:**

| Table | Description |
|---|---|
| `users` | Accounts, roles, 2FA secrets, email verification |
| `accounts` | Named investment accounts per user |
| `assets` | Asset registry (ISIN, ticker, type, currency) |
| `transactions` | All BUY/SELL/DIVIDEND/FEE records |
| `prices` | Latest price cache (also backed by Redis) |
| `alerts` | User-defined price/P&L alert thresholds |
| `audit_logs` | Admin action audit trail |

### Redis 7

Dual role:
1. **Price cache** — TTL-based cache for market prices (avoids hammering external APIs)
2. **Celery broker + result backend** — Task queue for async price fetching

### Celery Worker + Beat

- **Worker** executes price-fetch tasks asynchronously
- **Beat** scheduler triggers periodic tasks:
  - Every 15 min (market hours): equities and ETFs
  - Every 5 min: crypto

After each fetch, updated prices are broadcast to all connected WebSocket clients.

---

## Data Flow — Price Update

```
Celery Beat (cron)
      │
      ▼
Celery Worker
      │  fetch prices from Yahoo / CoinGecko / Borsa Italiana
      │
      ▼
Redis (price cache)  ──────►  PostgreSQL (prices table)
      │
      ▼
FastAPI WebSocket broadcaster
      │  publishes { isin, price, change_pct }
      ▼
All connected browser clients (real-time update)
```

---

## Data Flow — P&L Calculation

P&L is computed on the fly from the raw transaction ledger — no pre-aggregated P&L is stored.

```
GET /portfolio/positions
      │
      ▼
Load all transactions for user (ordered by date + id)
      │
      ▼
FIFO engine (services/portfolio/positions.py)
  ├── BUY  → append Lot(quantity, cost_per_unit_eur)
  └── SELL → consume oldest lots, accumulate realized_pnl_eur
      │
      ▼
Enrich with current prices from Redis
      │
      ▼
Return PositionOut[]  (quantity, PMC, invested_eur, realized_pnl, unrealized_pnl)
```

---

## Docker Networks

| Network | Members | Purpose |
|---|---|---|
| `data` | postgres, redis, backend, celery, celery-beat | Internal data plane — not exposed |
| default | frontend, backend | Frontend ↔ backend communication |

In production, only the frontend container exposes ports (80/443). The backend is reachable only through the frontend's Nginx reverse proxy.

---

## Authentication Flow

```
POST /auth/login
  └── verify email + password
  └── if 2FA enabled → issue short-lived 2FA session token
        └── POST /auth/verify-2fa  → issue access + refresh tokens
  └── if 2FA disabled → issue access + refresh tokens directly

POST /auth/refresh
  └── validate refresh token hash in DB
  └── issue new access token (sliding window)
```

Access tokens are Bearer tokens sent in the `Authorization` header. Refresh tokens are stored as **bcrypt hashes** in the database — the raw token is never persisted.
