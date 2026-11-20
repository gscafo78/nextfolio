# Nextfolio

> Self-hosted wealth management and portfolio tracker for the Italian market.

**Stack:** React + TypeScript · FastAPI · PostgreSQL · Redis · Celery · Docker  
**Current version:** 1.15.2 · [Changelog](CHANGELOG.md)

---

## Features

### Portfolio
- **Multi-asset tracking** — Stocks, ETFs, Bonds (BTP/BOT/CCT), Crypto, Cash
- **FIFO P&L engine** — Realized and unrealized P&L with FIFO lot matching
- **Real-time prices** — Yahoo Finance, CoinGecko, Borsa Italiana API, ECB FX rates via WebSocket
- **Multi-currency** — Transactions in any currency; all amounts converted to EUR at transaction rate
- **Multi-account** — Separate investment accounts per broker, with per-account fiscal regime and cash balance history

### Tax engine (Italian market)
- **Capital gains** — 26% (equities, corporate bonds, ETCs); government bonds (BTP/BOT/CCT, white-list sovereigns, supranationals) weighted at 48.08% → effective 12.5%; crypto-assets 26% until 2025, 33% from 2026
- **ETF / funds** — Gains taxed as capital income (26%, not offsettable); losses go into the loss pool
- **Sostituto d'imposta** — Per-account flag: administered regime (broker manages taxes) or declaratory regime (user declares in Redditi PF)
- **PMC / WAC** — Weighted average cost (art. 68 c.6 TUIR) in both regimes: per account in the administered regime, per asset across declaratory accounts
- **Loss carryforward** — Minusvalenze carried forward up to 4 years: one pool for redditi diversi (government bonds at 48.08%), one for crypto-assets
- **IVAFE** — 0.2% annual tax on foreign financial assets (per-account `is_foreign` flag); calculated at Dec 31 market value
- **Income tracking** — Dividends (26%), BTP coupons (12.5%), corporate-bond coupons (26%), interest
- **Dichiarazione assistita** — Summary of figures to enter in modello Redditi PF (quadri RT, RW, RL) with one-click copy
- **Fiscal PDF export** — `GET /tax/export/pdf?year=YYYY` — print-ready PDF with all fiscal sections

### Analytics
- **X-Ray** — Automated portfolio diagnostic (11 rules: concentration on single securities, asset class by underlying, look-through currency, equity geography, Italy exposure, fees, liquidity)
- **Allocation** — Asset class by underlying (bond ETFs = bonds), look-through currency exposure (hedged ETFs = EUR), equity/bond geography, sector, instrument type; manual asset-class override
- **Performance** — Flow-neutral TWRR (income included), per-period P&L (end − start − net flows + income), IRR/XIRR, benchmark comparison (MSCI World / FTSE MIB)
- **Dividend analytics** — Income calendar, yield on cost, growth history
- **Sell simulator** — Estimated tax impact before selling (weighted average cost, category-aware rate)
- **Loss simulator** — Carryforward visual, multi-year history

### Tools
- **Rebalancing** — Suggest buy/sell amounts to reach target asset-class weights
- **Watchlist** — Monitor assets without owning them (price, change %, target price)
- **PAC calculator** — Simulate a recurring investment plan
- **Correlation matrix** — Pearson heatmap between portfolio assets
- **Risk metrics** — Volatility, max drawdown, Sharpe, Sortino, Calmar on flow-neutral trading-day returns, with plausibility warnings

### Planning
- **Security search** — Name, ticker or ISIN with suggestions after 3 characters, from Nextfolio and Yahoo Finance (also securities never bought), type filters, security card with chart, metrics and look-through
- **Purchase simulator** — What-if purchases (new money or account cash): asset class, currency exposure, weights and every X-Ray rule before → after
- **Scenarios** — Save, compare (up to 4) and execute scenarios as real transactions
- **Smart contribution** — Target allocation by asset class with tolerance band and drift alert; buy-only suggestions for a new contribution or the available cash
- **Goals & FIRE** — Monte Carlo projection (probability, percentiles, contribution needed), FIRE calculator, simple PAC projection
- **Tax planning** — Expiring losses, suggested sales to use them or offset this year's gains (ETF gains excluded), multi-sale simulation with taxes before → after
- **Compare & backtest** — Compare 2–4 securities (returns, risk, correlation, ETF overlap) and backtest model portfolios with contributions and rebalancing

### AI
- **Chatbot prompt** — One click generates a text with your portfolio (holdings, allocation, performance, risk, X-Ray, dividends) plus analysis instructions, ready to paste into ChatGPT, Claude, Gemini, …; amounts optional (percentages only)
- **MCP server** — [Model Context Protocol](https://modelcontextprotocol.io) server at `/api/mcp` so AI assistants (Claude Desktop, Claude Code, ChatGPT, …) can query and update the portfolio; per-user tokens with separate permissions to read amounts, write (transactions, assets, watchlist, alerts) and delete; every write in the audit log

### UX
- **Zen Mode** — Masks all EUR amounts; percentages remain visible (for screenshots, screen sharing)
- **Dark / Light / System theme**
- **i18n** — Italian, English, French, German UI
- **Progressive Web App** — Installable, offline fallback, mobile-optimised layouts
- **Import** — Fineco, Directa Plus, Degiro, Interactive Brokers (Flex Query CSV)
- **Export** — Excel (transactions + positions), PDF portfolio report, PDF fiscal report, Ghostfolio JSON

### Security
- **Two-factor authentication** — TOTP (Google Authenticator, Aegis, Authy, etc.)
- **Role-based access** — Superadmin (full access) and User
- **JWT tokens** — Short-lived access tokens (30 min) + refresh tokens with optional "Remember Me" (30 days)
- **bcrypt** password hashing · Rate limiting via slowapi · Audit log

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

> **First run:** the first user to register becomes **Superadmin** automatically. Subsequent registrations are locked — new users are created from the **Administration** page inside the app.

### Production

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full instructions covering Cloudflare Tunnel, HTTPS with Let's Encrypt, and environment variable reference.

---

## Architecture

```
nextfolio/
├── frontend/               # React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── components/     # Shared UI components
│       ├── pages/          # One file per route
│       ├── services/       # Typed API clients (axios)
│       └── locales/        # i18n strings (it, en, fr, de)
│
├── backend/                # FastAPI + Python (async)
│   └── app/
│       ├── api/            # Route handlers + WebSocket
│       ├── models/         # SQLAlchemy ORM models
│       ├── schemas/        # Pydantic I/O schemas
│       ├── services/
│       │   ├── market_data/    # Price fetchers
│       │   ├── portfolio/      # P&L, positions, X-Ray, rebalancing
│       │   └── tax/            # Italian tax engine (PMC, 48.08% weighting, IVAFE)
│       └── tasks/          # Celery price-fetch tasks
│
├── docker-compose.yml          # Production compose
├── docker-compose.dev.yml      # Development compose
└── docker-compose.https.yml    # HTTPS override (Let's Encrypt)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full system diagram and service breakdown.

---

## Price Sources

| Source             | Assets                           | Frequency                   |
| ------------------ | -------------------------------- | --------------------------- |
| Yahoo Finance      | Stocks (.MI), ETFs, Bonds (MOT)  | Every 15 min (market hours) |
| CoinGecko          | Crypto                           | Every 5 min                 |
| Borsa Italiana API | ISIN on MIL / EuroTLX / MOT     | Every 15 min (market hours) |
| ECB (Frankfurter)  | FX exchange rates                | On demand (per transaction) |

Prices are cached in Redis and streamed to clients in real time via WebSocket at `/ws/prices`.

---

## Documentation

| Document | Description |
|---|---|
| [USER_GUIDE.md](docs/USER_GUIDE.md) | End-user guide: all features explained |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, service breakdown, data flow |
| [API.md](docs/API.md) | REST API and WebSocket reference |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | All environment variables explained |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Useful Commands

```bash
# Rebuild a single service after code changes
docker compose build backend && docker compose up -d backend

# Apply database migrations
docker exec nextfolio_backend alembic upgrade head

# Check current migration version
docker exec nextfolio_backend alembic current

# View backend logs
docker compose logs -f backend

# Open a psql shell
docker exec -it nextfolio_postgres psql -U nextfolio
```

---

## License

[MIT](LICENSE)
