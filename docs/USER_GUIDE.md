# Nextfolio — User Guide

> This guide covers every feature available in Nextfolio. It is written for end users — no technical background is required.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Accounts](#2-accounts)
3. [Assets](#3-assets)
4. [Transactions](#4-transactions)
5. [Dashboard](#5-dashboard)
6. [Performance](#6-performance)
7. [Allocations](#7-allocations)
8. [Dividends](#8-dividends)
9. [Tax (Fiscale)](#9-tax-fiscale)
10. [X-Ray](#10-x-ray)
11. [Watchlist](#11-watchlist)
12. [Rebalancing](#12-rebalancing)
13. [Alerts](#13-alerts)
14. [Tools (Strumenti)](#14-tools-strumenti)
15. [Import & Export](#15-import--export)
16. [Settings](#16-settings)
17. [Administration](#17-administration)

---

## 1. Getting Started

### First Login

1. Navigate to the Nextfolio URL provided by your administrator.
2. If no users exist yet, register on the login page — the first user becomes **Superadmin** automatically.
3. Enter your email and password. If your account has **Two-Factor Authentication (2FA)** enabled, you will be prompted for a 6-digit TOTP code after the password.
4. Check **Remember Me** to stay logged in for 30 days without re-entering your password.

### Navigation

The sidebar (desktop) or bottom bar (mobile) provides access to all sections:

| Icon | Section | Description |
|---|---|---|
| House | Dashboard | Portfolio overview |
| TrendingUp | Performance | P&L history |
| BarChart2 | Allocations | Asset-class and geographic breakdown |
| Calendar | Dividends | Income history |
| FileText | Fiscale | Italian tax report |
| ScanSearch | X-Ray | Portfolio health check |
| Eye | Watchlist | Monitored assets |
| Scale | Rebalancing | Portfolio rebalancing suggestions |
| Bell | Alerts | Price alerts |
| Wrench | Strumenti | Tools: calculator, import, export |
| Settings | Settings | Personal preferences, accounts, 2FA |

### Language and Theme

Go to **Settings → Preferences** to change:
- **Display currency** — the currency shown in all amounts
- **Theme** — Light, Dark, or System
- **Language** — Italian, English, French, German
- **Zen Mode** — masks all EUR amounts (useful for screen sharing or screenshots)

---

## 2. Accounts

Accounts represent your brokerage or bank accounts. Each transaction is linked to one account.

### Creating an Account

Go to **Settings → Investment Accounts** and click **New Account**.

| Field | Description |
|---|---|
| Name | A label, e.g. "Fineco Main" or "DEGIRO ETF" |
| Currency | The account's native currency (default: EUR) |
| Type | BROKERAGE, BANK, CRYPTO, PENSION, OTHER |
| Broker / Institution | Free-text label, e.g. "Fineco" |
| Account URL | Optional link to your broker's portal — a favicon appears next to the account name |
| **Sostituto d'imposta** | Toggle ON if your broker automatically handles Italian taxes (administered regime — PMC cost basis). Toggle OFF for foreign brokers where you declare taxes yourself (declaratory regime — FIFO cost basis) |
| **Foreign account** | Toggle ON if the account is held at a non-Italian intermediary (e.g. DEGIRO, Interactive Brokers). This enables IVAFE (0.2% annual tax) calculation for that account |

### Fiscal Regime Badges

Each account row shows colour-coded badges:

- **Green "Reg. amministrato"** — sostituto d'imposta ON — broker handles taxes, PMC method
- **Orange "Reg. dichiarativo"** — sostituto d'imposta OFF — you declare in modello Redditi PF, FIFO method
- **Blue "Estero"** — foreign account — subject to IVAFE calculation

> **Italian tax note:** Most Italian brokers (Fineco, Directa Plus, Banca Mediolanum) are sostituto d'imposta. Foreign brokers (DEGIRO, Interactive Brokers, Coinbase) are not — you must report gains and dividends in your annual tax return (modello Redditi PF, quadri RT / RW / RL).

---

## 3. Assets

Assets are the financial instruments you trade: stocks, ETFs, bonds, crypto.

### Adding an Asset

When creating a transaction, type the asset's **ISIN**, **ticker**, or **name** in the search box. Nextfolio searches its database automatically. If the asset is not found, click **Add manually** and fill in the details.

### Asset Types

| Type | Examples | Tax rate |
|---|---|---|
| STOCK | ENI.MI, AAPL | 26% |
| ETF | IE00B4L5Y983 | 26% |
| BOND (Italian gov.) | BTP, BOT, CCT — ISIN starts with IT | 12.5% |
| BOND (other) | Corporate bonds | 26% |
| CRYPTO | BTC, ETH | 26% |
| CASH | EUR deposits | — |

---

## 4. Transactions

Transactions are the raw ledger entries that drive all portfolio calculations. There is no pre-aggregated state — everything (P&L, tax, allocations) is computed from transactions at query time.

### Transaction Types

| Type | Description |
|---|---|
| BUY | Purchase of an asset |
| SELL | Sale of an asset |
| DIVIDEND | Cash dividend received |
| COUPON | Bond coupon payment |
| INTEREST | Interest income |
| FEE | Standalone fee or commission |
| DEPOSIT | Cash deposit into the account |
| WITHDRAWAL | Cash withdrawal |

### Creating a Transaction

1. Go to **Transactions** and click **+**.
2. Select **Account**, **Asset**, and **Transaction type**.
3. Fill in **Date**, **Quantity**, **Price**, and **Fee**.
4. For non-EUR assets, enter the **Exchange rate** (EUR per 1 unit of the asset's currency). Click the FX button to auto-fill the ECB rate for the transaction date.

### Editing / Deleting

Click the **⋮ kebab menu** on any transaction row to edit or delete it.

### Kebab menu quick actions

- **Edit** — modify any field of the transaction
- **Duplicate** — create a copy of the transaction (useful for regular DCA purchases)
- **Delete** — permanently remove the transaction (this recalculates all P&L)

---

## 5. Dashboard

The Dashboard is the home screen. It shows the current state of your portfolio.

### KPI Cards

| Card | Description |
|---|---|
| Portfolio Value | Total market value of all open positions |
| Invested | Total cost of all open positions (sum of BUY costs) |
| Unrealized P&L | Difference: market value − invested |
| Daily Change | Today's price movement in EUR and % |
| Performance (period) | P&L over the selected period |

### Period Selector

The global period selector (top right) filters the Performance card and the P&L chart. Available periods: 1W, 1M, 3M, 6M, 1Y, YTD, Max.

### Charts and Breakdown

- **Portfolio chart** — cumulative value over the selected period
- **Allocation pie** — breakdown by asset type (or platform, currency, geography)
- **Per-account breakdown** — stacked bar showing each account's contribution
- **Top holdings** — list of largest positions by market value

### Price Ticker

A real-time scrolling ticker at the bottom shows live prices for all your holdings via WebSocket.

---

## 6. Performance

The Performance page shows your portfolio's financial return over time.

### Metrics

| Metric | Description |
|---|---|
| Total Return | (Market value − Invested) / Invested |
| IRR / XIRR | Internal Rate of Return accounting for cash-flow timing |
| Unrealized P&L | Open positions gain/loss |
| Realized P&L | Closed positions gain/loss |
| Benchmark | Comparison vs MSCI World or FTSE MIB |

### Charts

- **P&L chart** — portfolio value vs. invested capital over time
- **Benchmark chart** — portfolio vs. benchmark index (rebased to 100 at start)

### Risk Metrics

| Metric | Description |
|---|---|
| Annualised Volatility | Standard deviation of daily returns × √252 |
| Maximum Drawdown | Largest peak-to-trough decline |
| Sharpe Ratio | Return per unit of risk (risk-free rate = 0) |
| Sortino Ratio | Return per unit of downside risk |
| Calmar Ratio | Annualised return / Max drawdown |

---

## 7. Allocations

The Allocations page shows where your money is invested, with interactive donut charts.

### Breakdown dimensions

| Tab | Groups by |
|---|---|
| Asset Type | STOCK, ETF, BOND, CRYPTO, CASH |
| Platform | Each investment account |
| Currency | EUR, USD, GBP, etc. |
| Asset Class | Equities, Fixed Income, Alternatives |
| Exchange | MIL, NASDAQ, NYSE, etc. |
| Sector | Technology, Healthcare, etc. |
| Geography | Country and continent (via ETF look-through) |

### ETF Look-Through

For ETFs, Nextfolio applies **look-through**: it reads the ETF's underlying holdings (countries, sectors) and includes them in the geographic and sector breakdowns, giving you a true view of your real-world exposure.

### Stacked allocation bar

Each account is shown as a stacked bar so you can see at a glance how each broker contributes to the total.

---

## 8. Dividends

The Dividends page tracks all income received from your portfolio.

### Summary cards

- **Total income this year** — sum of DIVIDEND, COUPON, INTEREST transactions in the current year
- **Income last year** — same for the previous year
- **Yield on cost** — total income / total invested
- **Average monthly income** — average over the last 12 months

### Monthly calendar

A bar chart showing monthly income. Hover over a month to see a breakdown by asset.

### Income table

Sortable table of all dividend/coupon/interest transactions with asset, date, amount, and type.

---

## 9. Tax (Fiscale)

The Fiscale page is the most comprehensive tax reporting tool in Nextfolio. It covers Italian taxation for both administered and declaratory-regime accounts.

### Year selector

Use the dropdown at the top right to select the tax year. Click **PDF fiscale** to download a print-ready PDF of the entire fiscal report for that year.

### KPI Cards

| Card | Description |
|---|---|
| Imposta dovuta | Total estimated capital gains tax (standard + govt-bond brackets) |
| Plusvalenze totali | Gross capital gains across all accounts |
| Minusvalenze totali | Gross capital losses across all accounts |
| Zainetto disponibile | Loss carryforward available from prior years |

### Dichiarazione assistita (Declaration helper)

This collapsible section appears when you have declaratory-regime or foreign accounts. It maps calculated figures to the Italian tax form:

| Quadro | Rigo | What to enter |
|---|---|---|
| RT | RT21, RT22, RT26 | Capital gains/losses and tax at 26% (declaratory) |
| RT | RT51, RT52, RT55 | Capital gains/losses and tax at 12.5% — BTP/BOT/CCT |
| RW | RW5, RW12 | Foreign asset value at Dec 31 and IVAFE due |
| RL | RL1, RL2 | Declaratory dividends and their withholding tax |

Click the **⎘** (copy) button next to any figure to copy it to the clipboard.

> **Disclaimer:** Values are estimates computed with FIFO/PMC. Always cross-check with your broker's official tax report and consult a tax advisor for your final declaration.

### Regime Breakdown Cards

Two side-by-side cards show:
- **Green card — Gestito dal broker:** capital gains and income tax handled by your administered-regime broker. No action needed from you.
- **Orange card — Da dichiarare nel 730:** capital gains and income from declaratory-regime accounts. These must be declared in your annual tax return.

### Bracket cards (Quadro RT detail)

Two expandable brackets:
- **Standard (26%):** equities, ETFs, corporate bonds, crypto
- **Titoli di Stato (12.5%):** BTP, BOT, CCT — Italian government bonds

Each bracket shows:
- Gross gains and losses for the year
- Loss carryforward applied from previous years
- Net taxable amount
- Tax due
- New losses to carry forward (with expiry year)

### Income section (Redditi da capitale)

Shows each income type (dividends, BTP coupons, corporate-bond coupons, interest) with:
- Gross amount received
- **↳ Ritenuta stimata** — estimated withholding tax per type (26% or 12.5%)
- Total estimated withholding across all income types

For administered-regime accounts, the broker has already applied these withholdings. For declaratory accounts, these amounts must be declared.

### IVAFE (Foreign asset tax)

Shown as a blue card when you have accounts marked as **Foreign**. For each asset held in a foreign account at December 31, it shows:
- Asset name
- Market value at Dec 31 (using the last available price in the database)
- IVAFE = market value × 0.2%

### Sell simulator

Enter an asset and a quantity. The simulator estimates:
- Sale proceeds at the current price
- Cost basis (FIFO or PMC depending on the account)
- Estimated capital gains tax
- Net proceeds after tax

### Loss carryforward history

A multi-year table showing minusvalenze available from past years, including:
- The year the loss was generated
- Amount still available
- Expiry year (losses expire after 4 years)

### Events table

A detailed collapsible table of all fiscal events in the year (SELL, DIVIDEND, COUPON, INTEREST) showing:
- Date, asset, type, quantity
- Proceeds and cost (for SELL)
- Gain/loss
- Tax bracket and rate
- Regime badge (administered / declaratory)
- Calculation method badge (PMC / FIFO) — for SELL events only

### Fiscal PDF export

Click **PDF fiscale** in the top right. The PDF contains:
1. Intestazione brand + year + generation date
2. Riepilogo regime (administered vs declaratory comparison table)
3. Quadro RT — capital gains figures for the tax form
4. Quadro RW — IVAFE breakdown by asset
5. Redditi da capitale — income by category with estimated withholding
6. Zainetto fiscale — loss carryforward with expiry dates
7. Full events table with PMC/FIFO method
8. Legal disclaimer

---

## 10. X-Ray

X-Ray analyses your portfolio against 10 rules and gives an overall health score (0–100%).

### Score

The score is the percentage of rules that pass (status = OK). Rules are grouped into categories:

### Category: Concentration

| Rule | Threshold | Description |
|---|---|---|
| Single asset | max 20% | No single holding should exceed 20% of the portfolio |
| Single account | max 80% | No single broker should hold more than 80% |
| Crypto exposure | max 10% | Cryptocurrency should not exceed 10% |

### Category: Asset Class

| Rule | Target range | Description |
|---|---|---|
| Equities + ETF | 50–80% | Core equity exposure |
| Bonds | 5–30% | Fixed income allocation |
| EUR currency | min 30% | Minimum home-currency exposure |

### Category: Fee

| Rule | Threshold | Description |
|---|---|---|
| Fee ratio | max 1.5% | Total fees / total invested |

### Category: Geographic diversification

| Rule | Threshold | Description |
|---|---|---|
| Continent concentration | max 70% | No single continent should dominate |
| Home bias | max 50% | European/Italian overexposure check |

### Category: Liquidity

| Rule | Description |
|---|---|
| Emergency fund | Checks for presence of short-duration bonds or cash |

### Status indicators

- **✅ OK** — rule passes
- **⚠️ Warning** — approaching the threshold
- **❌ Error** — threshold exceeded
- **ℹ️ Info** — informational rule (no pass/fail)

---

## 11. Watchlist

The Watchlist lets you monitor assets you don't own yet (or are considering buying).

### Adding an asset

Click **+ Aggiungi** and search by ISIN, ticker, or name. Optionally add:
- **Note** — your investment thesis or reminder
- **Target price** — the price at which you'd consider buying

### Watchlist table

Each row shows:
- Current price and daily change %
- Distance from your target price (if set)
- A **"Vicino al target"** badge (green) when the price is within 5% of your target
- Edit and delete buttons

---

## 12. Rebalancing

Rebalancing suggests trades to bring your portfolio back in line with your target allocation.

### Setting targets

Use the four sliders at the top of the X-Ray page to set your target percentages for:
- Equities (azioni + ETF)
- Bonds (obbligazioni)
- Crypto
- Other

The sliders always sum to 100%.

### Cash available

Optionally enter how much cash you have available to deploy.

### Trade suggestions

The table shows, for each position that is over- or under-weight:
- **Action** — Buy or Sell
- **Amount (EUR)** — how much to buy/sell to reach the target
- **Current %** and **Target %**

---

## 13. Alerts

Alerts notify you (via email or in-app) when a price crosses a threshold.

### Alert types

| Type | Trigger |
|---|---|
| PRICE_ABOVE | Asset price rises above the threshold |
| PRICE_BELOW | Asset price falls below the threshold |
| CHANGE_PCT_UP | Asset rises more than X% in one day |
| CHANGE_PCT_DOWN | Asset falls more than X% in one day |

### Creating an alert

1. Go to **Alerts** and click **+ Nuovo alert**.
2. Search for an asset.
3. Select the alert type and enter a threshold.
4. Click Save.

Alerts fire at most once every 4 hours (cooldown) to avoid notification spam. When an alert fires, it shows a **"Scattato"** badge and sends an email if SMTP is configured.

---

## 14. Tools (Strumenti)

### PAC Calculator (Piano di Accumulo)

Simulate a recurring investment plan:
1. Enter a **monthly investment** amount
2. Enter an **expected annual return** (%)
3. Enter the **investment duration** (years)
4. The calculator shows the projected final value and total invested

### Sell Simulator

See [Tax → Sell simulator](#sell-simulator) — the same simulator is also accessible from the Tools page.

### Correlation Matrix

A Pearson correlation heatmap between all your portfolio assets. Values range from -1 (perfect negative correlation) to +1 (perfect positive correlation). Assets with low or negative correlation provide the best diversification benefit.

---

## 15. Import & Export

### Importing transactions

Go to **Strumenti → Import** and select your broker format:

| Format | How to export from your broker |
|---|---|
| Fineco | Account → Estratto conto → Export CSV |
| Directa Plus | Portafoglio → Movimenti → Export CSV |
| Degiro | Account → Activity → Export CSV |
| Interactive Brokers | Reports → Flex Query → Create a custom Flex Query and export CSV |

Upload the CSV file. Nextfolio auto-detects the format, maps columns, and creates the transactions. A preview is shown before committing.

### Exporting

From **Strumenti → Export**:

| Export | Contents | Format |
|---|---|---|
| Excel portfolio | Transactions sheet, Positions sheet, Info sheet | .xlsx |
| PDF portfolio | Brand report with positions and all transactions | .pdf |
| **PDF fiscale** | Tax report for the selected year (RT, RW, RL, events) | .pdf |
| Ghostfolio | All transactions in Ghostfolio-compatible format | .json |
| Nextfolio backup | Complete data backup | .json |

The **PDF fiscale** button is also available directly from the **Fiscale** page header, next to the year selector.

---

## 16. Settings

### Preferences

| Setting | Description |
|---|---|
| Display currency | Currency for all displayed amounts (portfolio stored in EUR; conversion is for display only) |
| Theme | Light / Dark / System |
| Language | Italiano / English / Français / Deutsch |
| Zen Mode | Hides all EUR amounts — toggle from the sidebar or Settings |

### Two-Factor Authentication (2FA)

1. Click **Configura 2FA** in Settings.
2. Scan the QR code with your authenticator app (Google Authenticator, Aegis, Authy, etc.).
3. Enter the 6-digit code shown in the app to confirm activation.
4. To disable, enter a valid TOTP code and click **Disattiva**.

If you lose access to your 2FA device, ask your Superadmin to reset 2FA for your account from the Administration panel.

### Investment Accounts

See [Accounts](#2-accounts) — account creation, fiscal regime, and foreign account flags are all managed here.

---

## 17. Administration

The Administration panel is visible only to **Superadmin** users.

### User management

| Action | Description |
|---|---|
| Create user | Add a new user by email, name, and role |
| Edit user | Change name, email, or role |
| Reset 2FA | Disable a user's TOTP requirement (use if they lose their device) |
| Delete user | Permanently remove a user and all their data |

### Email configuration

The **Email** section shows the current SMTP configuration and allows you to:
- Test the SMTP connection
- Send a test email to yourself
- Re-send a welcome email to a user
- Generate a password-reset link manually (useful if the user's email is not working)

### Public registration

By default, only Superadmins can create new accounts. If you enable **public registration**, users can sign up themselves. Registration requires email verification (OTP sent by email).

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `G` then `D` | Go to Dashboard |
| `G` then `T` | Go to Transactions |
| `G` then `F` | Go to Fiscale |
| `?` | Show keyboard shortcuts |

---

## Frequently Asked Questions

**Q: Why is my portfolio value different from my broker's?**  
A: Prices are fetched from Yahoo Finance, Borsa Italiana, and CoinGecko. There can be a few minutes of delay compared to real-time broker feeds. For bonds, the last available price in the database may be from the previous trading day.

**Q: The tax calculation differs from my broker's statement. Why?**  
A: Nextfolio uses FIFO (declaratory regime) or PMC/WAC (administered regime), but the exact calculation may differ due to fee treatment, rounding, or data differences. Always verify against your broker's official tax report and consult a tax advisor.

**Q: I enabled "Sostituto d'imposta" on my account. What changes?**  
A: The cost basis method switches from FIFO to PMC (Weighted Average Cost). Capital gains for this account are shown under "Gestito dal broker" and are not included in the figures you need to declare in your 730.

**Q: I enabled "Conto estero" (Foreign account). What happens?**  
A: The IVAFE section in the Fiscale page will show a 0.2% annual tax estimate based on the market value of assets in that account at December 31. You must declare this in quadro RW of your modello Redditi PF.

**Q: How do I add a price for an asset that isn't found automatically?**  
A: Go to the asset's detail page and use the **backfill** button to request a historical price fetch. For assets not covered by any price source, you can enter manual transactions at the current market price.

**Q: Can I use Nextfolio with multiple brokers?**  
A: Yes — create one account per broker. Each account can have its own fiscal regime (administered or declaratory) and currency. All accounts are aggregated in the Dashboard and performance views.

**Q: Is my data private?**  
A: Nextfolio is self-hosted — your financial data never leaves your server. Zen Mode also lets you hide amounts when sharing your screen or taking screenshots.
