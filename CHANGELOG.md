# Changelog

Tutte le modifiche rilevanti sono documentate in questo file.
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) · Versioning: [SemVer](https://semver.org/lang/it/)

---

## [1.9.2] — 2026-08-21
### Fixed
- **Prezzi in valuta non-EUR trattati come EUR**: Yahoo Finance quota alcuni ETF (iShares Core MSCI World, Xtrackers EM) in USD ma non veniva mai calcolato un `exchange_rate` — il prezzo USD finiva usato as-is come EUR, gonfiando valore posizioni/conti del 15-18%. Aggiunta conversione FX (cache Redis) su prezzi live e storico `price_history`, via Frankfurter API (nel frattempo migrata da `.app` a `.dev`, redirect ora seguito)
- **Performance Max ignorava posizioni chiuse e asset senza storico**: `calculate_positions()` esclude di default le posizioni a quantità zero — nel loop giorno-per-giorno questo faceva sparire, il giorno stesso di una vendita totale, sia il valore che il cash flow della posizione, generando una perdita fittizia e falsando il TWRR da quel giorno in poi. Aggiunto anche un fallback al costo di carico per asset privi di storico prezzi (es. ISIN scarsamente scambiati), prima esclusi silenziosamente
- **Close NaN sulla barra odierna non chiusa propagava NaN in Performance Max**: `get_price_history` applicava il guard anti-NaN a open/high/low/volume ma non a `close` — il NaN restituito da Yahoo per la candela del giorno corrente finiva salvato in `price_history` e si propagava in tutto `get_portfolio_performance` (value/pnl/twrr = NaN). Guard aggiunto alla fonte, più filtro difensivo nei consumer
- **Importi monetari mostrati con 3 decimali invece di 2**: `toLocaleString` con solo `minimumFractionDigits` (senza `maximumFractionDigits`) usa un massimo di 3 decimali per default, mostrando cifre spurie sui totali calcolati lato client (es. "Variazione oggi": -27,038 invece di -27,04)
- **Card "investito" per conto ignorava le vendite**: sommava solo il costo degli acquisti (BUY), senza sottrarre le vendite — una posizione venduta per intero restava comunque conteggiata nel capitale investito

---

## [1.8.0] — 2026-06-02
### Added
- **Watchlist**: pagina `/watchlist` per monitorare asset senza possederli — prezzi live, variazione giornaliera, prezzo target con indicatore di distanza, note personali; icona `Eye` in Sidebar; i18n IT/EN/FR/DE
- **Ribilanciamento portafoglio**: sezione collapsible in pagina X-Ray — slider per target % per asset class (Azioni, Obbligazioni, Crypto, Altro), campo liquidità disponibile, lista trade suggeriti (buy/sell) con importo EUR e variazione allocazione; endpoint `POST /api/v1/portfolio/rebalance`
- Migration `0017_watchlist`: tabella `watchlist(user_id, asset_id, note, target_price, added_at)` con unique constraint per user+asset
- CRUD completo: `GET/POST/PATCH/DELETE /api/v1/watchlist`

### Fixed
- **X-Ray label mismatch**: le regole `asset_class_fixed_income` (cercava `"BOND"` invece di `"Obbligazioni"`) e `asset_class_equity` (cercava `"STOCK"` invece di `"Azioni"`) non mostravano dati; `_TYPE_LABELS` ora esportato come costante pubblica e usato per il lookup corretto
- **X-Ray home bias**: cercava il continente `"Europe"` invece di `"Europa"` in `by_continent`
- **Period P&L null per periodo "max"**: aggiunto fallback a `unrealized_pnl_eur` quando non esiste un prezzo a inizio periodo (copertura anche per asset comprati durante il periodo)

---

## [1.7.0] — 2026-06-02
### Added
- **X-Ray — diagnostica portafoglio**: pagina `/xray` con 10 regole in 4 categorie ispirata a Ghostfolio X-Ray
  - *Concentrazione*: singolo titolo (max 20%), singolo conto/broker (max 80%), esposizione crypto (max 10%)
  - *Asset Class*: azioni+ETF (target 50–80%), obbligazioni inclusi BTP (target 5–30%), copertura EUR (min 30%)
  - *Fee*: rapporto commissioni / capitale negoziato (max 1.5%)
  - *Diversificazione geografica*: concentrazione per continente (max 70%), home bias Europa (max 50%)
  - *Liquidità*: riserva di emergenza (min 2%)
- Score globale 0–100% con barra di progresso colorata (verde/ambra/rosso)
- Ogni regola mostra: icona status, valore attuale, soglia, barra visiva proporzionale
- Link "X-Ray" in Sidebar con icona `ScanSearch`
- Endpoint `GET /api/v1/portfolio/xray` con motore regole in `services/portfolio/xray.py`

### Fixed
- `__APP_VERSION__` mostrava 0.0.0 in produzione: frontend ora legge da `package.json` (dentro il build context Docker); backend legge env var `APP_VERSION` passata da `docker-compose.yml`
- `release.sh` aggiorna automaticamente `APP_VERSION` nel file `.env` ad ogni bump

---

## [1.6.0] — 2026-06-02
### Added
- **Kebab menu transazioni**: icona 3 puntini verticali sostituisce matita + cestino; dropdown con Modifica, Clona ed Elimina
- **Clona transazione**: copia tipo, conto, cambio, commissioni e note — svuota quantità, prezzo e data per reinserimento rapido
- **Swipe navigation mobile**: scorrimento orizzontale tra le 5 tab del BottomNav (`useSwipeNavigation` hook, soglia 60 px)
- **Long-press su righe desktop**: `useLongPress` hook + `DesktopHoldingRow` — apre HoldingDetailModal con singolo click/long-press (sostituisce il doppio-click)
- **Flower dashboard**: container Celery monitoring su `localhost:5555` in `docker-compose.dev.yml`
- **Script `scripts/release.sh`**: automatizza bump VERSION, package.json e intestazione CHANGELOG
- **Script `scripts/backup-offsite.sh`**: sincronizzazione backup PostgreSQL verso Backblaze B2 via rclone

### Fixed
- **BottomNav landscape**: etichette nascoste e padding ridotto in orientamento orizzontale per guadagnare spazio verticale
- **Layout 375px (iPhone SE)**: greeting row usa `flex-wrap + min-w-0 + truncate`; aggiunto breakpoint `xs: 375px` in Tailwind
- **Immagini ottimizzate**: `loading="lazy" decoding="async"` su favicon account e logo About; `fetchPriority="high"` sul logo Sidebar (LCP)

### Changed
- **Vite code splitting**: `manualChunks` con 8 chunk vendor separati (react, charts, maps, i18n, forms, sentry, dates, query); avviso chunk > 500 KB
- **Migration 0016**: 4 indici B-tree su `transactions(asset_id)`, `transactions(account_id, asset_id)`, `price_alerts(is_active, asset_id)`, `price_history(asset_id, date DESC)`
- Aggiunto breakpoint `landscape` e `xs` in `tailwind.config.js`

---

## [1.5.2] — 2026-06-02
### Fixed
- Mutex per il refresh token in `api.ts`: eliminato logout inatteso a ~24h con "Ricordami" attivo (race condition su refresh paralleli)
- Refresh proattivo in `PrivateRoute`: l'access token viene rinnovato silenziosamente al reload se scade entro 60 secondi

## [1.5.1] — 2026-05-30
### Added
- URL privacy: il browser mostra sempre e solo `nextfolio.myhomecloud.it` durante tutta la navigazione (MemoryRouter → BrowserRouter con nginx `try_files`)

### Fixed
- Sessione persistente "Ricordami": il flag `rem` viene ora propagato correttamente nel refresh token e riletto a ogni rinnovo; sessione attiva fino a 30 giorni
- Percentuale variazione giornaliera visibile nella KPI card "Variazione oggi" in Dashboard

## [1.5.0] — 2026-05-28
### Added
- Registrazione pubblica con verifica OTP email: il superadmin può abilitare la registrazione autonoma degli utenti
- Pagina `/register` con form a 2 step (dati → codice OTP 6 cifre, valido 15 min)
- Toggle "Registrazione pubblica" nel pannello Admin
- Link "Non hai un account?" in pagina Login (visibile solo se registrazione abilitata)
- Task Celery `cleanup_unverified_users`: pulizia automatica giornaliera alle 03:00
- i18n: chiavi registrazione/OTP aggiunte in IT / EN / FR / DE

### Fixed
- Migration 0015: tabella `app_settings` + colonne `email_verified` su `users`

## [1.4.0] — 2026-05-27
### Added
- Internazionalizzazione completa (i18n): IT · EN · FR · DE selezionabile dalle impostazioni utente
- Selettore lingua in Impostazioni → Preferenze (pill-button istantaneo senza reload)
- Formato date e numeri adattato alla lingua selezionata (`date-fns/locale`, `toLocaleString`)

## [1.3.0] — 2026-05-20
### Added
- UX/UI Polish: TopBar consistente su tutte le pagine, paginazione Transazioni, stacked allocation bar, mini progress bar legenda
- Zen Mode: toggle privacy che maschera i valori monetari in tutta l'app (full-stack)
- Login page redesign: split layout dark/light, grafico area SVG decorativo, ticker strip
- Tema dark / light / sistema (class-based Tailwind, anti-FOUC, cambio istantaneo)

## [1.2.0] — 2026-05-15
### Added
- Messa in produzione: `nextfolio.myhomecloud.it` via Cloudflare Tunnel
- Sentry error tracking: backend FastAPI + Celery + frontend React
- UptimeRobot monitoring su `/health`
- Backup automatico PostgreSQL ogni notte alle 02:00 (rotazione 30 giorni)
- PWA icon aggiornata con cache-busting

## [1.1.0] — 2026-04-01
### Added
- Pagina Allocazioni: donut chart per piattaforma, valuta, asset class, settore, continente, holdings ETF
- Asset enrichment via Yahoo Finance: settori, paesi, holdings ETF; override manuale
- Performance backend: `asyncio.gather`, MGET bulk Redis, cache `/performance`, endpoint aggregato `/portfolio/dashboard`
- Sistema SMTP: reset password self-service, email di benvenuto, test configurazione
- Pannello Admin: gestione utenti, audit log, invio email manuali

## [1.0.0] — 2026-01-15
### Added
- Setup iniziale: React + FastAPI + PostgreSQL + Redis + Celery
- Autenticazione JWT con refresh token, TOTP 2FA opzionale, ruoli SUPERADMIN/USER
- Gestione asset e transazioni (BUY/SELL/DIVIDEND/COUPON/FEE/INTEREST) con multi-valuta e tassi BCE
- Market data: Yahoo Finance, CoinGecko, Borsa Italiana API; WebSocket prezzi live
- Portfolio engine: P&L FIFO, TWRR, IRR/XIRR, benchmark, correlazione, rischio
- Tax engine italiano: aliquote 26%/12.5%, zainetto fiscale multi-anno, simulatore vendita
- Alert prezzi con Celery Beat; import CSV (Fineco, Directa, Degiro, IBKR); export Excel/Ghostfolio
- PWA: manifest, icone, offline fallback, install prompt
- Docker Compose production-ready
