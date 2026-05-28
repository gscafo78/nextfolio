# API Reference

Nextfolio exposes a versioned REST API and a WebSocket endpoint for real-time price streaming.

**Base URL:** `http(s)://yourdomain/api/v1`  
**Interactive docs:** available at `/docs` (development mode only — `DEBUG=true`)

---

## Authentication

All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/forgot-password`, and `/auth/reset-password` require a valid Bearer token.

```
Authorization: Bearer <access_token>
```

Access tokens expire in 30 minutes by default. Use `/auth/refresh` to obtain a new one without re-logging in.

---

## Auth

### Register

```
POST /auth/register
```

Creates the first user (Superadmin). Subsequent registrations are disabled — new users must be created by a Superadmin from the Administration page.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "strongpassword",
  "name": "Alice"
}
```

---

### Login

```
POST /auth/login
```

**Body:**
```json
{
  "email": "user@example.com",
  "password": "strongpassword",
  "remember_me": false
}
```

**Response (2FA disabled):**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

**Response (2FA enabled):**
```json
{
  "requires_2fa": true,
  "session_token": "..."
}
```

---

### Verify 2FA

```
POST /auth/verify-2fa
```

**Body:**
```json
{
  "session_token": "...",
  "code": "123456"
}
```

Returns the same `access_token` / `refresh_token` response as a standard login.

---

### Refresh Token

```
POST /auth/refresh
```

**Body:**
```json
{
  "refresh_token": "..."
}
```

---

### Password Reset

```
POST /auth/forgot-password    # sends reset email
POST /auth/reset-password     # consumes token, sets new password
```

---

## Portfolio

### Get Positions

```
GET /portfolio/positions
```

Returns all open positions with FIFO P&L, current prices, and unrealized P&L.

**Response:**
```json
[
  {
    "asset_id": 1,
    "isin": "IE00B4L5Y983",
    "name": "iShares Core MSCI World (Acc)",
    "type": "ETF",
    "quantity": 35.9973,
    "pmc_eur": 107.4792,
    "invested_eur": 3868.96,
    "current_price_eur": 115.20,
    "market_value_eur": 4147.13,
    "realized_pnl_eur": 0.0,
    "unrealized_pnl_eur": 278.17,
    "unrealized_pnl_pct": 7.19
  }
]
```

### Portfolio Summary

```
GET /portfolio/summary
```

Returns aggregated totals: total invested, total market value, realized P&L, unrealized P&L.

### Performance History

```
GET /portfolio/performance?from=2024-01-01&to=2024-12-31
```

Returns time-series portfolio values for charting.

---

## Transactions

### List Transactions

```
GET /transactions?account_id=1&from=2024-01-01&to=2024-12-31&type=BUY
```

Supports pagination (`limit`, `offset`) and filtering by account, date range, and transaction type.

### Create Transaction

```
POST /transactions
```

**Body:**
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
  "currency": "EUR",
  "notes": "Monthly DCA"
}
```

**Transaction types:** `BUY`, `SELL`, `DIVIDEND`, `FEE`, `DEPOSIT`, `WITHDRAWAL`

### Update / Delete Transaction

```
PUT  /transactions/{id}
DELETE /transactions/{id}
```

---

## Assets

### Search Asset

```
GET /assets/search?q=MSCI+World
GET /assets/lookup?isin=IE00B4L5Y983
```

### Get Price

```
GET /prices/{asset_id}
```

---

## Accounts

```
GET    /accounts
POST   /accounts
PUT    /accounts/{id}
DELETE /accounts/{id}
```

---

## Dividends

```
GET /transactions?type=DIVIDEND
```

Dividends are stored as transactions with type `DIVIDEND`.

---

## Tax (Italian)

```
GET /tax/report?year=2024
```

Returns Italian capital gains (minusvalenze/plusvalenze) and dividend income breakdown for the requested tax year.

---

## Import / Export

### Import CSV

```
POST /import/csv
Content-Type: multipart/form-data
```

Upload a CSV file. Supported formats are documented in the import page of the UI.

### Import Ghostfolio

```
POST /import/ghostfolio
Content-Type: application/json
```

Accepts a Ghostfolio-compatible JSON export.

### Export PDF

```
GET /export/pdf?year=2024
```

Returns a PDF portfolio report for the requested year.

---

## Alerts

```
GET    /alerts
POST   /alerts
DELETE /alerts/{id}
```

**Alert body:**
```json
{
  "asset_id": 1,
  "type": "PRICE_ABOVE",
  "threshold": 120.0
}
```

---

## FX Rates

```
GET /fx?from=USD&to=EUR&date=2024-06-01
```

Returns the exchange rate from the ECB (Frankfurter API).

---

## Admin (Superadmin only)

```
GET    /admin/users          # list all users
POST   /admin/users          # create a new user
PUT    /admin/users/{id}     # update user (role, name, email)
DELETE /admin/users/{id}     # delete user
POST   /admin/users/{id}/reset-2fa   # disable 2FA for a user
```

---

## WebSocket — Real-Time Prices

```
WS /ws/prices
```

Connect with a valid access token as a query parameter:

```
ws://yourdomain/ws/prices?token=<access_token>
```

The server pushes a message whenever prices are updated:

```json
{
  "type": "price_update",
  "data": [
    { "asset_id": 1, "isin": "IE00B4L5Y983", "price": 115.20, "change_pct": 0.43 }
  ]
}
```

---

## Error Responses

All errors follow the standard FastAPI format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|---|---|
| 400 | Bad request / validation error |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 422 | Request body validation failed (Pydantic) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

## Rate Limiting

The API is rate-limited via **slowapi** (per-IP). Default limits are configured in `backend/app/core/config.py`. Exceeded limits return HTTP 429.
