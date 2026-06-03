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
- Communicates with the backend exclusively via REST API and WebSocket
- State management: **Zustand**
- Server state & caching: **TanStack Query**
- Routing: **React Router v6** (BrowserRouter)
- Charts: **Recharts**
- Forms: **React Hook Form** + **Zod**
- Internationalisation: **i18next** (Italian, English, French, German)
- UI library: **Tailwind CSS** with custom `brand` palette

**Key pages:**

| Page | Route | Description |
|---|---|---|
| Dashboard | `/` | Portfolio summary, allocation, P&L chart, ticker |
| Performance | `/performance` | Time-series P&L, IRR, benchmark, risk metrics |
| Transazioni | `/transazioni` | Full transaction history with pagination |
| Allocazioni | `/allocazioni` | Asset-class, geography, sector donut charts |
| Dividendi | `/dividendi` | Dividend income calendar and history |
| Fiscale | `/fiscale` | Italian tax report (RT, RW, RL, IVAFE, PDF export) |
| X-Ray | `/xray` | Portfolio diagnostic with 10 rules + rebalancing |
| Watchlist | `/watchlist` | Monitored assets |
| Alert | `/alert` | Price threshold alerts |
| Strumenti | `/strumenti` | PAC calculator, correlation, import/export |
| Impostazioni | `/impostazioni` | Accounts, preferences, 2FA |
| Admin | `/admin` | User management (Superadmin only) |

### Backend — FastAPI + Python

Async API server built with FastAPI, using SQLAlchemy async ORM over asyncpg.

```
backend/app/
├── api/
│   ├── v1/endpoints/
│   │   ├── auth.py          # JWT auth, 2FA, password reset
│   │   ├── portfolio.py     # positions, performance, allocation, X-Ray, rebalancing
│   │   ├── transactions.py  # CRUD transactions
│   │   ├── assets.py        # asset search, price lookup, backfill
│   │   ├── accounts.py      # CRUD accounts (fiscal regime flags)
│   │   ├── tax.py           # tax report, IVAFE, fiscal PDF export
│   │   ├── dividends.py     # dividend income aggregation
│   │   ├── watchlist.py     # watchlist CRUD
│   │   ├── alerts.py        # price alert CRUD
│   │   ├── export.py        # Excel, PDF portfolio, Ghostfolio export
│   │   ├── import_.py       # CSV import (Fineco, Degiro, Directa, IBKR)
│   │   ├── fx.py            # ECB FX rates
│   │   ├── admin.py         # user management (Superadmin)
│   │   └── settings.py      # user preferences
│   └── ws.py                # WebSocket price broadcaster
├── core/
│   ├── config.py            # Pydantic settings (reads env vars)
│   ├── database.py          # Async engine + session factory
│   ├── deps.py              # FastAPI dependency injection
│   └── security.py          # JWT, bcrypt, TOTP
├── models/                  # SQLAlchemy ORM models
├── schemas/                 # Pydantic request/response schemas
├── services/
│   ├── market_data/
│   │   ├── yahoo.py         # Yahoo Finance price fetcher
│   │   ├── coingecko.py     # CoinGecko crypto prices
│   │   ├── borsa_italiana.py # Borsa Italiana (BTP, MOT)
│   │   └── updater.py       # Redis cache management
│   ├── portfolio/
│   │   ├── positions.py     # FIFO P&L engine (PositionCalc, Lot)
│   │   ├── performance.py   # Time-series performance calculator
│   │   ├── allocation.py    # Allocation + ETF look-through
│   │   ├── xray.py          # Portfolio health rules (10 rules, 4 categories)
│   │   └── rebalancing.py   # Trade suggestions for target allocation
│   └── tax/
│       ├── calculator.py    # Italian tax engine:
│       │                    #   - FIFO (declaratory regime, lots_fifo per asset)
│       │                    #   - PMC/WAC (administered regime, lots_wac per account+asset)
│       │                    #   - TaxEvent: gain/loss + is_sostituto_imposta + calculation_method
│       │                    #   - AnnualTaxReport: carryforward pools + regime breakdown
│       └── ivafe.py         # IVAFE calculator:
│                            #   - 0.2% on Dec-31 market value of foreign accounts
│                            #   - Queries price_history for year-end price
└── tasks/
    ├── celery_app.py        # Celery instance configuration
    ├── prices.py            # Scheduled price fetch tasks (EOD + intraday)
    └── alerts.py            # Price alert check task (every 5 min)
```

**Security hardening:**
- Rate limiting via **slowapi**
- Trusted host middleware (blocks Host header injection)
- `no-new-privileges` Docker security option on all containers
- Passwords hashed with **bcrypt**
- JWT signed with HS256; access tokens short-lived (30 min)
- Refresh tokens stored as bcrypt hashes in the database (raw token never persisted)
- Optional Sentry integration for error tracking

### PostgreSQL 15

Primary data store. Schema managed via **Alembic** migrations (currently at revision `0019`).

**Core tables:**

| Table | Description |
|---|---|
| `users` | Accounts, roles (`SUPERADMIN`/`USER`), TOTP secrets, email verification |
| `user_settings` | Per-user preferences: theme, display_currency, zen_mode, language |
| `accounts` | Named investment accounts; fields: `is_sostituto_imposta`, `is_foreign`, `url` |
| `assets` | Asset registry: ISIN, ticker, type, currency, sector, country enrichment |
| `transactions` | All BUY/SELL/DIVIDEND/COUPON/INTEREST/FEE records |
| `price_history` | OHLCV daily prices per asset |
| `prices` | Latest price cache (also backed by Redis) |
| `watchlist` | User-monitored assets with optional note and target_price |
| `price_alerts` | Price/change-% threshold alerts with cooldown |
| `audit_logs` | Admin action trail |
| `app_settings` | Global app config (public registration toggle, etc.) |

### Redis 7

Dual role:
1. **Price cache** — TTL-based cache for market prices (avoids hammering external APIs)
2. **Celery broker + result backend** — Task queue for async price fetching and alert checking

Cache keys:
- `price:{asset_id}` → `{ price, currency, exchange_rate, change_pct, updated_at }` (TTL: 5 min equities, 1 min crypto)
- `portfolio_performance:{user_id}` → cached performance response (TTL: 10 min)
- `xray:{user_id}` → cached X-Ray response (TTL: 10 min)

### Celery Worker + Beat

- **Worker** executes price-fetch tasks asynchronously
- **Beat** scheduler triggers:
  - Every 15 min (Mon–Fri 09:00–17:30 Rome time): equities, ETFs, BTP
  - Every 5 min: crypto
  - Every 5 min: price alert check
  - Daily at 03:00: unverified user cleanup

After each price fetch, updated prices are broadcast to all connected WebSocket clients via the FastAPI WebSocket broadcaster.

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
Redis (price cache, TTL)  ──────►  PostgreSQL (price_history, prices)
      │
      ▼
FastAPI WebSocket broadcaster
      │  publishes { asset_id, price, change_pct, exchange_rate }
      ▼
All connected browser clients (real-time update)
```

---

## Data Flow — P&L Calculation

P&L is computed on the fly from the raw transaction ledger — no pre-aggregated state is stored.

```
GET /portfolio/positions
      │
      ▼
Load all transactions for user (ordered by date + id, with account + asset selectinload)
      │
      ▼
FIFO engine (services/portfolio/positions.py)
  ├── BUY  → append Lot(quantity, cost_per_unit_eur)
  └── SELL → consume oldest lots, accumulate realized_pnl_eur
      │
      ▼
Enrich with current prices from Redis (MGET bulk)
      │
      ▼
Return PositionOut[] (quantity, PMC, invested_eur, unrealized_pnl, ...)
```

---

## Data Flow — Tax Engine

```
GET /tax/report?year=2024
      │
      ▼
Load all transactions (with account selectinload for is_sostituto_imposta, is_foreign)
      │
      ▼
compute_tax_events(transactions)  →  list[TaxEvent]
  ├── For each BUY/SELL:
  │     is_sostituto_imposta=True  → PMC: lots_wac[(account_id, asset_id)]
  │     is_sostituto_imposta=False → FIFO: lots_fifo[asset_id]
  ├── For each DIVIDEND/COUPON/INTEREST:
  │     tag with is_sostituto_imposta; no lot tracking needed
  └── Each TaxEvent carries: calculation_method ("PMC"|"FIFO"), is_sostituto_imposta
      │
      ▼
build_annual_reports(events)  →  list[AnnualTaxReport]
  ├── Per-year: capital gains/losses per bracket (26%, 12.5%)
  ├── Carryforward pools: pool_standard, pool_govt  (4-year window)
  ├── Income: dividends_eur, coupons_govt_eur, coupons_standard_eur, interests_eur
  ├── income_tax_eur: estimated withholding per income type
  └── Regime breakdown: administered_* and declaratory_* fields (no separate carryforward)
      │
      ▼
compute_ivafe(db, transactions, year)  →  IVAFEReport
  ├── Filter transactions on is_foreign=True accounts, date ≤ Dec 31
  ├── Compute net quantity per asset
  ├── Query price_history for last close ≤ Dec 31
  └── IVAFE = qty × price_eur × 0.002
      │
      ▼
AnnualTaxReportOut (JSON or PDF)
```

---

## Authentication Flow

```
POST /auth/login
  └── verify email + bcrypt password
  └── if 2FA enabled → issue short-lived 2FA session token
        └── POST /auth/verify-2fa → issue access + refresh tokens
  └── if 2FA disabled → issue access + refresh tokens directly

POST /auth/refresh
  └── validate refresh token hash in DB
  └── issue new access token (sliding window)
  └── if remember_me flag on token: 30-day TTL; otherwise 7-day TTL
```

Access tokens are Bearer tokens in the `Authorization` header. Refresh tokens are stored as **bcrypt hashes** — the raw token is never persisted.

---

## Docker Networks

| Network | Members | Purpose |
|---|---|---|
| `data` | postgres, redis, backend, celery, celery-beat | Internal data plane — not exposed |
| `backend` | frontend, backend | Frontend ↔ backend communication |

In production, only the frontend container exposes ports (80/443). The backend is reachable only through the frontend's Nginx reverse proxy.

---

## Alembic Migrations

Migrations are in `backend/alembic/versions/`. Apply with:

```bash
docker exec nextfolio_backend alembic upgrade head
```

| Revision | Description |
|---|---|
| 0001 | Initial users table |
| 0002 | Assets and transactions |
| 0003 | Prices and accounts |
| 0004 | User settings, audit logs |
| 0005 | Price alerts |
| 0006–0015 | Enrichment, 2FA, app_settings, email verification, indexes |
| 0016 | Performance indexes |
| 0017 | Watchlist table |
| 0018 | `is_sostituto_imposta` on accounts |
| 0019 | `is_foreign` on accounts (IVAFE) |
