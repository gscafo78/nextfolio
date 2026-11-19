# API Reference

Nextfolio exposes a versioned REST API and a WebSocket endpoint for real-time price streaming.

**Base URL:** `http(s)://yourdomain/api/v1`  
**Interactive docs:** available at `/docs` when `DEBUG=true`

---

## Authentication

All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/forgot-password`, and `/auth/reset-password` require a valid Bearer token.

```
Authorization: Bearer <access_token>
```

Access tokens expire in 30 minutes. Use `/auth/refresh` to obtain a new one.

---

## Auth

### Register
```
POST /auth/register
```
Creates the first user (Superadmin). Subsequent registrations are disabled by default.

**Body:**
```json
{ "email": "user@example.com", "password": "strongpassword", "name": "Alice" }
```

### Login
```
POST /auth/login
```
**Body:**
```json
{ "email": "user@example.com", "password": "strongpassword", "remember_me": false }
```
**Response (2FA disabled):** `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`  
**Response (2FA enabled):** `{ "requires_2fa": true, "session_token": "..." }`

### Verify 2FA
```
POST /auth/verify-2fa
Body: { "session_token": "...", "code": "123456" }
```

### Refresh Token
```
POST /auth/refresh
Body: { "refresh_token": "..." }
```

### Password Reset
```
POST /auth/forgot-password    # sends reset email
POST /auth/reset-password     # consumes token, sets new password
```

---

## Accounts

```
GET    /accounts              # list user's accounts
POST   /accounts              # create account
PATCH  /accounts/{id}         # update account
DELETE /accounts/{id}         # delete account (only if no transactions)
```

**Account fields:**
```json
{
  "name": "Fineco Main",
  "type": "BROKERAGE",
  "broker": "Fineco",
  "url": "https://www.fineco.it",
  "currency": "EUR",
  "is_sostituto_imposta": true,
  "is_foreign": false
}
```

| Field | Description |
|---|---|
| `is_sostituto_imposta` | `true` = broker handles Italian taxes (administered regime, PMC per account); `false` = user must declare in 730 (declaratory regime, PMC per asset across declaratory accounts) |
| `is_foreign` | `true` = account at a non-Italian intermediary; enables IVAFE 0.2% calculation in the tax report |

---

## Portfolio

### Positions
```
GET /portfolio/positions
```
Returns all open positions with FIFO P&L, current prices, and unrealized P&L.

### Dashboard aggregate
```
GET /portfolio/dashboard
```
Single endpoint returning positions + performance + allocation in one call (used by the Dashboard page to minimise round-trips).

### Portfolio Summary
```
GET /portfolio/summary
```
`total_pnl_eur` = unrealized + realized (closed positions included) + `income_eur` (coupons, dividends, interest net of separate fees). `total_invested_eur` is the cost basis of open positions.

### Performance History
```
GET /portfolio/performance?period=1y&account_id=1
```
`period`: `today|wtd|mtd|ytd|1w|1m|3m|6m|1y|3y|max|YYYY`.

| Field | Description |
|---|---|
| `twrr_pct` | Time-weighted return of the period, income included, flow-neutral |
| `twrr_annualized_pct` | Only for periods ≥ 1 year, otherwise `null` |
| `start_date` / `end_date` / `requested_start_date` | Actual and requested period bounds |
| `history_truncated` | `true` if the history is shorter than the requested period |
| `start_value_eur` / `end_value_eur` | Value at the opening / end of the period |
| `net_flows_eur` | Purchases − sales in the period |
| `income_eur` | Coupons, dividends, interest − fees in the period |
| `pnl_eur` | `end − start − net_flows + income` |
| `invested_eur` | `start_value + net_flows` |
| `series[]` | `date, value_eur, invested_eur, pnl_eur, twrr_pct, daily_return_pct, reliable, flow_eur, income_eur` (trading days only) |

### Risk Metrics
```
GET /portfolio/risk?period=3y&account_id=1
```
Volatility, max drawdown (on the TWRR index), Sharpe, Sortino, Calmar, best/worst day, positive days on flow-neutral trading-day returns. Also returns `risk_free_pct` (from `RISK_FREE_RATE_PCT`) and `warnings[]` (excluded low-base days, implausible values). `twrr_annualized_pct` and `calmar_ratio` are `null` with less than one year of data.

### Allocation
```
GET /portfolio/allocation
```
Returns breakdown by type, platform, currency, sector, continent, plus the look-through fields:

| Field | Description |
|---|---|
| `by_asset_class` | Azioni / Obbligazioni / Monetario / Crypto / Altro, by underlying (bond ETFs = Obbligazioni) |
| `by_currency_exposure` | Underlying currencies (hedged ETFs = EUR; `Non dettagliata` = countries not provided) |
| `by_continent_equity` / `by_continent_bond` | Geography of the equity / bond part |
| `italy_exposure_pct` | Italy on the total portfolio (BTPs included) |

### X-Ray
```
GET /portfolio/xray
```
Returns an array of `XRayRule` objects plus an overall `score` (0–100).

**Response:**
```json
{
  "score": 82,
  "rules_total": 11,
  "rules_ok": 9,
  "rules": [
    {
      "key": "concentration_single_asset",
      "name": "Concentrazione singolo titolo",
      "category": "Concentrazione",
      "status": "ok",
      "actual": 0.18,
      "threshold_max": 0.20,
      "unit": "%"
    }
  ]
}
```

### Rebalancing
```
POST /portfolio/rebalance
Body: { "targets": [{"label": "equities", "pct": 70}, ...], "cash_available": 1000 }
```
Returns suggested buy/sell trades to reach target allocation.

---

## Transactions

### List
```
GET /transactions?account_id=1&from=2024-01-01&to=2024-12-31&type=BUY&limit=50&offset=0
```

### Create
```
POST /transactions
```
```json
{
  "account_id": 1,
  "asset_id": 42,
  "type": "BUY",
  "date": "2024-03-15",
  "quantity": 10,
  "price": 107.50,
  "exchange_rate": 1.0,
  "fee": 2.95,
  "currency": "EUR"
}
```
**Transaction types:** `BUY`, `SELL`, `DIVIDEND`, `COUPON`, `INTEREST`, `FEE`, `DEPOSIT`, `WITHDRAWAL`

### Update / Delete
```
PATCH  /transactions/{id}
DELETE /transactions/{id}
```

---

## Assets

```
GET /assets/search?q=MSCI+World
GET /assets/lookup?isin=IE00B4L5Y983
GET /prices/{asset_id}
POST /assets/{id}/backfill      # trigger historical price backfill
PATCH /assets/{id}              # update asset data and overrides
```

`PATCH /assets/{id}` accepts, besides the master data:

| Field | Values | Description |
|---|---|---|
| `asset_class_override` | `EQUITY` \| `BOND` \| `MONEY_MARKET` \| `CRYPTO` \| `OTHER` \| `null` | Underlying asset class (`null` = automatic) |
| `govt_bond_override` | `true` \| `false` \| `null` | Force government-bond tax treatment for a BOND |
| `govt_bond_share` | `0`–`1` \| `null` | ETF share invested in white-list government bonds (reduced tax base) |
| `sectors_override`, `countries_override` | list \| `null` | Manual look-through |

---

## Tax (Italian)

### Annual Report
```
GET /tax/report?year=2024
```
Returns the full annual tax report. All amounts are in EUR.

**Key response fields:**

| Field | Description |
|---|---|
| `gains_standard` / `losses_standard` | Total capital gains/losses at 26% |
| `tax_standard` | Capital gains tax at 26% |
| `gains_govt` / `losses_govt` | Total gains/losses at 12.5% (BTP/BOT/CCT) |
| `tax_govt` | Capital gains tax at 12.5% |
| `income_tax_eur` | Estimated withholding on dividends + coupons + interest |
| `administered_total_tax` | Total tax already handled by the broker |
| `declaratory_total_tax` | Total tax to declare in modello Redditi PF |
| `administered_income_tax` | Income withholding for administered accounts |
| `declaratory_income_tax` | Income withholding for declaratory accounts |
| `has_declaratory_accounts` | `true` if any account is in declaratory regime |
| `ivafe` | IVAFE report object (see below) |
| `events[]` | Array of fiscal events; each has `is_sostituto_imposta` and `calculation_method` ("FIFO"\|"PMC") |

**IVAFE object:**
```json
{
  "year": 2024,
  "total_market_value_eur": 15000.00,
  "ivafe_eur": 30.00,
  "rate": 0.002,
  "has_foreign_accounts": true,
  "positions": [
    {
      "asset_id": 5,
      "asset_name": "iShares Core MSCI World",
      "quantity": 42.5,
      "price_eur": 352.94,
      "market_value_eur": 14999.85,
      "ivafe_eur": 30.00,
      "price_date": "2024-12-30"
    }
  ]
}
```

### Tax Years
```
GET /tax/years
```
Returns a list of years that have at least one fiscal event.

### Sell Simulator
```
GET /tax/simulate?asset_id=42&quantity=10&account_id=1
```
Returns estimated tax impact of a hypothetical sale at the current price, at weighted average cost. With `account_id` the cost of that account's pool is used (administered) or the declaratory pool; without it, the average of all pools for the asset.

### Fiscal PDF Export
```
GET /tax/export/pdf?year=2024
```
Returns a PDF report (`application/pdf`) containing the full fiscal summary for the requested year:
- Regime comparison table (administered vs declaratory)
- Quadro RT (capital gains — for declaratory accounts)
- Quadro RW (IVAFE — for foreign accounts)
- Redditi da capitale (income by category)
- Loss carryforward (zainetto fiscale)
- Full fiscal events table
- Legal disclaimer

---

## Dividends
```
GET /dividends?year=2024
```
Returns dividend/coupon/interest income aggregated by month and asset.

---

## Watchlist
```
GET    /watchlist                  # list user's watchlist
POST   /watchlist                  # add asset
PATCH  /watchlist/{id}             # update note or target_price
DELETE /watchlist/{id}             # remove from watchlist
```

**POST body:**
```json
{ "asset_id": 42, "note": "Wait for 10% correction", "target_price": 95.00 }
```

---

## AI

### Chatbot prompt
```
GET /ai/prompt?mode=analysis&lang=it&include_values=true&account_id=1&asset_type=ETF
```
| Param | Values | Default | Notes |
|---|---|---|---|
| `mode` | `analysis` \| `portfolio` | `analysis` | `portfolio` = data only; `analysis` = data + analysis instructions |
| `lang` | `it` \| `en` \| `fr` \| `de` | `it` | Language of the instructions / answer |
| `include_values` | bool | `true` | `false` omits all EUR amounts, keeping weights and percentages |
| `account_id`, `asset_type` | optional | — | Filters |

Response: `{ "prompt": "..." }` (Markdown tables).

### MCP access tokens
```
GET    /ai/mcp-tokens            # { enabled, path, tokens: [...] } — active tokens, never the secret
POST   /ai/mcp-tokens            # { name, can_read_values } → token returned in clear ONCE
DELETE /ai/mcp-tokens/{id}       # revoke
```

### MCP server
`POST /api/mcp` — Streamable HTTP transport (stateless, JSON responses), header `Authorization: Bearer nfmcp_…`.
Without a valid token: `401` with `WWW-Authenticate: Bearer realm="nextfolio-mcp"`.

Read-only tools: `get-portfolio`, `get-allocation`, `get-accounts`, `get-transactions`, `get-performance`,
`get-risk-metrics`, `get-xray`, `get-dividends`, `get-watchlist`, `get-tax-report`.
Tokens without `can_read_values` get percentages only (`get-tax-report` is refused).

```bash
claude mcp add --transport http nextfolio https://nextfolio.example.com/api/mcp \
  --header "Authorization: Bearer nfmcp_..."
```

---

## Alerts
```
GET    /alerts
POST   /alerts
PATCH  /alerts/{id}
DELETE /alerts/{id}
```

**Alert types:** `PRICE_ABOVE`, `PRICE_BELOW`, `CHANGE_PCT_UP`, `CHANGE_PCT_DOWN`

---

## FX Rates
```
GET /fx/rate?from=USD&to=EUR&date=2024-06-01
```
Returns the exchange rate from ECB (Frankfurter API).

---

## Import / Export

### Import CSV
```
POST /import/csv
Content-Type: multipart/form-data
```
Supported formats: Fineco, Directa Plus, Degiro, Interactive Brokers Flex Query.

### Import Ghostfolio
```
POST /import/ghostfolio
Content-Type: application/json
```

### Export Excel
```
GET /portfolio/export
```
Returns an Excel workbook with three sheets: Transactions, Positions, Info.

### Export PDF (Portfolio)
```
GET /portfolio/export/pdf
```
Returns a PDF portfolio report (positions + all transactions).

### Export Ghostfolio
```
GET /portfolio/export/ghostfolio
```

### Export Nextfolio Backup
```
GET /portfolio/export/nextfolio
```

---

## Admin (Superadmin only)

```
GET    /admin/users
POST   /admin/users
PATCH  /admin/users/{id}
DELETE /admin/users/{id}
POST   /admin/users/{id}/reset-2fa
```

---

## User Settings
```
GET   /settings
PATCH /settings
```
**Patchable fields:** `theme`, `display_currency`, `zen_mode`, `language`

---

## WebSocket — Real-Time Prices

```
WS /ws/prices?token=<access_token>
```

The server pushes price updates whenever Celery fetches new prices:
```json
{
  "type": "price_update",
  "data": [
    { "asset_id": 1, "price": 115.20, "change_pct": 0.43, "exchange_rate": 1.0 }
  ]
}
```

Clients can update their subscription at runtime:
```json
{ "action": "subscribe", "asset_ids": [1, 2, 3] }
```

---

## Error Responses

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|---|---|
| 400 | Bad request / validation error |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 422 | Request body validation failed (Pydantic) |
| 429 | Rate limit exceeded |
| 503 | External service unavailable (price source down) |
