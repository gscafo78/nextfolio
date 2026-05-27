# 🚀 Nextfolio — Roadmap di Sviluppo

> App di wealth management internazionale con focus sul mercato italiano.
> Stack: **React + TypeScript** (frontend) · **FastAPI + Python** (backend) · **PostgreSQL + Redis**

---

## Struttura del progetto

```
nextfolio/
├── frontend/                  # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/          # API calls
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                   # FastAPI + Python
│   ├── app/
│   │   ├── api/               # Route handlers
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── market_data/
│   │   │   ├── portfolio/
│   │   │   └── tax/           # Tax engine italiano
│   │   ├── tasks/             # Celery async tasks
│   │   └── main.py
│   ├── alembic/               # Database migrations
│   ├── tests/
│   └── requirements.txt
│
├── docker-compose.yml
├── docker-compose.dev.yml
└── README.md
```

---

## FASE 1 — Setup e infrastruttura base ✅
**Durata stimata: 1–2 settimane**
**Obiettivo: ambiente funzionante, autenticazione, DB schema**

### 1.1 Ambiente di sviluppo

- [x] Inizializzare il monorepo (`git init`, `.gitignore`, `README.md`)
- [x] Creare `docker-compose.dev.yml` con PostgreSQL 15 e Redis 7
- [x] Configurare VS Code workspace (`.vscode/settings.json`, estensioni consigliate)
- [x] Aggiungere `.env.example` con tutte le variabili necessarie

**Estensioni VS Code da installare:**
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "dbaeumer.vscode-eslint",
    "ms-azuretools.vscode-docker",
    "mtxr.sqltools",
    "mtxr.sqltools-driver-pg"
  ]
}
```

### 1.2 Backend — FastAPI scaffold

- [x] Creare virtual environment Python (`python -m venv venv`)
- [x] Installare dipendenze: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic`, `python-jose`, `passlib`, `celery`, `redis`, `yfinance`, `httpx`
- [x] Configurare `main.py` con CORS, middleware, e router
- [x] Configurare connessione PostgreSQL via SQLAlchemy async
- [x] Creare primo migration Alembic (tabelle `users`, `accounts`)
- [x] Implementare autenticazione JWT (register, login, refresh token)
- [x] Aggiungere endpoint `/health` e `/api/v1/auth/*`

### 1.3 Frontend — React scaffold

- [x] Scaffold Vite + React + TypeScript (creato manualmente, npm non disponibile nell'ambiente)
- [x] Installare: `tailwindcss`, `react-router-dom`, `@tanstack/react-query`, `axios`, `recharts`, `react-hook-form`, `zod`
- [x] Configurare Tailwind CSS e design system base
- [x] Creare layout principale (Sidebar, TopBar, MainContent)
- [x] Implementare pagine Login e Register
- [x] Configurare React Query client e Axios interceptors (JWT auto-refresh)
- [x] Proteggere le route con `PrivateRoute`

### 1.4 Schema database iniziale

```sql
-- Tabelle create nella FASE 1 (migration 0001)
users           (id, email, password_hash, name, currency, is_active, created_at)
accounts        (id, user_id, name, type, broker, currency, created_at)
```

---

## FASE 2 — Asset e transazioni ✅
**Durata stimata: 2–3 settimane**
**Obiettivo: inserire e gestire transazioni su tutti i tipi di asset**

### 2.1 Modello dati asset italiani

- [x] Tabella `assets` con supporto ISIN italiano
- [x] Tipi supportati: `STOCK`, `ETF`, `BOND`, `CRYPTO`, `COMMODITY`, `REIT`
- [x] Campi specifici IT: ISIN, mercato (`MIL`, `EuroTLX`, `MOT`), valuta EUR
- [x] Tabella `transactions` (BUY, SELL, DIVIDEND, COUPON, FEE, INTEREST)
- [x] Tabella `price_history` per storico prezzi

```sql
-- Schema FASE 2 (migration 0002)
assets          (id, isin, symbol, name, type, exchange, currency, sector)
transactions    (id, account_id, asset_id, type, date, quantity, price, fee, currency, notes)
price_history   (id, asset_id, date, open, high, low, close, volume)
```

### 2.2 Backend — API transazioni

- [x] `GET/POST /api/v1/transactions` — lista e creazione
- [x] `PUT/DELETE /api/v1/transactions/{id}` — modifica e cancellazione
- [x] `GET /api/v1/assets/search?q=` — ricerca asset per nome/ISIN/ticker
- [x] `GET /api/v1/accounts` — gestione conti multi-broker
- [x] Validazione ISIN italiano (checksum Luhn ISO 6166 completo)
- [x] Import CSV da broker italiani (Fineco, Directa Plus, Degiro)

**Formato CSV Fineco da supportare:**
```
Data,Descrizione,Divisa,Importo,Tipo
15/03/2024,Acquisto ENI,EUR,-1500.00,BUY
```

### 2.3 Frontend — Pagine transazioni

- [x] Pagina "Portafoglio" con tabella posizioni aperte (in Dashboard)
- [x] Form aggiunta transazione con autocomplete asset (ISIN/ticker) e debounce
- [x] Pagina "Transazioni" con tabella filtrata per data, tipo, account
- [x] Upload CSV con selezione broker e feedback errori
- [x] Componente `AssetBadge` con tipo e borsa colorati

### 2.X Gestione cambio valuta ✅ *(aggiunta extra)*

- [x] Campi `price_currency` e `exchange_rate` sulla transazione (migration 0003)
- [x] Campo `fee_currency` per commissioni in valuta diversa
- [x] `GET /api/v1/fx/rate?from_currency=USD&on_date=2024-03-15` — tasso storico BCE via Frankfurter API
- [x] Form transazione: pannello tasso di cambio visibile solo se asset non è in EUR
- [x] Tasso precompilato dal BCE alla data selezionata, modificabile manualmente
- [x] Riepilogo mostra controvalore in valuta estera + totale in EUR
- [x] Tabella transazioni: colonne "Totale EUR" (calcolato server-side) e "Cambio"

---

## FASE 3 — Market data e prezzi ✅
**Durata stimata: 2 settimane**
**Obiettivo: prezzi aggiornati automaticamente per tutti gli asset**

### 3.1 Integrazione fonti dati

- [x] **Yahoo Finance** (`yfinance`) — azioni Borsa Italiana (suffix `.MI`), ETF, mercati esteri
- [x] **CoinGecko API** — criptovalute (free tier, bulk fetch, storico)
- [ ] **Metals-API / Open Metals** — oro, argento, commodity *(rimandato — richiede API key a pagamento)*
- [x] **Borsa Italiana API** (`grafici.borsaitaliana.it`) — fonte primaria per asset italiani con ISIN: azioni XMIL, ETF EuroTLX, BTP/obbligazioni MOT *(aggiunta extra — ispirata da ghostfolio-feeder)*
- [x] Fallback logic: Borsa Italiana → Yahoo Finance → errore gestito

**Logica selezione fonte:**
```
Asset con ISIN su MIL / EuroTLX / MOT  →  Borsa Italiana API (JWT anonimo)
Asset NYSE / NASDAQ / XETRA            →  Yahoo Finance
Crypto                                 →  CoinGecko
```

**Ticker italiani principali:**
```python
# Yahoo Finance — suffisso .MI per Borsa Italiana
"ENI.MI", "ISP.MI", "ENEL.MI"
# Borsa Italiana API — via ISIN (più affidabile per BTP e obbligazioni)
"IT0005413171:XMIL"   # BTP
"IE00B3RBWM25:ETLX"   # VWCE su EuroTLX
```

### 3.2 Task asincroni con Celery

- [x] Task `update_stock_prices` — ogni 15 min lun-ven 9:00-17:00 (timezone Europe/Rome)
- [x] Task `update_prices_eod` — prezzi di chiusura ogni sera alle 18:30
- [x] Task `update_crypto_prices` — ogni 5 min (mercato 24/7)
- [x] Task `cleanup_old_prices` — pulizia dati oltre 5 anni (ogni domenica)
- [x] Task `backfill_asset_history` — backfill on-demand via API
- [x] Celery Beat per scheduling automatico
- [ ] Flower dashboard per monitoraggio task *(facoltativo — aggiungere container in docker-compose)*

### 3.3 API prezzi e WebSocket

- [x] `GET /api/v1/assets/{id}/price` — prezzo corrente da cache Redis, fallback live
- [x] `GET /api/v1/assets/{id}/history?period=1y&source=db|live` — storico dal DB o live
- [x] `POST /api/v1/assets/{id}/backfill` — avvia backfill storico (Celery, async 202)
- [x] WebSocket `/ws/prices?token=…&asset_ids=1,2,3` — stream live filtrato, sottoscrizione dinamica
- [x] Cache Redis con TTL: 5 min per azioni, 1 min per crypto
- [x] Redis pub/sub per broadcast prezzi ai WebSocket connessi

### 3.4 Frontend — prezzi e grafici

- [x] `services/prices.ts` — client REST prezzi e storico
- [x] `hooks/useLivePrices.ts` — hook WebSocket con subscribe/unsubscribe automatico
- [x] `PriceChart.tsx` — grafico area Recharts con selezione periodo (1S → Max), colore dinamico verde/rosso
- [x] `PriceTicker.tsx` — badge prezzo live con variazione % e icona trend
- [x] Dashboard aggiornata: KPI portafoglio (valore, P&L, variazione oggi), ticker live, tabella posizioni con prezzi real-time

---

## FASE 4 — Calcolo portfolio e performance ✅
**Durata stimata: 2–3 settimane**
**Obiettivo: P&L, rendimenti, allocazione**

### 4.1 Engine di calcolo performance

- [x] **Valore corrente portafoglio** — quantità × prezzo attuale (da cache Redis)
- [x] **P&L realizzato** — gain/loss su posizioni chiuse con metodo **FIFO**
- [x] **P&L non realizzato** — gain/loss su posizioni aperte (vs PMC)
- [x] **TWRR** (Time-Weighted Rate of Return) — prodotto dei sub-return giornalieri
- [x] **IRR / XIRR** — per investimenti con cash flow irregolari *(backend + Performance page)*
- [x] **Dividend yield** — reddito da dividendi e cedole (lista separata)
- [x] **Performance per periodo**: 1S, 1M, 3M, 6M, 1A, 3A, Max

### 4.2 Analisi allocazione

- [x] Allocazione per **tipo asset** (azioni, ETF, obbligazioni, crypto, altro)
- [x] Allocazione per **settore** *(implementata in Fase 4.Z — look-through via Yahoo Finance)*
- [x] Allocazione per **continente** *(look-through via `_COUNTRY_TO_CONTINENT`)*
- [x] Allocazione per **valuta** (EUR, USD, GBP...)
- [x] Allocazione per **broker/conto**
- [x] Concentrazione per singolo titolo (badge warning se > 10%)

### 4.3 API performance

- [x] `GET /api/v1/portfolio/summary` — valore totale, P&L realizzato/non, variazione oggi
- [x] `GET /api/v1/portfolio/performance?period=1y` — serie temporale TWRR
- [x] `GET /api/v1/portfolio/allocation` — breakdown per tipo/valuta/conto
- [x] `GET /api/v1/portfolio/positions` — posizioni aperte con PMC, P&L, cambio giornaliero
- [x] `GET /api/v1/portfolio/dividends` — storico dividendi, cedole e interessi ricevuti
- [x] `GET /api/v1/portfolio/benchmark?index=MSCI_WORLD&period=1y` — serie normalizzata a 100
- [x] `GET /api/v1/portfolio/correlation?period=1y` — matrice correlazione Pearson fra posizioni

### 4.4 Frontend — Pagina Performance e grafici

- [x] **Grafico a torta** — allocazione per tipo asset, valuta, conto (Recharts `PieChart`)
- [x] **Grafico area** — andamento valore portafoglio + capitale investito nel tempo
- [x] **Bar chart** — performance mensile / annuale (Recharts `BarChart`)
- [x] **Tabella posizioni** — asset, qtà, PMC, prezzo attuale, valore, P&L%, P&L€, P&L realizzato
- [x] KPI: P&L totale, P&L non realizzato, P&L realizzato, TWRR %, IRR %
- [x] **Tabella dividendi** — storico con importo EUR, tipo (dividendo/cedola/interesse), conto
- [x] **Benchmark overlay** — MSCI World / FTSE MIB sovrapposto al grafico performance
- [x] **Matrice correlazione** — heatmap interattiva delle correlazioni tra posizioni

### 4.5 Frontend — Pagina Allocazioni ✅ *(aggiunta extra)*

- [x] Rotta `/allocazione` con link sidebar (icona PieChart)
- [x] Barra **Quota del patrimonio netto** (100% del portafoglio, totale EUR)
- [x] Donut **Per Piattaforma** — ripartizione per conto/broker (`by_account`)
- [x] Donut **Per Valuta** — ripartizione per valuta (`by_currency`)
- [x] Donut **Per Classe di Asset** — ripartizione per tipo ETF/Obbligazioni/... (`by_type`)
- [x] Donut grande **Per Holding** — ogni singola posizione con etichette esterne e legenda
- [x] Donut **Per Borsa** — ripartizione per exchange (MIL, XETRA, MOT...)
- [x] Donut **Per Continente** — look-through via `_COUNTRY_TO_CONTINENT`
- [x] Tabella **Holdings ETF/Fondi** — composizione interna espandibile per ETF
- [x] **Override manuale** holdings/settori/paesi per asset (solo superadmin)

---

## FASE 4.X — Autenticazione avanzata e gestione utenti ✅ *(aggiunta extra)*

### 4.X.1 Ruoli utente

- [x] Enum `UserRole` (SUPERADMIN / USER) sul modello `User`
- [x] Primo utente registrato → SUPERADMIN automatico
- [x] Endpoint `POST /auth/register` bloccato se esistono già utenti (HTTP 403)
- [x] Dependency `require_superadmin` su tutte le route admin

### 4.X.2 TOTP (2FA) — opzionale per tutti

- [x] Libreria `pyotp` — generazione secret, URI provisioning, verifica con `valid_window=1`
- [x] `POST /auth/2fa/setup` — genera secret + URI, li salva sul DB (non ancora attivo)
- [x] `POST /auth/2fa/enable` — verifica codice TOTP, attiva 2FA
- [x] `POST /auth/2fa/disable` — verifica codice TOTP, disattiva 2FA e rimuove secret
- [x] **Login con 2FA**: se attivo, `/auth/login` restituisce `{requires_2fa: true, session_token: "..."}`; il client chiama poi `POST /auth/2fa/verify` con il session_token (JWT 5 min, tipo `2fa_session`) e il codice TOTP → token normali
- [x] Frontend: pagina Login a due step (credentials → TOTP) con transizione animata
- [x] Frontend: sezione 2FA in Impostazioni — QR code (`react-qr-code`), codice segreto testuale, attivazione/disattivazione

### 4.X.3 Pannello Amministrazione (solo Superadmin)

- [x] `GET /admin/users` — lista utenti con ruolo, stato, 2FA
- [x] `POST /admin/users` — crea utente con email, password, nome, ruolo
- [x] `PATCH /admin/users/{id}` — modifica ruolo, stato attivo, reset 2FA (`reset_2fa: true`)
- [x] `DELETE /admin/users/{id}` — elimina utente (non se stesso)
- [x] Frontend: pagina `/admin` con tabella utenti, modal crea, modal modifica, elimina con conferma
- [x] Sidebar: link "Amministrazione" visibile solo ai Superadmin
- [x] **Audit log** — tabella `audit_logs` (migration 0010), sezione collassabile con filtro in Admin
- [x] `PATCH /admin/assets/{id}/profile` — override manuale settori/paesi/holdings per ETF

### 4.X.4 Impostazioni personali (tutti gli utenti)

- [x] Tabella `user_settings` (user_id FK, theme, display_currency, updated_at)
- [x] `GET /me/settings` — legge preferenze dell'utente corrente
- [x] `PATCH /me/settings` — aggiorna tema e valuta di visualizzazione
- [x] Frontend: sezione Preferenze in Impostazioni (valuta display + tema)

```sql
-- Aggiunte da migration 0004
users           + role (SUPERADMIN|USER), two_factor_secret, two_factor_enabled
user_settings   (id, user_id, theme, display_currency, updated_at)
```

### 4.X.5 Account URL e favicon ✅ *(aggiunta extra)*

- [x] Campo `url` (String 500, nullable) sulla tabella `accounts` — migration 0012
- [x] `url` aggiunto a `AccountCreate`, `AccountUpdate`, `AccountOut` (Pydantic)
- [x] Frontend: campo URL nel form crea/modifica conto (Impostazioni)
- [x] Componente `AccountFavicon.tsx` — recupera favicon via **Google Favicons API** (`/s2/favicons?domain=...&sz=32`), gestisce assenza con `onError` silenzioso
- [x] Favicon mostrata prima del nome account in: **Impostazioni** (AccountRow), **Transazioni** (summary cards + righe mobile + colonna desktop), **Dashboard** (breakdown per-conto), **HoldingDetailModal** (tab Attività e tab Conti)
- [x] Nome conto cliccabile come link esterno se URL presente

### 4.X.6 Sistema email SMTP ✅ *(aggiunta extra)*

**Backend:**
- [x] Configurazione SMTP in `config.py`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM`, `APP_URL`; proprietà `email_configured: bool`
- [x] `services/email.py` — invio asincrono via `smtplib` + STARTTLS wrappato con `run_in_executor`; template HTML condiviso (`_base(title, body)`)
- [x] Funzioni: `send_password_reset(email, token)`, `send_welcome(email, name, temp_password)`, `send_test(to)`
- [x] `create_password_reset_token(user_id)` in `security.py` — JWT 1h tipo `"password_reset"`
- [x] `POST /auth/forgot-password` — risponde sempre 202 (no timing leak), invia email solo se utente esiste
- [x] `POST /auth/reset-password` — verifica token JWT, aggiorna password
- [x] `GET /admin/email/config` — stato configurazione SMTP (host, porta, mittente)
- [x] `POST /admin/email/test` — invia email di test a indirizzo specificato
- [x] `POST /admin/email/welcome/{user_id}` — invia email di benvenuto con password temporanea
- [x] `POST /admin/email/reset-link/{user_id}` — invia link reset password all'utente

**Frontend:**
- [x] Pagina `ForgotPassword.tsx` (`/forgot-password`) — form email + stato successo
- [x] Pagina `ResetPassword.tsx` (`/reset-password?token=...`) — form nuova password + redirect a `/login` dopo 3s
- [x] Link "Password dimenticata?" nel Login
- [x] `AdminPage`: pulsanti per inviare email benvenuto (con modal password temporanea) e link reset per ogni utente
- [x] `EmailSection` in Impostazioni (solo superadmin): stato SMTP, dettagli configurazione, invio email di test

### 4.X.7 Tema dark / light / sistema ✅ *(aggiunta extra)*

- [x] `darkMode: "class"` in `tailwind.config.js` — attiva varianti `dark:` basate su classe CSS
- [x] Script anti-FOUC in `index.html` — legge `localStorage["nf-theme"]` prima che React monti e aggiunge `dark` sull'`<html>` se necessario
- [x] `ThemeContext.tsx` — `applyTheme(mode)` esportata: togola classe `dark` su `document.documentElement` e persiste in `localStorage`; `ThemeProvider` legge `my-settings`, applica il tema solo dopo il caricamento (evita flash), registra listener `prefers-color-scheme` in modalità "system"
- [x] `index.css` — override `@layer utilities` con selettori `.dark .bg-*` / `.dark .text-*` / `.dark .border-*` / `.dark select,input,textarea` (specificità 0,2,0 > 0,1,0)
- [x] Tutti i componenti layout aggiornati con classi `dark:`: `Sidebar`, `TopBar`, `BottomNav`, `MainLayout`, `Input`, `Button` (variante secondary)
- [x] Selezione tema immediata: `onChange` nel dropdown chiama `applyTheme()` istantaneamente prima di salvare sul backend
- [x] Logo SVG (`assets/logo.svg`) in Sidebar — `Next` bianco + `Folio` verde (#6ee7b7) su sfondo scuro #0f172a, sostituisce la scritta "Nextfolio" in entrambi i temi

---

## FASE 4.Z — Asset enrichment ✅
**Obiettivo: arricchire gli asset con dati settoriali, holdings degli ETF e look-through allocazione**

> Fonte: **Yahoo Finance** (`yf.Ticker.get_funds_data()` per ETF, `yf.Ticker.info` per azioni).
> TrackInsight API inaccessibile (403), rimpiazzata con Yahoo Finance nativamente.

### 4.Z.1 Database ✅

- [x] Migration 0009: campi JSONB su `assets`:
  - `sectors` — `[{"name": "Technology", "weight": 0.24}, ...]`
  - `countries` — `[{"code": "US", "name": "United States", "weight": 1.0}]`
  - `holdings` — `[{"symbol": "AAPL", "name": "Apple Inc", "weight": 0.04}]`
  - `enriched_at` — timestamp ultimo arricchimento
- [x] Migration 0011: campi JSONB override su `assets`:
  - `sectors_override`, `countries_override`, `holdings_override`

### 4.Z.2 Backend — Enrichment service ✅

- [x] `enrich_asset()` in `services/market_data/enricher.py`:
  - ETF/Bond: `get_funds_data().sector_weightings` + `top_holdings` (top 10)
  - Stock/REIT: `info.sector` + `info.country`
  - ISIN resolver: **OpenFIGI** (primario) → Yahoo search (fallback)
- [x] `services/market_data/openfigi.py` — client OpenFIGI con `resolve_isin` / `resolve_isins_bulk`
  - Mappa exchCode → suffisso Yahoo (LN→.L, GR→.DE, IM→.MI, FP→.PA, ...)
  - Selezione exchange ottimale per tipo asset (ETF→London/XETRA, BOND→XETRA/London)
- [x] `OPENFIGI_APY_KEY` in settings + docker-compose.dev.yml
- [x] `POST /api/v1/assets/{id}/enrich` — enrichment singolo
- [x] `POST /api/v1/admin/enrich-assets` — enrichment bulk in background (admin)
- [x] Task Celery `enrich_all_assets`

### 4.Z.3 Backend — Calcolo look-through ✅

- [x] `calculate_allocation()` con `by_sector` (look-through: `position_value × sector_weight`)
- [x] `calculate_allocation()` con `by_continent` (look-through via `_COUNTRY_TO_CONTINENT`)
- [x] `GET /portfolio/etf-holdings` — composizione holdings ETF con override support
- [x] `AllocationOut.by_sector`, `by_continent`: `list[AllocationItem]`

### 4.Z.4 Frontend — Grafici pagina Allocazioni ✅

- [x] Donut **Per Settore** — visibile se dati disponibili (look-through ETF)
- [x] Donut **Per Continente** — look-through via `_COUNTRY_TO_CONTINENT`
- [x] Tabella **Holdings ETF** — espandibile per fondo, top 20 holdings
- [x] **Override modal** — solo superadmin, formato `SYMBOL|Nome|peso%`

---

## FASE 4.W — Performance & ottimizzazioni backend ✅

> Obiettivo: ridurre la latenza degli endpoint `/portfolio/*` percepita al refresh della Dashboard.

### Diagnosi bottleneck (analizzati il 25/05/2026)

| # | Problema | Impatto | Endpoint coinvolti |
|---|----------|---------|-------------------|
| A | Loop `await _price_data(db, asset)` **sequenziale** per N asset | 🔴 Alto — O(N × latenza Redis) | `/positions`, `/summary`, `/allocation` |
| B | Una nuova connessione TCP a Redis per ogni asset (`async with _redis()`) | 🟠 Medio — N handshake inutili | tutti |
| C | `/performance` ricalcolato da zero ad ogni request (TWRR su ~365 punti) | 🟠 Medio — CPU + N query DB | `/performance` |
| D | Dashboard fa 4+ chiamate HTTP separate al caricamento | 🟡 Bonus UX | frontend |

### 4.W.1 Fix A — `asyncio.gather` sui lookup prezzi ✅
- [x] `_fetch_prices_parallel(db, asset_map)`: gather Redis in parallelo, fallback DB solo su cache miss
- **Risultato atteso**: con cache Redis calda, latenza da O(N×1ms) a O(1ms)

### 4.W.2 Fix B — `MGET` bulk Redis ✅
- [x] `get_cached_prices_bulk(asset_ids)` con `r.mget(*keys)` → 1 connessione TCP
- [x] TTL dinamico: 5 min mercato aperto, 4 ore fuori orario/weekend
- **Risultato**: cache fredda ~90–150ms (era ~2s), cache calda ~25ms

### 4.W.3 Fix C — Cache Redis per `/performance` ✅
- [x] Chiave `perf:{user_id}:{period}:{account_id}`, TTL 5 min
- **Risultato**: `period=1y` 224ms cold → 7ms warm (32×)

### 4.W.4 Fix D — Endpoint aggregato `/portfolio/dashboard` ✅
- [x] `GET /portfolio/dashboard` — `{summary, positions, allocation}` in 1 chiamata
- **Risultato**: ~15ms warm (vs ~65ms×N separati)

### 4.W.5 Fix E — Arrotondamento valute a 2 decimali ✅
- [x] Uniformati tutti i prezzi visualizzati a 2 decimali (4 decimali mantenuti solo per tasso di cambio)

---

## FASE 5 — Tax engine italiano 🇮🇹 ✅
**Durata stimata: 2 settimane**
**Obiettivo: calcolo automatico imposte secondo normativa italiana**

### 5.1 Regole fiscali da implementare

- [x] **Capital gain tassabili** — aliquota 26% su plusvalenze
- [x] **Titoli di Stato** (BTP, BOT, CCT) — aliquota agevolata **12,5%** *(identificati via type=BOND + exchange=MOT)*
- [x] **Minusvalenze** — compensabili con plusvalenze entro **4 anni**
- [x] **Zainetto fiscale** — due zainetti separati: standard (26%) e titoli di Stato (12.5%)
- [x] **Dividendi** — mostrati come reddito informativo (aliquota 26%, spesso ritenuta alla fonte)
- [x] **Cedole BTP** — mostrate come reddito informativo (aliquota 12.5%)
- [x] **Crypto** — trattate come bracket standard 26% (normativa post-2023)
- [ ] **PIR** — esenzione fiscale se mantenuto 5 anni *(rimandato — richiede flag su asset/account)*
- [ ] **IVAFE** — imposta 0,2% su attività finanziarie estere *(rimandato — richiede classificazione conti)*

### 5.2 Calcolo FIFO

- [x] Metodo **FIFO** per il calcolo del costo base
- [x] Report per singola operazione con gain/loss dettagliato
- [x] Simulatore "cosa succede se vendo ora?" (`GET /tax/simulate?asset_id=X&quantity=Y`)
- [ ] Metodo **LIFO** *(rimandato — regime dichiarativo)*
- [ ] Metodo **PMC** *(rimandato — regime amministrato)*

### 5.3 API e report fiscali

- [x] `GET /api/v1/tax/years` — anni con eventi fiscali
- [x] `GET /api/v1/tax/report?year=2024` — report annuale con zainetto cumulativo
- [x] `GET /api/v1/tax/simulate?asset_id=1&quantity=10` — simulazione vendita
- [x] Frontend: pagina Fiscale con selettore anno, KPI, due bracket, tabella eventi collassabile
- [x] Frontend: **Simulatore vendita** — sezione in pagina Fiscale con dropdown asset e input quantità
- [x] **Storico minusvalenze multi-anno** — vista dedicata in pagina Fiscale con carryforward visuale
- [ ] **Export PDF** *(rimandato — richiede libreria reportlab)*
- [x] Export Excel incluso nell'export generale (`GET /api/v1/portfolio/export`)

---

## FASE 6 — Features avanzate ✅
**Durata stimata: 2–3 settimane**
**Obiettivo: funzionalità premium e UX avanzata**

### 6.1 Alert e notifiche ✅

- [x] Alert prezzo sopra/sotto soglia (`PRICE_ABOVE`, `PRICE_BELOW`)
- [x] Alert variazione % giornaliera (`CHANGE_PCT_UP`, `CHANGE_PCT_DOWN`)
- [x] Tabella `price_alerts` (migration 0005) con cooldown 4h per evitare spam
- [x] Task Celery `check_price_alerts` — ogni 5 min, confronta prezzo Redis con soglia
- [x] CRUD REST: `GET/POST /alerts`, `PATCH/DELETE /alerts/{id}`
- [x] Frontend: pagina Alert con autocomplete asset, sezioni attivi/disabilitati, badge "scattato"
- [ ] Alert dividendo in arrivo *(rimandato — richiede calendario dividendi esterno)*
- [x] Notifiche email transazionali (reset password, benvenuto utente) — via `smtplib` + STARTTLS *(completato in 4.X.6)*
- [ ] Notifiche email per price alert *(rimandato — SMTP pronto, manca integrazione con task Celery `check_price_alerts`)*
- [ ] Notifiche push via PWA *(rimandato — richiede VAPID backend)*

### 6.2 Strumenti di analisi ✅

- [x] **Calcolatore PAC** — simulazione piano di accumulo con rendimento atteso (pagina `/strumenti`)
- [x] **Simulatore vendita** — impatto fiscale prima di vendere (sezione in pagina Fiscale)
- [x] **Correlazione asset** — matrice Pearson fra i titoli in portafoglio (heatmap)
- [x] **Rischio portafoglio** — volatilità ann., max drawdown, Sharpe, Sortino, Calmar ratio
- [x] **Analisi dividendi** — calendario mensile, yield on cost, crescita storica (pagina dedicata)

### 6.3 Import/Export avanzato ✅

- [x] Import da **Fineco** (CSV estratto conto) *(completato in Fase 2)*
- [x] Import da **Directa Plus** (CSV movimenti) *(completato in Fase 2)*
- [x] Import da **Degiro** (CSV transazioni) *(completato in Fase 2)*
- [x] Import da **Interactive Brokers** (formato Flex Query CSV)
- [x] Export Excel con tutti i dati per uso personale (fogli: Transazioni, Posizioni, Info)
- [x] Export portafoglio in formato **Ghostfolio** (JSON compatibile)
- [ ] **Metals-API / Open Metals** — oro, argento, commodity *(rimandato — API key a pagamento)*

### 6.4 Mobile — Layout responsive e PWA ✅

- [x] **Breakpoint mobile-first** — revisione generale del layout per schermi < 640px
- [x] **Sidebar** → bottom navigation bar su mobile
- [x] **Dashboard** — grafico full-width, KPI cards in colonna singola
- [x] **Holdings table** — card verticali su mobile
- [x] **HoldingDetailModal** — bottom sheet su mobile, side panel su desktop
- [x] **Transazioni** — lista card su mobile
- [x] **Allocazione** — donut chart ridimensionato, legenda sotto
- [x] Form inserimento: `inputMode="decimal"` su tutti i campi numerici
- [x] PWA: `vite-plugin-pwa`, manifest, icone, offline cache
- [ ] Notifiche push per price alert *(rimandato — richiede VAPID)*

---

## FASE 8 — UX / UI Polish e funzionalità extra ✅
**Obiettivo: coerenza visiva, micro-interazioni, privacy e miglioramenti UX trasversali**

### 8.1 Layout e navigazione

- [x] **TopBar consistente su tutte le pagine** — titolo della pagina corrente in ogni vista autenticata (Alert, Fiscale, Strumenti, Import, Admin, Transazioni, Performance, Allocazioni, Dividendi, Dashboard)
- [x] **Rimozione titoli duplicati** — eliminati gli `<h1>` interni alle pagine che ridondavano con la TopBar
- [x] **Pagina Import/Export unificata** — `ExportCard` e `RestoreCard` spostati da Strumenti a Import; label sidebar aggiornata a "Importa / Esporta"

### 8.2 Paginazione Transazioni

- [x] Selettore righe per pagina (10 / 25 / 50 / 100, default 10) allineato a destra nella barra filtri
- [x] Navigazione ← / → con contatore "X–Y di Z"
- [x] Reset automatico alla prima pagina al cambio di filtro o page size

### 8.3 Allocazioni interattive

- [x] **Stacked allocation bar** — barra segmentata per conto/piattaforma in sostituzione della barra statica al 100%; al hover i segmenti non attivi si attenuano; tooltip con nome e %
- [x] **Mini progress bar nelle leggende** — ogni voce dei `SmallDonutCard` mostra una barra orizzontale relativa al valore massimo del gruppo

### 8.4 Zen Mode — modalità privacy *(full-stack)*

- [x] Backend: colonna `zen_mode` (Boolean, default `false`) su `user_settings` — migration `0013_zen_mode`
- [x] Schema `UserSettingsOut` / `UserSettingsUpdate` aggiornati con `zen_mode`
- [x] `ThemeContext.tsx` — `AppSettingsContext` espone `useZenMode()` dallo stesso query di `useTheme()`
- [x] Toggle iOS-style in Impostazioni → Preferenze con label e descrizione
- [x] Mascheramento **`"•••••"`** su tutte le pagine con valori EUR:
  - **Dashboard** — KPI, breakdown per-conto, tabella posizioni, colonna P&L
  - **Transazioni** — totali, commissioni, footer, card riepilogo per conto
  - **Performance** — KPI, tabella posizioni (PMC, valore, P&L unrealized/realized/daily), footer totale, dividendi, tooltip e asse Y del grafico
  - **Allocazioni** — totale stacked bar, tooltip donut, valore ETF holdings
  - **Dividendi** — KPI, asse Y grafico, tooltip, tabella per anno, yield on cost
  - **Fiscale** — KPI, Bracket, Row, GainBadge, EventsTable, IncomeSection, SellSimulator, storico minusvalenze
  - **HoldingDetailModal** — header valore corrente, overview stats, tab Attività, tab Conti
- [x] Le percentuali non vengono mai mascherate

### 8.5 Login page redesign

- [x] **Split layout** — pannello sinistro dark con brand (nascosto su mobile), pannello destro bianco con form
- [x] Pannello sinistro: sfondo navy profondo (`#05101f → #0b1a30`), texture dot-grid, glow orbs blu/smeraldo, card portafoglio con live-dot pulsante, headline con gradient, feature pills, ticker strip, grafico area SVG (portafoglio vs investito) decorativo in fondo
- [x] Pannello destro: heading "Bentornato", form pulito, errori in pill-banner, arrow sul CTA; step 2FA con card icona arrotondata; footer copyright
- [x] Responsive: su mobile il pannello sinistro scompare, compare il logo compatto verticale

### 8.6 Favicon e branding

- [x] **Nuovo favicon SVG** — `/public/favicon.svg`: dark navy rounded square, 3 barre crescenti (blu → smeraldo), linea trend bianca, dot smeraldo con glow in cima
- [x] `index.html` aggiornato: `<link rel="icon" type="image/svg+xml">` come prima scelta, PNG 32x32 come fallback per browser legacy

### 8.7 Fix Tailwind palette brand *(bug fix)*

- [x] Aggiunte le sfumature mancanti nel palette `brand` in `tailwind.config.js`: **200, 300, 400, 900** — le classi `bg-brand-400`, `text-brand-400`, ecc. non generavano CSS senza di esse, rendendo le barre di allocazione invisibili

---

## FASE 9 — Internazionalizzazione (i18n) 🌍 ⬜
**Obiettivo: UI completamente multilingua (IT, EN, FR, DE), lingua selezionabile dalle impostazioni utente**

> Librerie: **`i18next`** + **`react-i18next`** + **`i18next-browser-languagedetector`**
> Approccio: namespace unico `common`, file JSON per lingua, cambio senza ricarica pagina.

### 9.1 Backend

- [ ] Migration `0014_language`: colonna `language` (String 5, default `"it"`) su `user_settings`
- [ ] `UserSettingsOut` e `UserSettingsUpdate`: aggiungere campo `language: str | None`
- [ ] Messaggi di errore backend: lasciati in inglese tecnico (già gestiti come codici nel frontend) — refactoring completo rimandato

### 9.2 Setup i18n (Frontend)

- [ ] Installare dipendenze: `i18next react-i18next i18next-browser-languagedetector`
- [ ] Creare `src/i18n.ts` — configurazione con:
  - Namespace: `common` (unico namespace per semplicità)
  - Lingua di fallback: `"it"`
  - Rilevamento automatico da `localStorage["nf-lang"]`
  - Import lazy delle risorse JSON
- [ ] Struttura cartelle:
  ```
  src/locales/
    it/common.json   ← lingua di default (sorgente)
    en/common.json
    fr/common.json
    de/common.json
  ```
- [ ] Integrare `i18next.changeLanguage()` in `AppSettingsContext` — lingua applicata al mount e ad ogni cambio impostazione
- [ ] `src/i18n.ts` importato in `src/main.tsx` prima del render

### 9.3 Struttura chiavi di traduzione

```json
{
  "nav": { "dashboard": "Dashboard", "transactions": "Transazioni", ... },
  "common": { "save": "Salva", "cancel": "Annulla", "loading": "Caricamento...", ... },
  "dashboard": { "totalValue": "Valore portafoglio", "totalPnl": "P&L totale", ... },
  "transactions": { "addTransaction": "Aggiungi transazione", "type": "Tipo", ... },
  "performance": { "openPositions": "Posizioni aperte", "unrealizedPnl": "P&L non realizzato", ... },
  "allocation": { "portfolioComposition": "Composizione portafoglio", ... },
  "dividends": { "totalIncome": "Totale incassato", "currentYear": "Anno corrente", ... },
  "tax": { "taxDue": "Imposta dovuta", "capitalGains": "Plusvalenze totali", ... },
  "settings": { "preferences": "Preferenze", "theme": "Tema", "zenMode": "Zen Mode", "language": "Lingua", ... },
  "errors": { "invalidCredentials": "Credenziali non valide", "invalidCode": "Codice non valido", ... },
  "auth": { "welcome": "Bentornato", "signIn": "Accedi", "forgotPassword": "Password dimenticata?", ... }
}
```

### 9.4 Migrazione stringhe UI

- [ ] `src/components/layout/Sidebar.tsx` — label navigazione
- [ ] `src/components/layout/TopBar.tsx` — titoli pagina
- [ ] `src/pages/Login.tsx` + `ForgotPassword.tsx` + `ResetPassword.tsx`
- [ ] `src/pages/Dashboard.tsx` — KPI label, colonne tabella, header sezioni
- [ ] `src/pages/Transazioni.tsx` — filtri, colonne, form modifica, footer
- [ ] `src/pages/Performance.tsx` — KPI, label grafici, sezioni
- [ ] `src/pages/Allocation.tsx` — titoli card, label legenda
- [ ] `src/pages/Dividendi.tsx` — KPI, label tabella
- [ ] `src/pages/Fiscale.tsx` — bracket label, simulatore, storico
- [ ] `src/pages/Alert.tsx` — form, badge stato
- [ ] `src/pages/Impostazioni.tsx` — sezioni, label campo, descrizioni
- [ ] `src/pages/Import.tsx` + `Strumenti.tsx` + `Admin.tsx`
- [ ] `src/components/transactions/TransactionForm.tsx` — label, validazioni
- [ ] `src/components/portfolio/HoldingDetailModal.tsx` — tab, label stat

### 9.5 Selezione lingua in Impostazioni

- [ ] Sezione "Lingua" in Impostazioni → Preferenze (sotto tema, sopra Zen Mode)
- [ ] UI: 4 pill-button affiancati con codice ISO + nome nativo (`IT · Italiano`, `EN · English`, `FR · Français`, `DE · Deutsch`)
- [ ] `onChange` chiama `i18next.changeLanguage()` immediatamente (senza attendere il salvataggio backend) → cambio istantaneo
- [ ] `updateSettings({ language })` salva su backend; `staleTime: Infinity` sul query `my-settings`

### 9.6 Formato date e numeri per lingua

- [ ] `date-fns/locale` — importare `enUS`, `fr`, `de`, `it` e selezionare in base alla lingua corrente
  - Usato in: Transazioni, Performance (tooltip), HoldingDetailModal, Dividendi
- [ ] Numeri: `toLocaleString()` con `locale` dinamico (es. `"en-US"` → `1,234.56`, `"it-IT"` → `1.234,56`)
  - Wrapper helper `fmtNum(v, locale)` centralizzato in `src/utils/format.ts`

---

**Nota sull'approccio:** l'italiano è la lingua sorgente (tutti i JSON `it/common.json` vengono scritti per primi). Le traduzioni EN/FR/DE sono generate in un secondo momento — finché non disponibili, `i18next` usa il fallback italiano. Non sono necessarie tutte e quattro le lingue per il primo rilascio.

---

## FASE 7 — Qualità e rilascio ✅
**Durata stimata: 1–2 settimane**
**Obiettivo: test, sicurezza, deploy**

### 7.1 Testing

- [x] **Backend**: Pytest unit tests su tax engine — 77 test, 68 pass, 9 skip
- [x] **Backend**: Pytest unit tests su calcolo FIFO posizioni
- [x] **Backend**: Pytest unit tests su performance helpers
- [x] **Backend**: Integration tests API shape validation
- [x] **Bug fix**: `build_annual_reports` carryforward (Art. 68 TUIR)
- [ ] **Frontend**: Vitest per utility functions *(rimandato)*
- [ ] **Frontend**: Playwright E2E *(rimandato)*

### 7.2 Sicurezza

- [x] Rate limiting sulle API (`slowapi`)
- [x] Validazione input con Pydantic
- [ ] HTTPS obbligatorio in produzione *(rimandato — gestito a livello infrastrutturale)*
- [x] Refresh token rotation
- [x] CORS configurato per soli domini trusted
- [x] 2FA TOTP opzionale (`pyotp`)
- [x] Ruoli SUPERADMIN/USER
- [x] Registrazione pubblica bloccata dopo il primo utente
- [x] `bcrypt<4.0` per compatibilità con `passlib`
- [x] Audit log per operazioni sensibili

### 7.3 Docker e deploy

- [x] `Dockerfile` per frontend (nginx multi-stage build)
- [x] `Dockerfile` per backend (Python slim, alembic upgrade automatico)
- [x] `docker-compose.yml` production: porte solo su 127.0.0.1:80
- [x] Variabili d'ambiente documentate in `.env.example`
- [x] Script `scripts/backup-postgres.sh`: dump gzip + rotazione automatica

---

## Dipendenze chiave

### Backend (`requirements.txt`)
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0
pydantic[email]>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
celery[redis]>=5.3.0
redis>=5.0.0
yfinance>=0.2.36
httpx>=0.26.0
pandas>=2.0.0
numpy>=1.26.0
slowapi>=0.1.9
python-multipart>=0.0.9
openpyxl>=3.1.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
```

### Frontend (`package.json` dependencies)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.20.0",
    "axios": "^1.6.0",
    "recharts": "^2.12.0",
    "react-hook-form": "^7.51.0",
    "zod": "^3.22.0",
    "@hookform/resolvers": "^3.3.0",
    "date-fns": "^3.3.0",
    "lucide-react": "^0.344.0",
    "react-qr-code": "^2.0.21"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.1.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^1.3.0",
    "@playwright/test": "^1.42.0"
  }
}
```

---

## Comandi utili per VS Code

```bash
# Avviare l'ambiente di sviluppo completo
docker compose -f docker-compose.dev.yml up -d

# Backend — sviluppo con hot reload
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend — sviluppo con hot reload
cd frontend && npm run dev

# Eseguire migration database
cd backend && alembic upgrade head

# Creare nuova migration
cd backend && alembic revision --autogenerate -m "nome_migration"

# Avviare Celery worker
cd backend && celery -A app.tasks.celery_app:celery_app worker --loglevel=info

# Avviare Celery Beat (scheduler prezzi)
cd backend && celery -A app.tasks.celery_app:celery_app beat --loglevel=info

# Eseguire test backend
cd backend && pytest -v --cov=app

# Eseguire test frontend
cd frontend && npm run test

# Build production
cd frontend && npm run build
docker compose build
```

---

## Milestone e priorità

| Fase | Descrizione | Stato | Priorità | Stima |
|------|-------------|-------|----------|-------|
| 1 | Setup + auth + DB | ✅ Completata | 🔴 Critica | 1–2 sett. |
| 2 | Asset + transazioni + FX | ✅ Completata | 🔴 Critica | 2–3 sett. |
| 3 | Market data + prezzi + WebSocket | ✅ Completata | 🔴 Critica | 2 sett. |
| 4 | Portfolio + performance | ✅ Completata | 🔴 Critica | 2–3 sett. |
| 4.X | 2FA TOTP + ruoli + admin utenti + email + tema + favicon | ✅ Completata | 🟠 Alta | — |
| 4.5 | Pagina Allocazioni (frontend) | ✅ Completata | 🟠 Alta | — |
| 4.W | Performance backend (gather, MGET, cache, dashboard) | ✅ Completata | 🟠 Alta | 1 sett. |
| 4.Z | Asset enrichment (settori, continenti, ETF holdings, override) | ✅ Completata | 🟠 Alta | 2–3 sett. |
| 5 | Tax engine italiano | ✅ Completata | 🟠 Alta | 2 sett. |
| 6 | Features avanzate | ✅ Completata | 🟡 Media | 2–3 sett. |
| 7 | Testing + deploy | ✅ Completata (core) | 🟢 Normale | 1–2 sett. |
| 8 | UX/UI Polish — TopBar, Zen Mode, Login redesign, favicon, paginazione, allocazioni interattive | ✅ Completata | 🟡 Media | — |

**Punti rimandati per scelta:** Metals-API (paid), PIR/IVAFE/LIFO/PMC (complessità contabile), push notifications (VAPID), email per price alert (SMTP pronto, manca integrazione Celery), HTTPS (infra), Vitest/Playwright (frontend testing), Flower (monitoring opzionale).

**Tempo totale stimato: 12–18 settimane** (sviluppo part-time)

---

## Note implementative

### Aggiunte rispetto alla roadmap originale

| Feature | Fase | Motivazione |
|---------|------|-------------|
| Gestione cambio valuta (`price_currency`, `exchange_rate`, `fee_currency`) | 2.X | Necessaria per ETF/azioni in USD, calcolo P.M.C. corretto in EUR |
| Endpoint `GET /fx/rate` — tassi storici BCE (Frankfurter API) | 2.X | Tasso precompilato nel form transazione, modificabile |
| Client Borsa Italiana API (`grafici.borsaitaliana.it`) | 3.X | Fonte ufficiale per BTP/obbligazioni MOT non coperti da Yahoo Finance |
| `POST /assets/{id}/backfill` — backfill storico on-demand | 3.X | Permette di popolare il DB per asset già presenti senza attendere il task EOD |
| `fill_missing_dates` nel client Borsa Italiana | 3.X | Propaga prezzi ai weekend/festivi, coerente con ghostfolio-feeder |
| TOTP 2FA opzionale (pyotp) + login a due step | 4.X | Sicurezza account; flusso session_token per non esporre credenziali nella challenge TOTP |
| Ruoli SUPERADMIN/USER, pannello admin utenti | 4.X | Gestione multi-utente: solo il superadmin crea account; utenti normali configurano solo preferenze personali |
| Tabella `user_settings` (tema, valuta display) | 4.X | Personalizzazione per-utente senza toccare il profilo principale |
| Pagina `/allocazione` con donut chart (holding, piattaforma, valuta, asset class, borsa, settore, continente) | 4.5 | Dashboard allocazione dedicata, ispirata a Ghostfolio; look-through ETF |
| Asset enrichment via Yahoo Finance (paesi, settori, holdings ETF) | 4.Z | Ghostfolio usa TrackInsight + JSON blob su `SymbolProfile`; stessa architettura adattata |
| Audit log (`audit_logs`) | 4.X | Tracciabilità operazioni sensibili per ambienti multi-utente |
| Override manuale settori/countries/holdings | 4.Z | Correzione manuale dati enrichment non accurati (ispirato a Ghostfolio) |
| Export Excel (Transazioni, Posizioni, Info) | 6.3 | Backup e analisi offline dei dati |
| Export formato Ghostfolio | 6.3 | Compatibilità e migrazione |
| Import Interactive Brokers Flex Query | 6.3 | Broker più usato da investitori avanzati |
| Calcolatore PAC + Simulatore vendita | 6.2 | Strumenti decisionali senza dipendenze esterne |
| Risk metrics (volatilità, drawdown, Sharpe, Sortino, Calmar) | 6.2 | Analisi quantitativa del rischio |
| IRR/XIRR | 4.1 | Misura di rendimento più accurata per cash flow irregolari |
| Benchmark MSCI World / FTSE MIB | 4.4 | Confronto con indici di riferimento |
| Correlazione asset (matrice Pearson) | 6.2 | Diversificazione e rischio concentrazione |
| Analisi dividendi (calendario, yield on cost) | 6.2 | Visione income del portafoglio |
| Concentrazione per singolo titolo (badge > 10%) | 4.2 | Alert visivo per rischio concentrazione |
| Storico minusvalenze multi-anno | 5.3 | Compensazione Art. 68 TUIR su 4 anni |
| Campo `url` su `accounts` + favicon Google Favicons API | 4.X.5 | Link diretto al conto broker; favicon come identificatore visivo ovunque appaia il nome conto |
| Sistema SMTP completo (`smtplib` + STARTTLS) | 4.X.6 | Password reset self-service, email benvenuto per nuovi utenti, test configurazione; nessuna dipendenza esterna oltre stdlib |
| Flusso reset password (`/forgot-password`, `/reset-password`) | 4.X.6 | Token JWT 1h tipo `password_reset`; risposta 202 costante per evitare user enumeration |
| Pannello email admin (config, test, welcome, reset link) | 4.X.6 | Operazioni email manuali per il superadmin senza accesso a shell |
| Logo SVG Nextfolio in Sidebar | 4.X.7 | Branding coerente con header email; "Next" bianco + "Folio" verde su sfondo slate-900 |
| Tema dark / light / system (class-based Tailwind) | 4.X.7 | Preferenza persistita su backend (`user_settings.theme`), localStorage per FOUC prevention, cambio immediato senza attesa refetch |
| TopBar consistente + rimozione titoli duplicati | 8.1 | Coerenza visiva su tutte le pagine autenticate; una sola fonte di verità per il titolo |
| Paginazione Transazioni (righe per pagina) | 8.2 | Gestione grandi volumi di transazioni senza degradare le performance del DOM |
| Stacked allocation bar + mini progress bar legenda | 8.3 | Visualizzazione allocazione per conto più intuitiva; replace della barra statica al 100% che non trasmetteva informazione reale |
| Zen Mode (privacy toggle full-stack) | 8.4 | Ispirato a Ghostfolio; permette screenshot/condivisione del portafoglio senza esporre valori assoluti; percentuali sempre visibili |
| Login page redesign — stile broker premium | 8.5 | Primo impatto professionale; layout split con pannello brand dark e grafico decorativo SVG |
| Favicon SVG (barre crescenti + trend line) | 8.6 | Favicon riconoscibile a 16×16; SVG preferito dai browser moderni con PNG fallback |
| Fix palette `brand` Tailwind (200/300/400/900) | 8.7 | Bug silenzioso: le classi senza sfumatura definita non generano CSS; rendeva invisibili barre e indicatori |

### Decisioni architetturali

- **Borsa Italiana come fonte primaria** per tutti gli asset con ISIN su MIL/EuroTLX/MOT; Yahoo Finance come fallback — copre BTP e obbligazioni che Yahoo non gestisce
- **Exchange rate = EUR per 1 unità di valuta estera** (es. 0.9259 EUR/USD): convenzione usata per il calcolo `total_eur = qty × price × exchange_rate`
- **Celery timezone = Europe/Rome**: gli orari di borsa (9:00-17:00) sono in ora locale italiana
- **WebSocket filtra per asset_ids**: il client può aggiornare la sottoscrizione a runtime inviando `{"action": "subscribe", "asset_ids": [1,2,3]}`

---

*Stack: React + FastAPI + PostgreSQL + Redis + Celery*
