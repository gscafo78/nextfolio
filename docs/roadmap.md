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

## FASE 1 — Setup e infrastruttura base
**Durata stimata: 1–2 settimane**
**Obiettivo: ambiente funzionante, autenticazione, DB schema**

### 1.1 Ambiente di sviluppo

- [ ] Inizializzare il monorepo (`git init`, `.gitignore`, `README.md`)
- [ ] Creare `docker-compose.dev.yml` con PostgreSQL 15 e Redis 7
- [ ] Configurare VS Code workspace (`.vscode/settings.json`, estensioni consigliate)
- [ ] Aggiungere `.env.example` con tutte le variabili necessarie

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

- [ ] Creare virtual environment Python (`python -m venv venv`)
- [ ] Installare dipendenze: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic`, `python-jose`, `passlib`, `celery`, `redis`, `yfinance`, `httpx`
- [ ] Configurare `main.py` con CORS, middleware, e router
- [ ] Configurare connessione PostgreSQL via SQLAlchemy async
- [ ] Creare primo migration Alembic (tabelle `users`, `accounts`)
- [ ] Implementare autenticazione JWT (register, login, refresh token)
- [ ] Aggiungere endpoint `/health` e `/api/v1/auth/*`

### 1.3 Frontend — React scaffold

- [ ] `npm create vite@latest frontend -- --template react-ts`
- [ ] Installare: `tailwindcss`, `react-router-dom`, `@tanstack/react-query`, `axios`, `recharts`, `react-hook-form`, `zod`
- [ ] Configurare Tailwind CSS e design system base
- [ ] Creare layout principale (Sidebar, TopBar, MainContent)
- [ ] Implementare pagine Login e Register
- [ ] Configurare React Query client e Axios interceptors (JWT)
- [ ] Proteggere le route con `PrivateRoute`

### 1.4 Schema database iniziale

```sql
-- Tabelle da creare nella FASE 1
users           (id, email, password_hash, name, currency, created_at)
accounts        (id, user_id, name, type, broker, currency, created_at)
```

---

## FASE 2 — Asset e transazioni
**Durata stimata: 2–3 settimane**
**Obiettivo: inserire e gestire transazioni su tutti i tipi di asset**

### 2.1 Modello dati asset italiani

- [ ] Tabella `assets` con supporto ISIN italiano
- [ ] Tipi supportati: `STOCK`, `ETF`, `BOND`, `CRYPTO`, `COMMODITY`, `REIT`
- [ ] Campi specifici IT: ISIN, mercato (`MIL`, `EuroTLX`, `MOT`), valuta EUR
- [ ] Tabella `transactions` (BUY, SELL, DIVIDEND, COUPON, FEE, INTEREST)
- [ ] Tabella `price_history` per storico prezzi

```sql
-- Schema FASE 2
assets          (id, isin, symbol, name, type, exchange, currency, sector)
transactions    (id, account_id, asset_id, type, date, quantity, price, fee, currency, notes)
price_history   (id, asset_id, date, open, high, low, close, volume)
```

### 2.2 Backend — API transazioni

- [ ] `GET/POST /api/v1/transactions` — lista e creazione
- [ ] `PUT/DELETE /api/v1/transactions/{id}` — modifica e cancellazione
- [ ] `GET /api/v1/assets/search?q=` — ricerca asset per nome/ISIN/ticker
- [ ] `GET /api/v1/accounts` — gestione conti multi-broker
- [ ] Validazione ISIN italiano (regex + checksum)
- [ ] Import CSV da broker italiani (Fineco, Directa Plus, Degiro)

**Formato CSV Fineco da supportare:**
```
Data,Descrizione,Divisa,Importo,Tipo
15/03/2024,Acquisto ENI,EUR,-1500.00,BUY
```

### 2.3 Frontend — Pagine transazioni

- [ ] Pagina "Portafoglio" con tabella posizioni aperte
- [ ] Form aggiunta transazione con autocomplete asset (ISIN/ticker)
- [ ] Pagina "Transazioni" con filtri per data, tipo, account
- [ ] Upload CSV con preview e mappatura colonne
- [ ] Componente `AssetBadge` con logo broker/borsa

---

## FASE 3 — Market data e prezzi
**Durata stimata: 2 settimane**
**Obiettivo: prezzi aggiornati automaticamente per tutti gli asset**

### 3.1 Integrazione fonti dati

- [ ] **Yahoo Finance** (`yfinance`) — azioni Borsa Italiana (suffix `.MI`), ETF
- [ ] **CoinGecko API** — criptovalute (free tier sufficiente)
- [ ] **Metals-API / Open Metals** — oro, argento, commodity
- [ ] **MTS / Borsa Italiana** — BTP e obbligazioni (scraping o API pubblica)
- [ ] Fallback logic: se fonte primaria fallisce, prova fonte secondaria

**Ticker italiani principali:**
```python
# Esempi suffissi Yahoo Finance per Borsa Italiana
"ENI.MI"     # ENI
"ISP.MI"     # Intesa Sanpaolo  
"ENEL.MI"    # Enel
"FCA.MI"     # Stellantis
# ETF su Borsa Italiana
"SWRD.MI"    # SPDR MSCI World
"VWCE.MI"    # Vanguard FTSE All-World
```

### 3.2 Task asincroni con Celery

- [ ] Task `update_prices_realtime` — ogni 15 min durante orari di borsa
- [ ] Task `update_prices_eod` — prezzi di chiusura ogni sera
- [ ] Task `update_crypto_prices` — ogni 5 min (mercato 24/7)
- [ ] Task `cleanup_old_prices` — pulizia dati oltre 5 anni
- [ ] Celery Beat per scheduling automatico
- [ ] Flower dashboard per monitoraggio task

### 3.3 API prezzi e WebSocket

- [ ] `GET /api/v1/assets/{id}/price` — prezzo corrente + variazione %
- [ ] `GET /api/v1/assets/{id}/history?period=1y` — storico prezzi
- [ ] WebSocket `/ws/prices` — aggiornamenti live per asset nel portafoglio
- [ ] Cache Redis con TTL: 5 min per azioni, 1 min per crypto

---

## FASE 4 — Calcolo portfolio e performance
**Durata stimata: 2–3 settimane**
**Obiettivo: P&L, rendimenti, allocazione**

### 4.1 Engine di calcolo performance

- [ ] **Valore corrente portafoglio** — quantità × prezzo attuale
- [ ] **P&L realizzato** — gain/loss su posizioni chiuse (FIFO/LIFO)
- [ ] **P&L non realizzato** — gain/loss su posizioni aperte
- [ ] **TWRR** (Time-Weighted Rate of Return) — per confronto con benchmark
- [ ] **IRR / XIRR** — per investimenti con cash flow irregolari (es. PAC)
- [ ] **Dividend yield** — rendimento da dividendi e cedole
- [ ] **Performance per periodo**: 1G, 1S, 1M, 3M, YTD, 1A, 3A, Max

### 4.2 Analisi allocazione

- [ ] Allocazione per **tipo asset** (azioni, ETF, obbligazioni, crypto, altro)
- [ ] Allocazione per **settore** (energia, finanza, tech, healthcare...)
- [ ] Allocazione per **area geografica** (Italia, Europa, USA, Emergenti)
- [ ] Allocazione per **valuta** (EUR, USD, GBP...)
- [ ] Allocazione per **broker/conto**
- [ ] Concentrazione per singolo titolo (alert se > 10% portafoglio)

### 4.3 API performance

- [ ] `GET /api/v1/portfolio/summary` — valore totale, P&L, rendimento %
- [ ] `GET /api/v1/portfolio/performance?period=1y` — serie temporale rendimento
- [ ] `GET /api/v1/portfolio/allocation` — breakdown per tipo/settore/geo
- [ ] `GET /api/v1/portfolio/positions` — posizioni aperte con P&L
- [ ] `GET /api/v1/portfolio/dividends` — storico dividendi e cedole ricevuti

### 4.4 Frontend — Dashboard e grafici

- [ ] **Grafico a torta** — allocazione asset con Recharts `PieChart`
- [ ] **Grafico lineare** — andamento portafoglio nel tempo vs benchmark (FTSE MIB)
- [ ] **Bar chart** — performance mensile / annuale
- [ ] **Tabella posizioni** — con colonne: asset, quantità, P.M.C., valore, P&L%, P&L€
- [ ] Widget "Riepilogo oggi" — variazione giornaliera totale
- [ ] Benchmark: FTSE MIB, MSCI World, BTP 10Y rendimento

---

## FASE 5 — Tax engine italiano 🇮🇹
**Durata stimata: 2 settimane**
**Obiettivo: calcolo automatico imposte secondo normativa italiana**

### 5.1 Regole fiscali da implementare

- [ ] **Capital gain tassabili** — aliquota 26% su plusvalenze
- [ ] **Titoli di Stato** (BTP, BOT, CCT) — aliquota agevolata **12,5%**
- [ ] **Minusvalenze** — compensabili con plusvalenze entro **4 anni**
- [ ] **Zainetto fiscale** — calcolo minusvalenze residue disponibili
- [ ] **Dividendi** — ritenuta 26% (già alla fonte per azioni italiane)
- [ ] **Cedole BTP** — ritenuta 12,5%
- [ ] **Crypto** — tassazione 26% su gain > 2.000€/anno (dal 2023)
- [ ] **PIR** — esenzione fiscale se mantenuto 5 anni (flag apposito)
- [ ] **IVAFE** — imposta 0,2% su attività finanziarie estere

### 5.2 Calcolo LIFO / FIFO

- [ ] Metodo **LIFO** (obbligatorio per regime dichiarativo in Italia)
- [ ] Calcolo del **PMC** (Prezzo Medio di Carico) per regime amministrato
- [ ] Report "vendite" con gain/loss per singola operazione
- [ ] Simulatore "cosa succede se vendo ora?"

### 5.3 Report fiscali

- [ ] **Riepilogo annuale** — totale plusvalenze, minusvalenze, imposte dovute
- [ ] **Export per dichiarazione** — dati pronti per Quadro RT (Unico/730)
- [ ] **Storico minusvalenze** — per anno, con scadenza (4 anni)
- [ ] Export PDF/Excel del report fiscale

---

## FASE 6 — Features avanzate
**Durata stimata: 2–3 settimane**
**Obiettivo: funzionalità premium e UX avanzata**

### 6.1 Alert e notifiche

- [ ] Alert prezzo (sopra/sotto soglia per un asset)
- [ ] Alert variazione % giornaliera (es. > 5%)
- [ ] Alert dividendo in arrivo
- [ ] Notifiche email via `fastapi-mail`
- [ ] Notifiche push via PWA (Service Worker)

### 6.2 Strumenti di analisi

- [ ] **Calcolatore PAC** — simulazione piano di accumulo con rendimento atteso
- [ ] **Simulatore vendita** — impatto fiscale prima di vendere
- [ ] **Correlazione asset** — matrice di correlazione fra i titoli in portafoglio
- [ ] **Rischio portafoglio** — volatilità, Sharpe ratio, max drawdown
- [ ] **Analisi dividendi** — calendario dividendi, yield on cost, crescita storica

### 6.3 Import/Export avanzato

- [ ] Import da **Fineco** (CSV estratto conto)
- [ ] Import da **Directa Plus** (CSV movimenti)
- [ ] Import da **Degiro** (CSV transazioni)
- [ ] Import da **Interactive Brokers** (formato Flex Query)
- [ ] Export portafoglio in formato Ghostfolio (compatibilità)
- [ ] Export Excel con tutti i dati per uso personale

### 6.4 PWA e mobile

- [ ] Configurare `vite-plugin-pwa` per Progressive Web App
- [ ] Manifesto e icone per installazione su smartphone
- [ ] Ottimizzazione mobile (layout responsive, touch gestures)
- [ ] Modalità offline con cache delle ultime posizioni

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

- [ ] Rate limiting sulle API (`slowapi`)
- [ ] Validazione input con Pydantic (nessun SQL injection possibile)
- [ ] HTTPS obbligatorio in produzione
- [ ] Refresh token rotation
- [ ] CORS configurato per soli domini trusted
- [ ] Audit log per operazioni sensibili (cancellazione transazioni)

### 7.3 Docker e deploy

- [ ] `Dockerfile` per frontend (nginx multi-stage build)
- [ ] `Dockerfile` per backend (Python slim)
- [ ] `docker-compose.yml` production con tutti i servizi
- [ ] Variabili d'ambiente documentate in `.env.example`
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
fastapi-mail>=1.4.0
slowapi>=0.1.9
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
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
    "lucide-react": "^0.344.0"
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
cd backend && celery -A app.tasks worker --loglevel=info

# Avviare Celery Beat (scheduler)
cd backend && celery -A app.tasks beat --loglevel=info

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

| Fase | Descrizione | Priorità | Stima |
|------|-------------|----------|-------|
| 1 | Setup + auth + DB | 🔴 Critica | 1–2 sett. |
| 2 | Asset + transazioni | 🔴 Critica | 2–3 sett. |
| 3 | Market data + prezzi | 🔴 Critica | 2 sett. |
| 4 | Portfolio + performance | 🟠 Alta | 2–3 sett. |
| 5 | Tax engine italiano | 🟠 Alta | 2 sett. |
| 6 | Features avanzate | 🟡 Media | 2–3 sett. |
| 7 | Testing + deploy | 🟢 Normale | 1–2 sett. |

**Tempo totale stimato: 12–18 settimane** (sviluppo part-time)

---

*Generato per: Nextfolio — wealth management focalizzato sul mercato italiano*
*Stack: React + FastAPI + PostgreSQL + Redis*
