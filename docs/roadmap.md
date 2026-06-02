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
- [x] Flower dashboard per monitoraggio task — container in `docker-compose.dev.yml`, porta 5555, basic-auth *(completato in FASE 15.1)*

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
- [x] **Export PDF** — `GET /portfolio/export/pdf` via `reportlab`; pagine: intestazione brand, riepilogo, posizioni aperte con zebra-table, tutte le transazioni; pulsante in Import/Export con chiavi i18n IT/EN/FR/DE
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
- [x] Notifiche email per price alert — `send_price_alert()` in `email.py`; task Celery `check_price_alerts` carica `user` via `selectinload` e invia email ad ogni alert scattato; errori SMTP loggati come warning senza interrompere il task; cooldown 4h invariato
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

## FASE 9 — Internazionalizzazione (i18n) 🌍 ✅
**Obiettivo: UI completamente multilingua (IT, EN, FR, DE), lingua selezionabile dalle impostazioni utente**

> Librerie: **`i18next`** + **`react-i18next`** + **`i18next-browser-languagedetector`**
> Approccio: namespace unico `common`, file JSON per lingua, cambio senza ricarica pagina.

### 9.1 Backend

- [x] Migration `0014_language`: colonna `language` (String 5, default `"it"`) su `user_settings`
- [x] `UserSettingsOut` e `UserSettingsUpdate`: aggiungere campo `language: str | None`
- [ ] Messaggi di errore backend: lasciati in inglese tecnico (già gestiti come codici nel frontend) — refactoring completo rimandato

### 9.2 Setup i18n (Frontend)

- [x] Installare dipendenze: `i18next react-i18next i18next-browser-languagedetector`
- [x] Creare `src/i18n.ts` — configurazione con:
  - Namespace: `common` (unico namespace per semplicità)
  - Lingua di fallback: `"it"`
  - Rilevamento automatico da `localStorage["nf-lang"]`
  - Import lazy delle risorse JSON
- [x] Struttura cartelle:
  ```
  src/locales/
    it/common.json   ← lingua di default (sorgente)
    en/common.json
    fr/common.json
    de/common.json
  ```
- [x] Integrare `i18next.changeLanguage()` in `AppSettingsContext` — lingua applicata al mount e ad ogni cambio impostazione
- [x] `src/i18n.ts` importato in `src/main.tsx` prima del render

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

- [x] `src/components/layout/Sidebar.tsx` — label navigazione
- [x] `src/components/layout/TopBar.tsx` — titoli pagina
- [x] `src/pages/Login.tsx` + `ForgotPassword.tsx` + `ResetPassword.tsx`
- [x] `src/pages/Dashboard.tsx` — KPI label, colonne tabella, header sezioni
- [x] `src/pages/Transazioni.tsx` — filtri, colonne, form modifica, footer
- [x] `src/pages/Performance.tsx` — KPI, label grafici, sezioni
- [x] `src/pages/Allocation.tsx` — titoli card, label legenda
- [x] `src/pages/Dividendi.tsx` — KPI, label tabella
- [x] `src/pages/Fiscale.tsx` — bracket label, simulatore, storico
- [x] `src/pages/Alert.tsx` — form, badge stato
- [x] `src/pages/Impostazioni.tsx` — sezioni, label campo, descrizioni
- [x] `src/pages/Import.tsx` + `Strumenti.tsx` + `Admin.tsx`
- [x] `src/components/transactions/TransactionForm.tsx` — label, validazioni
- [x] `src/components/portfolio/HoldingDetailModal.tsx` — tab, label stat

### 9.5 Selezione lingua in Impostazioni

- [x] Sezione "Lingua" in Impostazioni → Preferenze (sotto tema, sopra Zen Mode)
- [x] UI: 4 pill-button affiancati con codice ISO + nome nativo (`IT · Italiano`, `EN · English`, `FR · Français`, `DE · Deutsch`)
- [x] `onChange` chiama `i18next.changeLanguage()` immediatamente (senza attendere il salvataggio backend) → cambio istantaneo
- [x] `updateSettings({ language })` salva su backend; `staleTime: Infinity` sul query `my-settings`

### 9.6 Formato date e numeri per lingua

- [x] `date-fns/locale` — importare `enUS`, `fr`, `de`, `it` e selezionare in base alla lingua corrente via `getDateFnsLocale(i18n.language)`
  - Usato in: Transazioni, Performance (tooltip), HoldingDetailModal, PriceChart, PortfolioChart
- [x] Numeri: `toLocaleString()` con locale dinamico (es. `"en-US"` → `1,234.56`, `"it-IT"` → `1.234,56`)
  - `src/utils/format.ts` — `getIntlLocale(lang)`, `getDateFnsLocale(lang)`, `fmtNum(v, opts, locale)`
  - `ThemeContext.tsx` — `useLocale()` hook esportato
  - Aggiornati: Dashboard, Performance, Transazioni, Allocation, Dividendi, Fiscale, Alert, Strumenti, Admin, HoldingDetailModal, PriceChart, PortfolioChart, PriceTicker, TransactionForm

---

**Nota sull'approccio:** l'italiano è la lingua sorgente (tutti i JSON `it/common.json` vengono scritti per primi). Le traduzioni EN/FR/DE sono generate in un secondo momento — finché non disponibili, `i18next` usa il fallback italiano. Non sono necessarie tutte e quattro le lingue per il primo rilascio.

---

## FASE 10 — Mobile & Smartphone ✅
**Obiettivo: esperienza pienamente fruibile su smartphone — tutte le pagine testate e ottimizzate per schermi < 640px**

> Le fondamenta responsive sono già in FASE 6.4 (breakpoints, bottom nav, card layout, PWA).
> Questa fase completa la copertura su ogni pagina e introduce interazioni native-like.

### 10.1 Audit responsive su tutte le pagine

- [x] **Performance** — colonne qty/avgCost/currentPrice/realizedPnl/dailyChange nascoste su mobile (`hidden md:table-cell`); colonna account dividendi nascosta
- [x] **Fiscale** — EventsTable: colonne type/rate nascoste su sm, quantity/cost su md; padding ridotto
- [x] **Dividendi** — tabella annuale e yield-on-cost già con `overflow-x-auto`; grafici full-width
- [x] **Alert** — modal con padding responsive (`p-4 sm:p-6`)
- [x] **Strumenti (PAC)** — chart height 220px su mobile / 280px su sm+; colonna tableReturn nascosta su mobile
- [x] **Admin** — colonne email/status/twoFactor/created nascoste progressivamente; modal responsive

### 10.2 Interazioni touch

- [x] **Swipe per navigare** tra le tab principali — `useSwipeNavigation` hook, threshold 60px, ignora swipe verticali (scroll); integrato in `MainLayout`
- [x] **Pull-to-refresh** sulla Dashboard — `usePullToRefresh` hook: touch start/move/end; soglia 72px, resistance 2.5×; indicatore spinner circolare fisso in cima durante il pull; al rilascio invalida `portfolio-dashboard`, `portfolio-performance`, `transactions`; solo mobile (`md:hidden`)
- [x] **Long-press / click su posizione** per aprire `HoldingDetailModal` — `useLongPress` hook + `DesktopHoldingRow` componente; mobile card già usava tap (`onClick`); desktop table usa click singolo + long-press per touch tablet
- [x] BottomNav tap area già 44×44px (`py-2` + icona 20px + label 10px)

### 10.3 PWA — completamento

- [x] **Install prompt** — `useInstallPrompt()` hook + `InstallBanner` component (dismiss persistito su `localStorage`)
- [x] **Offline fallback** — `/public/offline.html` + workbox `navigateFallback` configurato
- [x] **Splash screen** — `theme_color: #1d4ed8` e `background_color: #f0f7ff` in manifest
- [x] **Icone PWA** — set completo già presente: `icon-192x192-v2.png`, `icon-512x512-v2.png`, `apple-touch-icon-v2.png`, `favicon-32x32.png`; manifest referenzia tutte le taglie
- [ ] Notifiche push per price alert *(rimandato a VAPID backend)*

### 10.4 Performance su mobile

- [x] **Lazy load** di tutte le pagine non-dashboard via `React.lazy` + `Suspense` con `PageSkeleton`
- [ ] **Virtualizzazione tabelle** (> 50 righe) — rimandato
- [x] **Riduzione bundle** — `manualChunks` in `vite.config.ts`: 8 chunk vendor separati (react, charts, maps, i18n, forms, sentry, dates, query) *(completato in FASE 15.3)*
- [x] Immagini ottimizzate per connessioni lente — `loading="lazy" decoding="async"` su `AccountFavicon` e logo About; `fetchPriority="high" decoding="sync"` sul logo Sidebar (LCP element); topojson mappa già lazy via chunk `vendor-maps` + `React.lazy` Allocation page

### 10.5 Test su dispositivi reali

- [x] **iPhone safe-area** — `BottomNav` usa `env(safe-area-inset-bottom)`
- [ ] Verifica completa su iPhone Safari e Android Chrome
- [x] Breakpoint **< 375px** (iPhone SE) — aggiunto breakpoint `xs: 375px` in Tailwind; greeting row usa `flex-wrap + min-w-0 + truncate`; font ridotto a `text-lg` sotto xs
- [x] **Landscape** su smartphone — `landscape:` breakpoint Tailwind; `BottomNav` in landscape mostra solo icone (label nascoste, `py-1` ridotto) per risparmiare spazio verticale

---

## FASE 11 — Messa in Produzione 🚀 ✅
**Dominio: `nextfolio.myhomecloud.it` · HTTPS via Cloudflare Tunnel**
**Obiettivo: app live, stabile, sicura e monitorata**

### 11.1 Infrastruttura server

- [x] VPS disponibile (già in uso per altri servizi)
- [x] Docker + Docker Compose installati
- [x] Firewall UFW: nessuna porta pubblica esposta — il tunnel Cloudflare è outbound
- [x] Accesso SSH solo via chiave
- [ ] Utente non-root dedicato (es. `nextfolio`) per eseguire i container *(opzionale se già gestito)*

### 11.2 Dominio e HTTPS — Cloudflare Tunnel (esterno)

> Approccio scelto: **Cloudflare Tunnel condiviso** già attivo sulla VPS.
> Il tunnel è gestito separatamente (serve più webapp); nextfolio si espone solo su
> `127.0.0.1:3000` e il tunnel instrada `nextfolio.myhomecloud.it` verso quella porta.
> Nessuna porta 80/443 esposta pubblicamente; nessun certificato da gestire.

- [x] Dominio `nextfolio.myhomecloud.it` disponibile
- [x] Cloudflare Tunnel già attivo sulla VPS (condiviso tra più app)
- [x] Nel dashboard Cloudflare → Tunnel → Public Hostname configurato:
  - Hostname: `nextfolio.myhomecloud.it`
  - Service: `http://127.0.0.1:3000`
- [x] `docker-compose.yml` aggiornato: frontend su `127.0.0.1:3000`, nessun container `cloudflared`

### 11.3 Configurazione produzione

- [x] `.env` di produzione creato e configurato (mai committato nel repo)
- [x] `DEBUG=false` impostato
- [x] `APP_URL=https://nextfolio.myhomecloud.it` (usato nei link email reset password)

### 11.4 Database, migration e primo utente

- [x] Prima avvio: `docker compose run --rm backend alembic upgrade head` — applica tutte le migration
- [x] Tutte le migration 0001–0014 applicate senza errori

**Creazione primo utente SUPERADMIN** — aprire `https://nextfolio.myhomecloud.it/register` nel browser (la rotta esiste da FASE 12). Il backend accetta la registrazione senza OTP se il DB è vuoto; il primo utente diventa SUPERADMIN automaticamente. In alternativa via curl:
```bash
curl -s -X POST http://127.0.0.1:3000/api/v1/auth/register \
  -H "Host: nextfolio.myhomecloud.it" \
  -H "Content-Type: application/json" \
  -d '{"email":"tua@email.com","password":"Password123!","name":"Nome"}' \
  | python3 -m json.tool
```
> Il flag `Host:` è obbligatorio perché il backend valida `ALLOWED_HOSTS`.

- [x] Primo utente SUPERADMIN creato
- [x] Endpoint `/auth/register` bloccato dopo il primo utente (già implementato)
- [x] Reset password testato con SMTP produzione (Mailjet)

### 11.5 Backup automatico

- [x] Script `scripts/backup-postgres.sh` già presente — schedulato con `cron` ogni notte alle 02:00
  ```cron
  0 2 * * * /opt/nextfolio/scripts/backup-postgres.sh >> /var/log/nextfolio-backup.log 2>&1
  ```
- [x] Backup conservati per 30 giorni (rotazione già nello script)
- [x] Primo dump eseguito e verificato (208K)
- [x] Backup off-site: `scripts/backup-offsite.sh` — `rclone sync` verso Backblaze B2, crontab `5 2 * * *` *(completato in FASE 15.4)*

### 11.6 Monitoraggio e log

- [x] **Log rotation**: `json-file` driver con `max-size: 10m, max-file: 5` su tutti i container (via `x-logging` anchor in docker-compose.yml)
- [x] **Uptime monitoring**: UptimeRobot configurato su `https://nextfolio.myhomecloud.it/health`
- [x] **Error tracking**: [Sentry](https://sentry.io) integrato:
  - Backend: `sentry-sdk[fastapi]` + `CeleryIntegration` — cattura eccezioni non gestite
  - Frontend: `@sentry/react` + `browserTracingIntegration` — cattura JS errors + performance traces
- [x] **Celery**: `restart: unless-stopped` su tutti i container — si riavviano automaticamente in caso di crash
- [x] Task Celery attivi: `update_crypto_prices` e `check_price_alerts` eseguiti ogni 5 minuti (verificato nei log)

### 11.7 Checklist pre-lancio

- [x] ✅ Tutte le pagine funzionanti su desktop e mobile
- [x] ✅ Login, 2FA, reset password funzionanti end-to-end
- [x] ✅ HTTPS: certificato Cloudflare valido, nessun mixed content
- [x] ✅ Backup: dump nightly alle 02:00, rotazione 30 giorni, primo dump verificato (208K)
- [x] ✅ Sentry attivo (backend FastAPI + Celery, frontend React)
- [x] ✅ PWA icon aggiornata (barre crescenti navy/blu/smeraldo), cache-busting via versioning URL
- [x] ✅ UptimeRobot configurato su `https://nextfolio.myhomecloud.it/health`
- [ ] Import CSV (Fineco / Degiro) — da testare con file reale *(utente)*
- [ ] Market data: verificare prezzi aggiornati per azioni, ETF, BTP, crypto *(utente)*

### 11.8 Post-lancio (prime 2 settimane)

- [ ] Monitorare log Celery per errori nei task di market data
- [ ] Verificare consumo RAM/CPU dopo 24h di uptime (`docker stats`)
- [ ] Controllare dimensione DB dopo 1 settimana (tabella `price_history` cresce velocemente)
- [x] Indici aggiuntivi attivati — migration 0016: `transactions(asset_id)`, `transactions(account_id, asset_id)`, `price_alerts(is_active, asset_id)`, `price_history(asset_id, date DESC)` *(completato in FASE 15.2)*
- [ ] Archiviare `.env.production` in gestore password (non nel repo git)

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

## FASE 12 — Registrazione pubblica opzionale con verifica email ✅
**Prerequisiti: SMTP configurato (già fatto), FASE 11 completata**
**Obiettivo: il superadmin può abilitare la registrazione autonoma degli utenti, con conferma obbligatoria via email (OTP 6 cifre)**

> Flusso: l'utente inserisce email + password → il backend invia un codice OTP a 6 cifre (valido 15 min) → l'utente inserisce il codice → account creato con ruolo USER.
> La registrazione pubblica è **disabilitata di default** e attivabile solo dal superadmin.

### 12.1 Backend

**Migration:**
- [x] Migration `0015_registration_settings`: tabella `app_settings` (key VARCHAR PK, value TEXT) con seed `allow_public_registration = 'false'`
- [x] Migration 0015: aggiungere colonne su `users`: `email_verified` (Boolean, server_default `true`), `email_verification_token` (String, nullable), `email_verification_expires` (DateTime, nullable)

**Endpoint admin:**
- [x] `GET /admin/settings` — legge le impostazioni globali (incluso `allow_public_registration`)
- [x] `PATCH /admin/settings` — aggiorna impostazioni (solo superadmin); campo: `allow_public_registration: bool`

**Endpoint registrazione pubblica:**
- [x] `GET /auth/registration-status` — risponde `{"allow_public_registration": true/false}` (pubblico, senza auth)
- [x] `POST /auth/register` — logica aggiornata:
  - Se `allow_public_registration = false` AND esistono già utenti → HTTP 403
  - Se `allow_public_registration = true` → genera OTP 6 cifre, salva hash bcrypt su DB, invia email con codice, restituisce `{"requires_verification": true, "email": "..."}`
  - Il primo utente (DB vuoto) → SUPERADMIN senza verifica
- [x] `POST /auth/verify-email` — body: `{"email": "...", "code": "123456"}` → verifica hash OTP, attiva account, restituisce access+refresh token
- [x] `POST /auth/resend-verification` — reinvia OTP; sempre 202 (no user enumeration)
- [x] `services/email.py`: `send_verification_code(email, code, name)` con template HTML (codice in blocco grande centrato)

**OTP:**
- Codice: 6 cifre numeriche (`secrets.randbelow(1_000_000)` zero-padded)
- Hash `bcrypt(code)` salvato su DB (mai in chiaro)
- Scadenza: 15 minuti
- Risposta generica su errore (no user enumeration)

### 12.2 Frontend

**Pagina `/register`:**
- [x] Rotta `<Route path="/register" element={<Register />} />` aggiunta in `App.tsx`
- [x] `src/pages/Register.tsx` — form a 2 step con stesso layout split-panel del Login:
  - **Step 1**: nome + email + password + conferma password → `POST /auth/register`
  - **Step 2**: campo OTP 6 cifre, countdown 15 min (MM:SS), link "Rinvia codice" sbloccato dopo 60s → `POST /auth/verify-email`; successo → redirect a `/`
- [x] Link "Non hai un account? Registrati" nel Login — visibile solo se `GET /auth/registration-status` → `allow_public_registration: true`
- [x] Chiavi i18n aggiunte in IT / EN / FR / DE: `auth.createAccount`, `auth.register`, `auth.verifyEmail`, `auth.verifyEmailDesc`, `auth.verificationCode`, `auth.codeExpires`, `auth.codeExpired`, `auth.resendCode`, `auth.resendIn`, `auth.registerError`, `auth.alreadyAccount`, `auth.noAccount`, `auth.backToRegister`

**Pannello Admin — toggle registrazione pubblica:**
- [x] Componente `RegistrationToggleSection` in `Admin.tsx` — toggle iOS-style con `GET/PATCH /admin/settings`
- [x] Chiavi i18n: `admin.publicRegistration`, `admin.publicRegistrationDesc` (IT / EN / FR / DE)

### 12.3 Sicurezza

- [x] Rate limiting su `POST /auth/register` — già attivo via `slowapi`
- [x] Rate limiting su `POST /auth/verify-email` e `POST /auth/resend-verification` — già attivo
- [x] User enumeration prevenuta — risposta 202 costante su `resend-verification`; errore generico su verify
- [x] Pulizia automatica: task Celery `cleanup_unverified_users` giornaliero alle 03:00 — elimina utenti con `email_verified=false` e token scaduto
- [x] Utenti esistenti non impattati: `email_verified` impostato a `true` via `server_default` in migration

### 12.4 Checklist implementazione

```
Backend:                                         Frontend:
  [x] Migration 0015                               [x] Register.tsx (step 1 + step 2)
  [x] GET /auth/registration-status                [x] Route /register in App.tsx
  [x] POST /auth/register (aggiornato)             [x] Link condizionale in Login.tsx
  [x] POST /auth/verify-email                      [x] Toggle registrazione in Admin.tsx
  [x] POST /auth/resend-verification               [x] Chiavi i18n (it/en/fr/de)
  [x] GET /admin/settings + PATCH /admin/settings
  [x] send_verification_code() in email.py
  [x] Task Celery cleanup utenti non verificati
```

### 12.5 URL Privacy — MemoryRouter *(rimosso — causava bug di sessione)*

> MemoryRouter introdotto per nascondere il path nell'URL del browser, ma causava un bug critico:
> dopo il login, `navigate("/")` aggiornava solo il router in memoria; il browser URL rimaneva su `/login`.
> Al successivo F5 il browser ricaricava su `/login` e l'app mostrava di nuovo la login page
> ignorando i token validi in localStorage.
>
> Ripristinato `BrowserRouter` — Nginx è già configurato con `try_files $uri $uri/ /index.html`
> che serve correttamente l'SPA su qualsiasi path. L'URL del browser aggiorna normalmente.

- [x] Ripristinato `BrowserRouter` in `App.tsx` (rimosso `MemoryRouter`)
- [x] Nginx `try_files $uri $uri/ /index.html` già presente — nessuna modifica server richiesta
- [x] F5 / link diretti / link email funzionano correttamente su tutti i path

---

## FASE 13 — Fix post-lancio e miglioramenti UX 🔧

### 13.1 Sessione persistente — "Ricordami" ✅

**Problema:** con "Ricordami" attivo il refresh token durava solo 7 giorni; al rinnovo il flag `remember_me` veniva perso e l'access token tornava a 30 minuti invece di 24h. Dopo 7 giorni di inattività l'utente veniva disconnesso.

- [x] `create_refresh_token(remember_me)` — il flag `rem` è ora codificato nel payload JWT
- [x] Refresh token con remember_me: **30 giorni** (configurabile via `REFRESH_TOKEN_REMEMBER_ME_DAYS`)
- [x] `/auth/refresh` legge il flag `rem` dal refresh token e lo propaga al nuovo access token e al nuovo refresh token — la sessione non decade mai finché il refresh token è valido
- [x] `saveTokens()` in `auth.ts` — `refresh_token` salvato sempre in `localStorage` (indipendentemente da remember_me); solo l'`access_token` può andare in `sessionStorage` se remember=false
- [x] Aggiunto `REFRESH_TOKEN_REMEMBER_ME_DAYS=30` in `.env`, `backend/.env`, `.env.example` e `config.py`

### 13.2 Login al refresh del browser ✅

**Problema:** ogni F5 richiedeva il login. Causa: `MemoryRouter` non aggiornava l'URL reale del browser dopo il login (`navigate("/")` muoveva solo il router interno); al reload il browser ricaricava su `/login` e l'app mostrava la login page anche con token validi.

- [x] Sostituito `MemoryRouter` con `BrowserRouter` in `App.tsx` (vedi §12.5)

### 13.2b Token di sessione "Ricordami" — verifica 30 giorni ✅

**Problema riportato:** con "Ricordami" selezionato, il login sembrava scadere dopo ~24 ore invece di 30 giorni.

**Diagnosi:**
- `create_access_token(remember_me=True)` → durata `ACCESS_TOKEN_EXPIRE_MINUTES × 48 = 30 × 48 = 1440 min = **24 ore**`
- `create_refresh_token(remember_me=True)` → durata 30 giorni (corretto, flag `rem` propagato nel JWT)
- **Race condition**: al reload della pagina, 4–6 chiamate API partono in parallelo (dashboard, positions, prices…); tutte ottengono 401 (access_token scaduto); tutte tentavano `/auth/refresh` simultaneamente → alcune fallivano con il refresh token già ruotato → redirect a `/login`

**Fix implementati:**

- [x] **Mutex per il refresh** in `api.ts`: variabile `refreshPromise` condivisa — la prima chiamata che ottiene 401 avvia il refresh; tutte le successive attendono la stessa promessa invece di avviarne una propria; `finally(() => refreshPromise = null)` la resetta dopo ogni ciclo
- [x] **Refresh proattivo** in `auth.ts` — `refreshIfExpired()`: al mount di `PrivateRoute`, decodifica l'expiry del JWT (`atob(token.split(".")[1])`) senza librerie esterne; se scade entro 60 secondi, chiama `/auth/refresh` prima che qualsiasi altra API parta — azzera alla radice il problema dei 401 in burst
- [x] **PrivateRoute async-aware**: stato `ready/authenticated` — mostra `null` durante il refresh proattivo, poi renderizza la dashboard o reindirizza al login; elimina il flash di redirect seguito da reload

### 13.3 Dashboard — percentuale variazione di oggi ✅

- [x] KPI card "Variazione oggi" mostra ora anche la percentuale `(+0.42%)` sotto al valore in EUR, in linea con la card "Performance periodo"

### 13.3b + 13.4 Dashboard — Griglia 4 caselle sulla stessa riga ✅

**Layout finale implementato:**
```
Desktop (md+, ≥ 768px) — griglia 5 colonne:
┌────────────────────────┬────────────┬────────────┬────────────┐
│       Grafico          │   Valore   │ Perf. YTD  │ Var. oggi  │
│   col-span-2 (40%)     │   (20%)    │   (20%)    │   (20%)    │
│      h = 180px         │ € 142.830  │ +€ 12.830  │ +€ 320     │
│                        │ Inv €120k  │ +18.4%     │ +0.42%     │
└────────────────────────┴────────────┴────────────┴────────────┘

Mobile: stacked verticalmente (1 colonna)
```

- [x] Griglia `grid-cols-1 md:grid-cols-5` — grafico `col-span-2` (40%), 3 KPI `col-span-1` (20% ciascuna)
- [x] Aggiunto prop `height?: number` (default 220) a `PortfolioChart`; Dashboard passa `height={180}` per la vista compatta
- [x] Aggiunto prop `header?: ReactNode` a `PortfolioChart` (usato in fasi precedenti, mantenuto per estensibilità)
- [x] Card "Valore portafoglio / Investito" autonoma (non più nell'header del grafico)
- [x] Card "Performance periodo" e "Variazione oggi" in caselle separate
- [x] Zen mode e colori verde/rosso mantenuti su tutte le caselle
- [x] Rimossa `KpiCard` locale (non più necessaria)

### 13.5 Selettore periodo globale ✅

**Obiettivo:** il selettore della timeline nella Dashboard (1D · WTD · MTD · YTD · 1A · Max) diventa lo stato globale dell'app: Dashboard e Performance si sincronizzano automaticamente.

- [x] `src/context/PeriodContext.tsx` — `PeriodProvider` + `usePeriod()` hook; stato persistito in `localStorage("dashboard_period")`, default `"ytd"`
- [x] `App.tsx` — `PeriodProvider` wrappa `MainLayout` (solo route autenticate)
- [x] `Dashboard.tsx` — sostituito `useState` locale con `usePeriod()`; rimosso il `localStorage.setItem` duplicato nel `onChange` (ora gestito dal context)
- [x] `Performance.tsx` — sostituito `useState("1y")` locale con `usePeriod()`; il bottone periodo scrive nel context condiviso
- [x] Comportamento cross-page: selezionare "YTD" in Dashboard → navigare in Performance → la pagina mostra già YTD; cambiare periodo in Performance → tornare in Dashboard → il grafico riflette la nuova selezione
- [x] Se il periodo dal context non è nel set di una pagina (es. "wtd" in Performance), l'API lo gestisce correttamente e nessun bottone è evidenziato; l'utente può riallineare con un click
- [x] Allocazioni, Fiscale, Dividendi: non dipendono da un periodo di performance → nessuna modifica necessaria

### 13.6 Menu azioni transazione (kebab) ✅

**Motivazione:** le due icone matita + cestino erano scomode su mobile e non consentivano azioni aggiuntive.

- [x] Rimossi pulsanti `Pencil` + `Trash2` da riga desktop e card mobile
- [x] Sostituiti con icona `MoreVertical` (3 puntini verticali) che apre un dropdown con:
  - **Modifica** — apre `EditTxModal` (comportamento invariato)
  - **Clona** — apre `CloneTxModal`: copia il tipo, conto, cambio, commissioni e note ma svuota quantità, prezzo e data; crea una nuova transazione sullo stesso asset
  - **Elimina** — confirm + delete (comportamento invariato)
- [x] `TxActionMenu` component con click-away handler e dark mode
- [x] `CloneTxModal` component — stessa struttura di `EditTxModal`, chiama `transactionService.create()`
- [x] Chiavi i18n `transactions.clone`, `transactions.cloneTransaction`, `transactions.cloneDesc`, `transactions.actions` in IT / EN / FR / DE

---

## FASE 14 — Versioning e changelog ✅
**Obiettivo: ogni rilascio ha un numero di versione leggibile dall'app; le novità di ogni aggiornamento (anche minor) sono visibili all'utente e al superadmin**

### Strategia di versioning

Adottare **Semantic Versioning** (`MAJOR.MINOR.PATCH`):

| Incremento | Quando |
|------------|--------|
| `PATCH` (x.y.**Z**) | Bug fix, fix sicurezza, miglioramenti senza nuove funzioni |
| `MINOR` (x.**Y**.0) | Nuova funzionalità retrocompatibile (es. selettore periodo globale, pagina register) |
| `MAJOR` (**X**.0.0) | Redesign profondo, breaking change API, migrazione dati non reversibile |

**Versione attuale di partenza: `1.5.2`**
_(FASE 1–7 = 1.0.0 · FASE 8–9 = 1.1.0 · FASE 11 go-live = 1.2.0 · FASE 12 = 1.3.0 · FASE 13 fixes = 1.4.x → 1.5.x)_

### 14.1 Sorgente unica della versione

- [x] Creare `/opt/nextfolio/VERSION` — file di testo con il solo numero di versione (es. `1.5.2`)
- [x] `backend/app/core/config.py` — `APP_VERSION: str` letta da `VERSION` a runtime:
  ```python
  from pathlib import Path
  APP_VERSION = (Path(__file__).parents[3] / "VERSION").read_text().strip()
  ```
- [x] `frontend/vite.config.ts` — legge `VERSION` con `fs.readFileSync` e lo inietta come costante globale `__APP_VERSION__` al build
- [x] `frontend/src/vite-env.d.ts` — aggiunta dichiarazione `declare const __APP_VERSION__: string`

### 14.2 Endpoint versione

- [x] `GET /health` — aggiunto il campo `version` (da `APP_VERSION`) e `environment` nella risposta:
  ```json
  { "status": "ok", "version": "1.5.2", "environment": "production" }
  ```

### 14.3 Changelog strutturato

- [x] Creato `/opt/nextfolio/CHANGELOG.md` — formato [Keep a Changelog](https://keepachangelog.com/):
  ```markdown
  ## [1.5.2] — 2026-06-02
  ### Fixed
  - Mutex per refresh token: eliminato logout inatteso a 24h con "Ricordami"
  - Refresh proattivo al reload: nessun burst di 401 dopo inattività prolungata

  ## [1.5.1] — 2026-05-28
  ### Added
  - URL privacy: barra degli indirizzi mostra sempre solo il dominio base

  ## [1.5.0] — 2026-05-28
  ### Added
  - Registrazione pubblica con verifica OTP email (abilitabile dal superadmin)
  - Toggle registrazione pubblica nel pannello Admin
  ...
  ```
- [x] Aggiornare `CHANGELOG.md` ad ogni commit significativo (non solo sui tag)

### 14.4 Versione visibile in app

- [x] **Pagina About** (`/about`) — versione in badge, changelog con badge per tipo (Added/Fixed/Changed), sezione "versioni precedenti" espandibile, copyright con anno dinamico
- [x] **Sezione Info di sistema** (solo superadmin) — versione frontend (`__APP_VERSION__`) + versione backend (da `GET /health`) + environment + status
- [x] **Nessun banner popup** — le novità non interrompono l'utilizzo

### 14.5 Processo di rilascio (workflow)

```
1. Modifiche al codice
2. Aggiornare CHANGELOG.md con le novità della versione
3. Bumppare VERSION (es. 1.5.2 → 1.5.3 per patch, → 1.6.0 per minor)
4. Sincronizzare frontend/package.json "version"
5. git tag v1.5.3
6. docker compose build && docker compose up -d
```

- [x] Script `scripts/release.sh <patch|minor|major>` che automatizza i passi 2–4

### 14.6 Pagina About ✅

**Posizione nel menu:** dropdown utente in TopBar → tra "Impostazioni" e "Esci"

```
┌─────────────────┐
│ ⚙ Impostazioni  │
│ ℹ About         │  ← nuovo
│ ─────────────── │
│ ⬡ Esci          │
└─────────────────┘
```

**Contenuto della pagina `/about`:**

- [x] **Header** — logo Nextfolio + tagline + numero di versione in badge (`v1.5.2`)
- [x] **Changelog** — ultime 3 versioni visibili; sezione espandibile "versioni precedenti" con chevron toggle; badge colorati per tipo (Added verde, Fixed blu, Changed ambra)
- [x] **Info di sistema** (solo superadmin) — versione frontend / backend, environment, status (da `GET /health`)
- [x] **Copyright** — `© 2024–{anno corrente} Nextfolio` con anno dinamico

**Implementazione frontend:**

- [x] Rotta `<Route path="about" element={<About />} />` aggiunta in `App.tsx`
- [x] `src/pages/About.tsx` — layout card-based, dark mode, stesso stile delle altre pagine
- [x] `TopBar.tsx` — link "About" con icona `Info` tra Impostazioni e il divisore rosso Esci
- [x] **Chiavi i18n — tutte e 4 le lingue** (`src/locales/it|en|fr|de/common.json`), coerente con il resto dell'app:

  | Chiave | IT | EN | FR | DE |
  |--------|----|----|----|----|
  | `nav.about` | Info | About | À propos | Über |
  | `about.title` | Informazioni sull'app | About Nextfolio | À propos de Nextfolio | Über Nextfolio |
  | `about.description` | Gestione portafoglio... | Portfolio management... | Gestion de portefeuille... | Portfolioverwaltung... |
  | `about.version` | Versione | Version | Version | Version |
  | `about.environment` | Ambiente | Environment | Environnement | Umgebung |
  | `about.changelog` | Novità | What's new | Nouveautés | Neuigkeiten |
  | `about.systemInfo` | Info di sistema | System info | Infos système | Systeminfo |
  | `about.uptime` | Uptime server | Server uptime | Uptime serveur | Server-Uptime |
  | `about.copyright` | © {{from}}–{{year}} Nextfolio | © {{from}}–{{year}} Nextfolio | © {{from}}–{{year}} Nextfolio | © {{from}}–{{year}} Nextfolio |
  | `about.changelog.added` | Aggiunto | Added | Ajouté | Hinzugefügt |
  | `about.changelog.fixed` | Corretto | Fixed | Corrigé | Behoben |
  | `about.changelog.changed` | Modificato | Changed | Modifié | Geändert |
  | `about.changelog.older` | Versioni precedenti | Older versions | Versions précédentes | Ältere Versionen |

---

## FASE 15 — Manutenzione e performance ✅
**Obiettivo: chiudere i punti operativi rimasti aperti dopo il go-live**

### 15.1 Flower — monitoraggio Celery ✅

- [x] Container `flower` aggiunto in `docker-compose.dev.yml` (solo dev, non produzione)
- [x] Basic-auth `admin:admin` — cambiare se esposto su rete condivisa
- [x] Accessibile su `http://localhost:5555` — mostra task in coda, eseguiti, falliti, worker attivi
- [x] `flower>=2.0.0` aggiunto a `requirements.txt`

```bash
# Per avviarlo: docker compose -f docker-compose.dev.yml up flower
# Oppure con tutti i servizi: docker compose -f docker-compose.dev.yml up -d
```

### 15.2 Indici DB — migration 0016 ✅

- [x] `ix_transactions_asset_id` su `transactions(asset_id)` — FIFO e calcoli portafoglio iterano per asset
- [x] `ix_transactions_account_asset` su `transactions(account_id, asset_id)` — performance per-conto in `/allocation`
- [x] `ix_price_alerts_active_asset` su `price_alerts(is_active, asset_id)` — task `check_price_alerts` ogni 5 min
- [x] `ix_price_history_asset_date_desc` su `price_history(asset_id, date DESC)` — query "prezzo più recente"

```bash
# Applicare in produzione:
docker compose run --rm backend alembic upgrade head
```

### 15.3 Vite code splitting ✅

- [x] `build.rollupOptions.output.manualChunks` in `vite.config.ts`:
  - `vendor-react` — react + react-dom + react-router-dom
  - `vendor-query` — @tanstack/react-query + axios
  - `vendor-charts` — recharts (~300 KB separato)
  - `vendor-maps` — react-simple-maps (solo Allocation)
  - `vendor-i18n` — i18next stack
  - `vendor-forms` — react-hook-form + zod
  - `vendor-sentry` — @sentry/react (non bloccante per il render)
  - `vendor-dates` — date-fns
- [x] `chunkSizeWarningLimit: 500` — avviso se un chunk supera 500 KB

### 15.4 Backup off-site — Backblaze B2 ✅

- [x] Script `scripts/backup-offsite.sh` — sincronizza `/opt/nextfolio/backups/*.sql.gz` verso Backblaze B2 via `rclone sync`
- [x] `--delete-before` mantiene la stessa rotazione 30-giorni del backup locale
- [x] Crontab suggerito: `5 2 * * *` (5 min dopo il backup locale delle 02:00)
- [x] Istruzioni setup `rclone config` documentate nell'header dello script

---

## FASE 16 — X-Ray (analisi diagnostica portafoglio) 🔬
**Ispirata a:** [Ghostfolio X-Ray](https://github.com/ghostfolio/ghostfolio)
**Obiettivo: pagina di diagnostica del portafoglio che valuta automaticamente regole di rischio e diversificazione, segnalando in verde/rosso cosa va bene e cosa no**

> Ghostfolio X-Ray raggruppa le regole in categorie (concentrazione, asset class, geografie, fee, liquidità).
> Nextfolio adatta le stesse categorie con soglie configurabili e regole specifiche per il mercato italiano
> (BTP, valuta EUR, regime fiscale 26% / 12.5%).

---

### 16.1 Backend — motore regole (`services/portfolio/xray.py`)

**Struttura dati output:**

```python
class XRayRule(BaseModel):
    key: str                    # es. "concentration_single_asset"
    name: str                   # es. "Concentrazione singolo titolo"
    category: str               # es. "Concentrazione"
    description: str            # spiegazione della regola
    status: str                 # "ok" | "warn" | "error"
    actual: float | None        # valore attuale (es. 0.35 = 35%)
    threshold_min: float | None
    threshold_max: float | None
    unit: str                   # "%" | "EUR" | "mesi"

class XRayResponse(BaseModel):
    rules: list[XRayRule]
    score: int                  # 0–100: % regole superate
    rules_total: int
    rules_ok: int
```

**Regole da implementare (10 regole, 4 categorie):**

#### Categoria: Concentrazione

- [ ] **`concentration_single_asset`** — nessun titolo supera soglia% del portafoglio (default: max 20%)
  - `actual` = peso% del titolo più grande
  - `status = "ok"` se tutti i titoli ≤ 20%; "warn" 20–33%; "error" > 33%

- [ ] **`concentration_single_account`** — nessun conto/broker supera soglia% del portafoglio (default: max 80%)
  - `actual` = peso% del conto più grande
  - Usa il breakdown per-conto già calcolato

- [ ] **`concentration_crypto`** — esposizione crypto < soglia% (default: max 10%)
  - `actual` = % del portafoglio in asset di tipo CRYPTO
  - Usa l'allocazione `by_type` già disponibile

#### Categoria: Asset Class

- [ ] **`asset_class_equity`** — azioni + ETF nell'intervallo [min, max]% (default: 50–80%)
  - `actual` = % portafoglio in STOCK + ETF
  - Regola informativa/target, non bloccante

- [ ] **`asset_class_fixed_income`** — obbligazioni nell'intervallo [min, max]% (default: 5–30%)
  - `actual` = % portafoglio in BOND (inclusi BTP)
  - Utile per il mercato italiano dove i BTP sono comuni

- [ ] **`asset_class_currency_eur`** — esposizione EUR ≥ soglia% (default: min 30%)
  - `actual` = % portafoglio in asset denominati in EUR
  - Usa l'allocazione `by_currency`

#### Categoria: Fee

- [ ] **`fee_ratio`** — commissioni totali / capitale investito < soglia% (default: max 1.5%)
  - `actual` = sum(fee) / sum(total_invested_eur) × 100
  - Usa le transazioni già caricate; tipi FEE esclusi dall'investimento

#### Categoria: Diversificazione geografica

- [ ] **`geo_diversification`** — nessun continente supera soglia% (default: max 70%)
  - `actual` = peso% del continente più rappresentato (via look-through ETF)
  - Usa `by_continent` dall'allocation service

- [ ] **`geo_home_bias`** — esposizione Europa / Italia < soglia% (default: max 50%)
  - `actual` = % portafoglio con esposizione al continente Europe
  - Segnala "home bias" (sovraesposizione al mercato domestico)

#### Categoria: Liquidità

- [ ] **`liquidity_emergency_fund`** — presenza di riserva di liquidità (min 1 mese di investimento medio)
  - `actual` = cash in portafoglio come % del valore totale
  - Cerca asset di tipo BOND a breve scadenza o contanti (convenzionalmente: assets con yield > 0 e duration < 1y, oppure semplificato: presenza di qualsiasi obbligazione a breve)
  - Regola informativa

**Endpoint:**
- [ ] `GET /api/v1/portfolio/xray` — risponde con `XRayResponse`
- [ ] Cache Redis 10 min (chiave `xray:{user_id}`) — invalidata da nuove transazioni

---

### 16.2 Frontend — pagina X-Ray (`src/pages/XRay.tsx`)

**Route:** `/xray` · **Sidebar:** icona `ScanSearch` (lucide), label "X-Ray"

**Layout:**

```
┌────────────────────────────────────────────────┐
│  🔬 X-Ray                          Score: 7/10 │
│  Analisi diagnostica del portafoglio            │
│  ████████░░  70%                                │
└────────────────────────────────────────────────┘

┌─ Concentrazione ───────────────────────────────┐
│  ✅  Concentrazione singolo titolo   18% ≤ 20%  │
│  ✅  Concentrazione per conto        65% ≤ 80%  │
│  ⚠️  Esposizione crypto              14% > 10%  │
└────────────────────────────────────────────────┘

┌─ Asset Class ──────────────────────────────────┐
│  ✅  Azioni + ETF        72%  target 50–80%     │
│  ✅  Obbligazioni        12%  target  5–30%     │
│  ✅  Valuta EUR          45%  min 30%           │
└────────────────────────────────────────────────┘

┌─ Fee ──────────────────────────────────────────┐
│  ✅  Rapporto commissioni  0.3%  max 1.5%      │
└────────────────────────────────────────────────┘

┌─ Diversificazione geografica ──────────────────┐
│  ⚠️  Concentrazione per continente  72% > 70%   │
│  ✅  Home bias Europa               38% ≤ 50%   │
└────────────────────────────────────────────────┘

┌─ Liquidità ────────────────────────────────────┐
│  ℹ️  Fondo di emergenza — non rilevato          │
└────────────────────────────────────────────────┘
```

- [ ] Score globale in badge (regole OK / totale) con barra di progresso
- [ ] Ogni categoria è una card con lista regole
- [ ] Ogni regola mostra: icona status (✅ / ⚠️ / ❌), nome, valore attuale, soglia, barra visiva
- [ ] Dark mode completo
- [ ] Skeleton loading state
- [ ] Colori: verde (`ok`), ambra (`warn`), rosso (`error`), grigio (`info`)
- [ ] Tooltip con spiegazione di ciascuna regola

---

### 16.3 Integrazione sidebar e i18n

- [ ] Link "X-Ray" con icona `ScanSearch` in Sidebar (sotto "Analisi dividendi")
- [ ] Link "X-Ray" in BottomNav mobile (sostituisce o aggiunge — verificare spazio)
- [ ] Chiavi i18n `nav.xray`, `xray.title`, `xray.score`, `xray.categories.*`, `xray.rules.*` in IT / EN / FR / DE
- [ ] `NAV_ROUTES` in `BottomNav.tsx` aggiornato (se X-Ray entra tra le 5 tab)

---

### 16.4 Aggiornamento roadmap e CHANGELOG

- [ ] Aggiornare CHANGELOG.md
- [ ] Bumppare versione → `1.7.0` (nuova feature rilevante)

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
| 9 | Internazionalizzazione (i18n) — IT, EN, FR, DE | ✅ Completata | 🟡 Media | 2–3 sett. |
| 10 | Mobile & Smartphone — audit responsive, touch, PWA completo, performance | ✅ Completata | 🟠 Alta | 1–2 sett. |
| **11** | **Messa in Produzione — Cloudflare Tunnel, nextfolio.myhomecloud.it, backup, monitoring** | ✅ **Completata** | 🔴 **Critica** | **< 1 sett.** |
| **12** | **Registrazione pubblica opzionale con verifica email** | ✅ **Completata** | 🟠 Alta | 2–3 giorni |
| **13** | **Miglioramenti post-lancio — sessione, dashboard, periodo globale, token 30gg** | ✅ **Completata** | 🟠 Alta | — |
| **14** | **Versioning e changelog — VERSION file, endpoint, pagina About, i18n, release.sh** | ✅ **Completata** | 🟡 Media | 1–2 gg |
| **15** | **Manutenzione e performance — Flower, indici DB, code splitting, backup off-site, lazy images, PDF export** | ✅ **Completata** | 🟡 Media | 1 gg |
| **16** | **X-Ray — diagnostica portafoglio: 10 regole in 4 categorie, score, UI card-based** | 🔵 **In corso** | 🟠 Alta | 3–5 gg |

**Sequenza verso il go-live:** ~~FASE 9 (i18n)~~ ✅ → ~~FASE 10 (mobile)~~ ✅ → ~~FASE 11 (produzione)~~ ✅ → ~~FASE 12 (registrazione pubblica)~~ ✅ → ~~FASE 13 (miglioramenti post-lancio)~~ ✅ → ~~FASE 14 (versioning)~~ ✅ → ~~FASE 15 (manutenzione)~~ ✅

**Punti rimandati per scelta:** Metals-API (paid), PIR/IVAFE/LIFO/PMC (complessità contabile), push notifications (VAPID), Vitest/Playwright (frontend testing).

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
| Supporto smartphone completo (audit responsive, touch, PWA, performance mobile) | 10 | L'app deve essere pienamente fruibile su smartphone — copertura tutte le pagine, install prompt, offline fallback, virtualizzazione tabelle grandi |
| Internazionalizzazione (i18n) — IT, EN, FR, DE | 9 | Lingua selezionabile dalle impostazioni; `i18next` + `react-i18next`; `language` su `user_settings` |
| Piano go-live (VPS, nginx, HTTPS Let's Encrypt, Sentry, UptimeRobot, checklist pre-lancio) | 11 | Roadmap completa dalla dev locale al dominio pubblico; prerequisiti: FASE 9 + FASE 10 completate |
| Registrazione pubblica con OTP email (`app_settings`, `email_verified`, `send_verification_code`) | 12 | Il superadmin abilita la registrazione; OTP 6 cifre bcrypt-hashed scade in 15 min; cleanup Celery alle 03:00 per utenti non verificati; `allow_public_registration = false` di default |
| Sessione persistente "Ricordami" — flag `rem` in refresh token, durata 30 giorni, refresh_token sempre in localStorage | 13.1 | Con MemoryRouter il flag remember_me veniva perso ad ogni rinnovo; il refresh token durava solo 7 giorni causando logout frequenti su mobile |
| Fix login al F5 — `BrowserRouter` in sostituzione di `MemoryRouter` | 13.2 | MemoryRouter non aggiornava l'URL reale del browser dopo login; F5 ricaricava su `/login` ignorando i token validi in localStorage |
| Dashboard — percentuale variazione giornaliera nella KPI card | 13.3 | La card "Variazione oggi" mostrava solo il valore EUR; aggiunta la percentuale in linea con la card "Performance periodo" |

### Decisioni architetturali

- **Borsa Italiana come fonte primaria** per tutti gli asset con ISIN su MIL/EuroTLX/MOT; Yahoo Finance come fallback — copre BTP e obbligazioni che Yahoo non gestisce
- **Exchange rate = EUR per 1 unità di valuta estera** (es. 0.9259 EUR/USD): convenzione usata per il calcolo `total_eur = qty × price × exchange_rate`
- **Celery timezone = Europe/Rome**: gli orari di borsa (9:00-17:00) sono in ora locale italiana
- **WebSocket filtra per asset_ids**: il client può aggiornare la sottoscrizione a runtime inviando `{"action": "subscribe", "asset_ids": [1,2,3]}`

---

*Stack: React + FastAPI + PostgreSQL + Redis + Celery*
