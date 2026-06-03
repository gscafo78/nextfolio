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
| `is_sostituto_imposta` | `true` = broker handles Italian taxes (administered regime, PMC cost basis); `false` = user must declare in 730 (declaratory regime, FIFO cost basis) |
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

### Performance History
```
GET /portfolio/performance?from=2024-01-01&to=2024-12-31
```

### Allocation
```
GET /portfolio/allocation
```
Returns breakdown by type, platform, currency, asset_class, exchange, sector, continent. Includes ETF look-through for geography and sector.

### X-Ray
```
GET /portfolio/xray
```
Returns an array of `XRayRule` objects plus an overall `score` (0–100).

**Response:**
```json
{
  "score": 70,
  "rules_total": 10,
  "rules_ok": 7,
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
```

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
GET /tax/simulate?asset_id=42&quantity=10
```
Returns estimated tax impact of a hypothetical sale at the current price.

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
