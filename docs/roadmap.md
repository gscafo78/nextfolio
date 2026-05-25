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
- [ ] **Metals-API / Open Metals** — oro, argento, commodity *(rimandato a Fase 6)*
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
- [ ] **IRR / XIRR** — per investimenti con cash flow irregolari *(rimandato)*
- [x] **Dividend yield** — reddito da dividendi e cedole (lista separata)
- [x] **Performance per periodo**: 1S, 1M, 3M, 6M, 1A, 3A, Max

### 4.2 Analisi allocazione

- [x] Allocazione per **tipo asset** (azioni, ETF, obbligazioni, crypto, altro)
- [ ] Allocazione per **settore** *(richiede enrichment TrackInsight — vedi Fase 4.Z)*
- [ ] Allocazione per **area geografica / paese** *(richiede enrichment TrackInsight — vedi Fase 4.Z)*
- [x] Allocazione per **valuta** (EUR, USD, GBP...)
- [x] Allocazione per **broker/conto**
- [ ] Concentrazione per singolo titolo (alert se > 10%) *(rimandato a Fase 6)*

### 4.3 API performance

- [x] `GET /api/v1/portfolio/summary` — valore totale, P&L realizzato/non, variazione oggi
- [x] `GET /api/v1/portfolio/performance?period=1y` — serie temporale TWRR
- [x] `GET /api/v1/portfolio/allocation` — breakdown per tipo/valuta/conto
- [x] `GET /api/v1/portfolio/positions` — posizioni aperte con PMC, P&L, cambio giornaliero
- [x] `GET /api/v1/portfolio/dividends` — storico dividendi, cedole e interessi ricevuti

### 4.4 Frontend — Pagina Performance e grafici

- [x] **Grafico a torta** — allocazione per tipo asset, valuta, conto (Recharts `PieChart`)
- [x] **Grafico area** — andamento valore portafoglio + capitale investito nel tempo
- [ ] **Bar chart** — performance mensile / annuale *(rimandato)*
- [x] **Tabella posizioni** — asset, qtà, PMC, prezzo attuale, valore, P&L%, P&L€, P&L realizzato
- [x] KPI: P&L totale, P&L non realizzato, P&L realizzato, TWRR %
- [x] **Tabella dividendi** — storico con importo EUR, tipo (dividendo/cedola/interesse), conto
- [ ] Benchmark FTSE MIB / MSCI World *(rimandato a Fase 6)*

### 4.5 Frontend — Pagina Allocazioni ✅ *(aggiunta extra)*

- [x] Rotta `/allocazione` con link sidebar (icona PieChart)
- [x] Barra **Quota del patrimonio netto** (100% del portafoglio, totale EUR)
- [x] Donut **Per Piattaforma** — ripartizione per conto/broker (`by_account`)
- [x] Donut **Per Valuta** — ripartizione per valuta (`by_currency`)
- [x] Donut **Per Classe di Asset** — ripartizione per tipo ETF/Obbligazioni/... (`by_type`)
- [x] Donut grande **Per Holding** — ogni singola posizione con etichette esterne e legenda
- [x] Donut **Per Borsa** — ripartizione per exchange (MIL, XETRA, MOT...)

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

---

## FASE 4.Z — Asset enrichment (Ghostfolio-style) ⏳
**Obiettivo: arricchire gli asset con dati settoriali, geografici e holdings degli ETF**

> Ispirato all'architettura di Ghostfolio, che usa **TrackInsight** (NASDAQ ETF Database)
> come fonte principale per paese, settore e sottostanti degli ETF.

### Come funziona in Ghostfolio (riferimento)

1. Per ogni asset viene salvato un `symbol_mapping` es. `{"TRACKINSIGHT": "IE00B4L5Y983"}`
2. Un job "Gather Profile Data" chiama l'API TrackInsight con l'ISIN
3. I risultati vengono salvati come JSON sul profilo dell'asset:
   ```json
   {
     "countries":  [{"code": "US", "weight": 0.65}, {"code": "JP", "weight": 0.07}],
     "sectors":    [{"name": "Technology", "weight": 0.24}, {"name": "Financials", "weight": 0.14}],
     "holdings":   [{"symbol": "AAPL", "name": "Apple Inc", "weight": 0.04}]
   }
   ```
4. Il portfolio engine fa il "look-through": `position_weight × etf_holding_weight`
5. Un modello `SymbolProfileOverride` permette correzioni manuali per ETF non coperti

### 4.Z.1 Database

- [ ] Migration 0006: aggiungere campi JSON su `assets`:
  - `countries JSONB` — `[{"code": "US", "weight": 0.65}, ...]`
  - `sectors JSONB` — `[{"name": "Technology", "weight": 0.24}, ...]`
  - `holdings JSONB` — `[{"symbol": "AAPL", "name": "Apple Inc", "weight": 0.04}, ...]`
  - `data_provider_map JSONB` — `{"TRACKINSIGHT": "IE00B4L5Y983", "YAHOO": "SWDA.MI"}`
- [ ] Tabella `asset_profile_overrides` (asset_id FK, countries, sectors, holdings, updated_at)

### 4.Z.2 Backend — Enrichment service

- [ ] `TrackInsightEnricher` — client HTTP per `https://www.trackinsight.com/data-api/`
  - `fetch_profile(isin)` → paesi, settori, top holdings con pesi
  - Fallback su Yahoo Finance per `sector` dei singoli titoli (`Sector` nel `info` dict)
- [ ] `GET /api/v1/assets/{id}/enrich` — trigger manuale enrichment singolo asset (admin)
- [ ] Task Celery `enrich_all_assets` — enrichment bulk su tutti gli asset (on-demand)
- [ ] API `PATCH /api/v1/assets/{id}/profile` — override manuale paesi/settori/holdings (admin)

### 4.Z.3 Backend — Calcolo look-through

- [ ] Aggiornare `calculate_allocation()` per gestire `by_sector`, `by_country`, `by_continent`
  - Per ogni posizione ETF: iterare su `holdings` e moltiplicare per `position_weight`
  - Aggregare per settore e paese attraverso tutti gli ETF del portafoglio
- [ ] Tabella ISO paese → continente (mapping statico, ~250 righe)
- [ ] `AllocationOut` esteso: aggiungere `by_sector`, `by_country`, `by_continent`, `etf_holdings`

### 4.Z.4 Frontend — Grafici aggiuntivi su pagina Allocazioni

- [ ] Donut **Per Settore** (Technology, Financials, Healthcare...)
- [ ] Donut **Per Continente** (Nord America, Europa, Asia-Pacifico, Mercati Emergenti)
- [ ] Donut **Per Mercato** (Developed Markets, Emerging Markets, Other)
- [ ] **Mappa Regioni** — world map SVG colorata per peso geografico
- [ ] Donut **Per Paese** (US, JP, UK, FR, DE...)
- [ ] Tabella **By ETF Holding** — top sottostanti con valore e % look-through
- [ ] Sezione admin per editare manualmente `countries/sectors/holdings` di un asset

---

## FASE 4.W — Performance & ottimizzazioni backend

> Obiettivo: ridurre la latenza degli endpoint `/portfolio/*` percepita al refresh della Dashboard.

### Diagnosi bottleneck (analizzati il 25/05/2026)

| # | Problema | Impatto | Endpoint coinvolti |
|---|----------|---------|-------------------|
| A | Loop `await _price_data(db, asset)` **sequenziale** per N asset | 🔴 Alto — O(N × latenza Redis) | `/positions`, `/summary`, `/allocation` |
| B | Una nuova connessione TCP a Redis per ogni asset (`async with _redis()`) | 🟠 Medio — N handshake inutili | tutti |
| C | `/performance` ricalcolato da zero ad ogni request (TWRR su ~365 punti) | 🟠 Medio — CPU + N query DB | `/performance` |
| D | Dashboard fa 4+ chiamate HTTP separate al caricamento | 🟡 Bonus UX | frontend |

### 4.W.1 Fix A — `asyncio.gather` sui lookup prezzi ✅

- [x] Aggiunta `_fetch_prices_parallel(db, asset_map)`: fase 1 tutti i lookup Redis in parallelo con `asyncio.gather`, fase 2 fallback DB sequenziale solo per cache miss
- [x] `/positions` — rimosso loop sequenziale, usa `_fetch_prices_parallel`
- [x] `/summary` — idem
- [x] `/allocation` — idem
- **Risultato atteso**: con cache Redis calda (caso normale), latenza scende da O(N×1ms) a O(1ms)

### 4.W.2 Fix B — `MGET` bulk Redis + fallback non-bloccante ✅

- [x] `get_cached_prices_bulk(asset_ids)` in `updater.py` con `r.mget(*keys)` → 1 connessione TCP invece di N
- [x] Cache miss → fallback istantaneo su `price_history` DB (nessun fetch live nel path della request)
- [x] `BackgroundTasks` FastAPI lancia un singolo task parallelo (`asyncio.gather`) per warm-up cache post-risposta
- [x] TTL dinamico: 5 min durante orario di borsa (9:00–17:30), **4 ore** fuori orario/weekend
- [x] Celery Beat: aggiunto `update-stock-prices-premarket` (8:45) e `update-stock-prices-postmarket` (18:05)
- [x] Fix `yahoo_ticker` esplicito: quando impostato dall'utente usa `Exchange.OTHER` (nessun suffisso)
- [x] `yfinance` wrappato in `run_in_executor` → non blocca più l'event loop asyncio durante fetch in background
- **Risultato misurato (25/05/2026)**:
  - Cache fredda: ~90–150ms (era ~2s)
  - Cache calda: ~25ms (era invariata ma ora garantita anche fuori orario)

### 4.W.3 Fix C — Cache Redis per `/performance` ✅

- [x] Serializzare `PerformanceOut` come JSON in Redis con chiave `perf:{user_id}:{period}:{account_id}`
- [x] TTL 5 minuti (allineato al task `update_prices_eod`)
- [x] Invalidare la cache quando Celery pubblica nuovi prezzi (`update_prices_eod` chiama `invalidate_perf_cache(user_id)`)
- **Risultato**: `period=1y` 224ms cold → 7ms warm (32×); `period=3y` 377ms cold → 7ms warm (54×)

### 4.W.4 Fix D — Endpoint aggregato `/portfolio/dashboard` ✅

- [x] `GET /portfolio/dashboard` — risponde con `{summary, positions, allocation}` in una sola chiamata (1 DB session, 1 Redis MGET)
- [x] Dashboard page: `getPositions()` → `getDashboard()` (1 query invece di 1)
- [x] Performance page: `getSummary() + getPositions() + getAllocation()` → `getDashboard()` (3 query → 1)
- [x] Allocation page: `getAllocation() + getPositions()` → `getDashboard()` (2 query → 1)
- **Risultato**: ~15ms warm (vs ~65ms×N separati); 1 DB session, 1 Redis MGET, 0 round-trip extra

### 4.W.5 Fix E — Arrotondamento valute a 2 decimali in visualizzazione ✅

> **Obiettivo**: uniformare tutti i valori monetari visualizzati a 2 cifre decimali su ogni pagina.
> Gli input (inserimento transazioni) continuano ad accettare fino a 6 cifre decimali per la quantità e il prezzo unitario.

**Scope frontend (display-only):**
- [x] Performance — tabella posizioni: PMC e prezzo corrente `fmt(v, 4)` → `fmt(v, 2)`
- [x] HoldingDetailModal — StatCards PMC, prezzo mercato, min/max: `fmt(v, 4)` → `fmt(v, 2)`
- [x] HoldingDetailModal — tab Attività: `fmt(a.price, 4)` → `fmt(a.price, 2)`
- [x] HoldingDetailModal — tooltip grafico: `fmt(v, 4)` → `fmt(v, 2)`
- [x] PriceTicker — live price: `maximumFractionDigits: 4` → `2`
- [x] PriceChart — tooltip: `toFixed(4)` → `toFixed(2)`

**Invariati (4 decimali giustificati):**
- Tasso di cambio in Transazioni (`exchange_rate`) — necessita precisione
- Quantità asset in Dashboard — crypto/frazioni richiedono max 6 decimali
- Soglie alert in Alert.tsx — precisione richiesta dall'utente

**Regola da applicare:**
- Visualizzazione prezzi singoli (prezzo per unità): **2 decimali**
- Quantità asset: **max 6 decimali** (crypto/frazioni), mantenere come da standard attuale
- Tutti gli importi EUR: **2 decimali** (invariato, già corretto nella maggior parte dei componenti)

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

- [x] Metodo **FIFO** per il calcolo del costo base *(semplificazione MVP — broker italiani usano PMC in regime amministrato)*
- [x] Report per singola operazione con gain/loss dettagliato
- [x] Simulatore "cosa succede se vendo ora?" (`GET /tax/simulate?asset_id=X&quantity=Y`)
- [ ] Metodo **LIFO** *(regime dichiarativo — rimandato)*
- [ ] **PMC** *(regime amministrato — rimandato)*

### 5.3 API e report fiscali

- [x] `GET /api/v1/tax/years` — anni con eventi fiscali
- [x] `GET /api/v1/tax/report?year=2024` — report annuale con zainetto cumulativo
- [x] `GET /api/v1/tax/simulate?asset_id=1&quantity=10` — simulazione vendita
- [x] Frontend: pagina Fiscale con selettore anno, KPI, due bracket, tabella eventi collassabile
- [ ] **Export PDF/Excel** *(rimandato a Fase 6)*
- [ ] **Storico minusvalenze multi-anno** *(vista dedicata — rimandato)*

---

## FASE 6 — Features avanzate
**Durata stimata: 2–3 settimane**
**Obiettivo: funzionalità premium e UX avanzata**

### 6.1 Alert e notifiche ✅

- [x] Alert prezzo sopra/sotto soglia (`PRICE_ABOVE`, `PRICE_BELOW`)
- [x] Alert variazione % giornaliera (`CHANGE_PCT_UP`, `CHANGE_PCT_DOWN`)
- [x] Tabella `price_alerts` (migration 0005) con cooldown 4h per evitare spam
- [x] Task Celery `check_price_alerts` — ogni 5 min, confronta prezzo Redis con soglia
- [x] CRUD REST: `GET/POST /alerts`, `PATCH/DELETE /alerts/{id}`
- [x] Frontend: pagina Alert con autocomplete asset, sezioni attivi/disabilitati, badge "scattato"
- [ ] Alert dividendo in arrivo *(rimandato)*
- [ ] Notifiche email via `fastapi-mail` *(rimandato — richiede SMTP)*
- [ ] Notifiche push via PWA *(rimandato a Fase 6.4)*

### 6.2 Strumenti di analisi

- [ ] **Calcolatore PAC** — simulazione piano di accumulo con rendimento atteso
- [ ] **Simulatore vendita** — impatto fiscale prima di vendere
- [ ] **Correlazione asset** — matrice di correlazione fra i titoli in portafoglio
- [ ] **Rischio portafoglio** — volatilità, Sharpe ratio, max drawdown
- [ ] **Analisi dividendi** — calendario dividendi, yield on cost, crescita storica

### 6.3 Import/Export avanzato

- [x] Import da **Fineco** (CSV estratto conto) *(completato in Fase 2)*
- [x] Import da **Directa Plus** (CSV movimenti) *(completato in Fase 2)*
- [x] Import da **Degiro** (CSV transazioni) *(completato in Fase 2)*
- [ ] Import da **Interactive Brokers** (formato Flex Query)
- [ ] Export portafoglio in formato Ghostfolio (compatibilità)
- [ ] Export Excel con tutti i dati per uso personale
- [ ] **Metals-API / Open Metals** — oro, argento, commodity *(rimandato da Fase 3)*

### 6.4 Mobile — Layout responsive e PWA

> **Obiettivo**: Nextfolio deve essere pienamente usabile da smartphone, sia come web app nel browser che installata tramite PWA.

#### Responsive design (priorità alta)

- [ ] **Breakpoint mobile-first** — revisione generale del layout per schermi < 640px
- [ ] **Sidebar** → sostituita da bottom navigation bar su mobile (icone: Dashboard, Performance, Allocazioni, Transazioni, Impostazioni)
- [ ] **Dashboard** — grafico full-width, KPI cards in colonna singola, holdings in card verticali invece di tabella orizzontale
- [ ] **Holdings table** — su mobile mostra solo Nome + Valore + Performance; colonne secondarie accessibili con swipe o drawer
- [ ] **HoldingDetailModal** — già a pannello laterale, adattarlo a bottom sheet su mobile (full height, drag to dismiss)
- [ ] **Transazioni** — tabella → lista card su mobile
- [ ] **Grafici Recharts** — verificare leggibilità assi e tooltip su touch screen (tooltip on tap invece di hover)
- [ ] **Allocazione** — donut chart ridimensionato, legenda sotto il grafico su mobile
- [ ] **Form inserimento transazione** — input ottimizzati per tastiera numerica mobile (`inputMode="decimal"`)

#### PWA (priorità media)

- [ ] Configurare `vite-plugin-pwa` con Service Worker
- [ ] `manifest.webmanifest`: nome, icone (192px, 512px), colori brand, `display: standalone`
- [ ] Installazione su home screen iOS (Safari) e Android (Chrome)
- [ ] Modalità offline: cache delle ultime posizioni e prezzi con Workbox (`StaleWhileRevalidate`)
- [ ] Notifiche push per price alert (richiede backend endpoint VAPID)

---

## FASE 7 — Qualità e rilascio
**Durata stimata: 1–2 settimane**
**Obiettivo: test, sicurezza, deploy**

### 7.1 Testing

- [ ] **Backend**: Pytest con test unitari su tax engine e calcoli P&L
- [ ] **Backend**: Test di integrazione per le API (TestClient FastAPI)
- [ ] **Frontend**: Vitest per utility functions e hooks
- [ ] **Frontend**: Playwright per E2E (login, inserimento transazione, verifica P&L)
- [ ] Coverage minimo: 80% backend, 60% frontend

### 7.2 Sicurezza

- [x] Rate limiting sulle API (`slowapi`) *(completato in Fase 1)*
- [x] Validazione input con Pydantic (nessun SQL injection possibile) *(completato in Fase 1)*
- [ ] HTTPS obbligatorio in produzione
- [x] Refresh token rotation *(completato in Fase 1)*
- [x] CORS configurato per soli domini trusted *(completato in Fase 1)*
- [x] 2FA TOTP opzionale (`pyotp`) con session_token separato per il challenge *(completato in Fase 4.X)*
- [x] Ruoli SUPERADMIN/USER con dependency FastAPI `require_superadmin` *(completato in Fase 4.X)*
- [x] Registrazione pubblica bloccata dopo il primo utente *(completato in Fase 4.X)*
- [x] `bcrypt<4.0` per compatibilità con `passlib` *(fix applicato in Fase 4.X)*
- [ ] Audit log per operazioni sensibili (cancellazione transazioni)

### 7.3 Docker e deploy

- [ ] `Dockerfile` per frontend (nginx multi-stage build)
- [ ] `Dockerfile` per backend (Python slim)
- [ ] `docker-compose.yml` production con tutti i servizi
- [x] Variabili d'ambiente documentate in `.env.example` *(completato in Fase 1)*
- [ ] Script di backup PostgreSQL automatico

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
| 4.X | 2FA TOTP + ruoli + admin utenti | ✅ Completata | 🟠 Alta | — |
| 4.5 | Pagina Allocazioni (frontend) | ✅ Completata | 🟠 Alta | — |
| 4.W | Performance backend (gather, MGET, cache perf, dashboard) | ✅ Completata (Fix A ✅ Fix B ✅ Fix C ✅ Fix D ✅ Fix E ✅) | 🟠 Alta | 1 sett. |
| 4.Z | Asset enrichment (settori, paesi, ETF holdings) | ⏳ In coda | 🟠 Alta | 2–3 sett. |
| 5 | Tax engine italiano | ✅ Completata | 🟠 Alta | 2 sett. |
| 6 | Features avanzate | 🔄 In corso | 🟡 Media | 2–3 sett. |
| 7 | Testing + deploy | ⏳ In coda | 🟢 Normale | 1–2 sett. |

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
| Pagina `/allocazione` con 5 donut chart (holding, piattaforma, valuta, asset class, borsa) | 4.5 | Dashboard allocazione dedicata, ispirata a Ghostfolio; usa dati già disponibili senza enrichment |
| Asset enrichment via TrackInsight (paesi, settori, holdings ETF) | 4.Z | Ghostfolio usa TrackInsight + JSON blob su `SymbolProfile`; stessa architettura adattata a FastAPI/SQLAlchemy |

### Decisioni architetturali

- **Borsa Italiana come fonte primaria** per tutti gli asset con ISIN su MIL/EuroTLX/MOT; Yahoo Finance come fallback — copre BTP e obbligazioni che Yahoo non gestisce
- **Exchange rate = EUR per 1 unità di valuta estera** (es. 0.9259 EUR/USD): convenzione usata per il calcolo `total_eur = qty × price × exchange_rate`
- **Celery timezone = Europe/Rome**: gli orari di borsa (9:00-17:00) sono in ora locale italiana
- **WebSocket filtra per asset_ids**: il client può aggiornare la sottoscrizione a runtime inviando `{"action": "subscribe", "asset_ids": [1,2,3]}`

---

*Stack: React + FastAPI + PostgreSQL + Redis + Celery*
