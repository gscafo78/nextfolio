# Changelog

Tutte le modifiche rilevanti sono documentate in questo file.
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) · Versioning: [SemVer](https://semver.org/lang/it/)

---

## [1.15.1] — 2026-11-20
### Fixed
- **Storico prezzi assente per alcuni BTP/obbligazioni MOT**: Borsa Italiana censisce i grafici di alcuni titoli con un codice di mercato diverso da quello in cui sono negoziati (es. `IT0005619546` negoziato sul MOT ma con grafici su `XMIL`): con `MOTX` rispondeva 400 «InstrumentKey non valido» e il titolo restava senza prezzi né storico. Ora se il mercato previsto non restituisce dati si provano gli altri (MOTX, XMIL, ETLX), ricordando quello che funziona
- Il prezzo corrente ripiega sull'ultima chiusura dello storico anche quando il JWT del mercato previsto non è ottenibile

---

## [1.15.0] — 2026-11-20
### Added
- **Pianificazione fiscale** (scheda Fisco, `GET /planning/tax/overview`): stima imposte dell'anno, zainetto con scadenze, vendite suggerite per usare le minusvalenze in scadenza (ETF esclusi, titoli di Stato al 48,08%) o per compensare le plusvalenze dell'anno, con imposta risparmiata
- **Simulazione vendite multiple** (`POST /planning/tax/simulate-sales`): plus/minus al costo medio e imposte dell'anno prima/dopo, uso dello zainetto
- **Confronto titoli** (scheda Confronto, `POST /planning/compare`): 2–4 titoli anche non in portafoglio, serie ribasate, rendimenti, rischio, correlazione, sovrapposizione delle holding tra ETF
- **Backtest portafoglio modello** (`POST /planning/backtest`): pesi, capitale iniziale, versamenti mensili, ribilanciamento nessuno/annuale/a soglia, benchmark
- Tool MCP di lettura `compare-securities`, `simulate-sale-tax`
- `carryforward_pools()` nel motore fiscale: zainetto residuo dopo tutti gli eventi

---

## [1.14.0] — 2026-11-20
### Added
- **Versamento intelligente** (scheda Versamento): allocazione obiettivo per asset class con tolleranza e strumenti preferiti (migration `0028`, `GET/PUT /planning/targets`), barre di scostamento (`GET /planning/drift`) e avviso in dashboard, suggerimento "solo acquisti" per un importo o per la liquidità (`POST /planning/contribution`) con quote intere, ordine minimo e commissioni, apertura nel simulatore
- **Obiettivi** (scheda Obiettivi): proiezione Monte Carlo a 5.000 scenari (`POST /planning/projection`) con probabilità, percentili in euro di oggi e versamento necessario per l'80%; ipotesi per asset class modificabili; obiettivi salvati (`/planning/goals`)
- **FIRE** (`POST /planning/fire`): capitale necessario, anni stimati, probabilità che il capitale duri, prelievo sostenibile al 90%
- Tool MCP di lettura `suggest-contribution`, `project-goal`

### Changed
- Il calcolatore PAC è nella scheda Obiettivi (proiezione semplice); `/strumenti` reindirizza lì e la voce Strumenti esce dal menu
- Ribilanciamento di X-Ray raggruppato per asset class del sottostante (un ETF obbligazionario conta come obbligazioni)
- Ricerca: con un ISIN già presente in Nextfolio non si aggiungono altre quotazioni da Yahoo; cache di yfinance in `/tmp`

---

## [1.13.0] — 2026-11-19
### Added
- **Pagina Pianifica** (`/pianifica`, icona `Compass`; i18n IT/EN/FR/DE)
- **Ricerca titoli** (`GET /planning/search`): nome, ticker o ISIN con suggerimenti dopo 3 caratteri, da Nextfolio e da Yahoo Finance, filtro per tipo, navigazione da tastiera
- **Scheda titolo** (`GET /planning/security`): prezzo in EUR, grafico 3 anni, rendimento 1A e 3A/5A annuo, volatilità e max drawdown, asset class, valute, settori, paesi e principali titoli; aggiunta alla watchlist anche per titoli non ancora in Nextfolio (`POST /planning/security/import`)
- **Simulatore d'acquisto** (`POST /planning/simulate`): acquisti ipotetici con denaro nuovo o liquidità dei conti, prima/dopo di patrimonio, liquidità, asset class, valute, pesi e regole X-Ray
- **Scenari** (migration `0027`): salva, confronta fino a 4 (`/planning/scenarios/compare`), esegui come transazioni reali (`/execute`, tutto-o-niente, doppioni saltati, titoli Yahoo importati automaticamente)
- Tool MCP di lettura `search-securities`, `simulate-purchase`, `get-scenarios`
- Dati Yahoo per titoli esterni in cache Redis (`services/market_data/external.py`); prezzi in pence (`GBp`) gestiti

### Changed
- Snapshot del portafoglio spostato in `services/portfolio/snapshot.py` (condiviso da report AI e Pianifica); inserimento transazioni in blocco in `services/transaction.create_transactions_batch` (usato da MCP ed esecuzione scenari)
- La ricerca asset locale cerca anche nel ticker Yahoo e accetta un filtro per tipo

---

## [1.12.0] — 2026-11-19
### Added
- **Saldo di cassa per conto** (migration `0026`, tabella `account_balances`): storico per data, il più recente è quello corrente, un nuovo saldo nella stessa data sostituisce il precedente; date future rifiutate; conversione in EUR per conti in altra valuta
- Impostazioni → Conti: saldo corrente sotto ogni conto, "Aggiorna saldo" e storico con cancellazione
- API `GET/POST /accounts/{id}/balances`, `DELETE /accounts/{id}/balances/{balance_id}`; `GET /accounts` restituisce l'ultimo saldo
- Dashboard e riepilogo: `cash_eur` e `net_worth_eur` (investimenti + liquidità)
- Allocazione: liquidità in "Monetario", nella valuta del conto e nel peso del conto
- X-Ray: la riserva di liquidità conta il saldo di cassa
- Report e MCP: liquidità e patrimonio totale nel riepilogo, saldo e data nella tabella conti; tool `update-account-balance` (permesso di scrittura)

---

## [1.11.0] — 2026-11-19
### Added
- **Server MCP in scrittura**: permessi per token `can_write` e `can_delete` (migration `0025`), scelti alla creazione nella pagina AI e mostrati nella lista token
- Tool di scrittura: `create-asset` (idempotente per ISIN), `update-asset` (asset class, trattamento fiscale, quota titoli di Stato ETF, look-through), `create-transactions` (fino a 100, tutto-o-niente, doppioni saltati), `update-transaction`, `add-to-watchlist`, `update-watchlist-item`, `create-alert`, `update-alert`
- Tool di cancellazione (`destructiveHint`): `delete-transaction`, `remove-from-watchlist`, `delete-alert`
- Tool di lettura `search-assets` e `get-alerts`; colonna ID in `get-transactions` e `get-watchlist`
- Ogni scrittura MCP nel log di audit (`MCP_*`, `via: mcp`, id del token), con etichette nella pagina Amministrazione

### Fixed
- **Alert di prezzo**: `alert_type` letto dal DB come stringa faceva fallire lista e creazione degli alert (`.value` su `str`) e bloccava l'invio delle email
- La cache della performance ora si invalida dopo creazione, modifica, cancellazione e import CSV di transazioni (prima restava vecchia fino a 5 minuti)
- Test: login con JSON (i test autenticati di `test_api.py` venivano sempre saltati), `NullPool` nei test per evitare connessioni legate a event loop chiusi

---

## [1.10.0] — 2026-11-19
### Added
- **Pagina AI** (`/ai`, icona `Sparkles` in Sidebar; i18n IT/EN/FR/DE), ispirata alle funzioni AI/MCP di Ghostfolio
- **Prompt per chatbot**: `GET /api/v1/ai/prompt` genera un testo con riepilogo, posizioni, allocazione (tipo/valuta/conto/settore/area), performance TWRR, XIRR, metriche di rischio, X-Ray e dividendi in tabelle Markdown, più le istruzioni di analisi (modalità `analysis`) o solo i dati (modalità `portfolio`); filtri per conto e tipo asset; importi in EUR opzionali (default disattivati in Zen Mode); pulsante Copia
- **Server MCP in sola lettura** su `/api/mcp` (SDK `mcp` 2.x, Streamable HTTP stateless): tool `get-portfolio`, `get-allocation`, `get-accounts`, `get-transactions`, `get-performance`, `get-risk-metrics`, `get-xray`, `get-dividends`, `get-watchlist`, `get-tax-report`
- **Token di accesso MCP** per utente (`nfmcp_…`, salvati come SHA-256, mostrati una sola volta, revocabili, permesso opzionale "leggi importi"); `GET/POST/DELETE /api/v1/ai/mcp-tokens`; azioni audit `CREATE_MCP_TOKEN` / `REVOKE_MCP_TOKEN`
- Migration `0022_mcp_tokens`: tabella `mcp_access_tokens`
- Variabile `ENABLE_MCP` (default `true`)
- **Trattamento fiscale manuale delle obbligazioni**: campo `govt_bond_override` sugli asset (migration `0023`), selettore "Trattamento fiscale" nel modale *Modifica titolo*
- Simulatore vendita: parametro opzionale `account_id` per usare il costo medio di un conto specifico

### Fixed — performance e rischio
- **Metriche di rischio gonfiate dai flussi di cassa**: i rendimenti giornalieri ora sono neutralizzati dai flussi (acquisti a inizio giornata, vendite e proventi a fine giornata), anche per flussi in giorni senza prezzi (prima un acquisto nel weekend diventava un "rendimento" il giorno dopo); volatilità, Sharpe, Sortino, miglior/peggior giorno ricalcolati su questi rendimenti
- **Giorni di borsa**: un giorno conta solo se almeno metà del valore ha un prezzo nuovo (niente weekend/festivi piatti da una crypto o da una borsa aperta)
- **Max drawdown** sull'indice TWRR invece che sul valore (una vendita non è un drawdown); basi minime (< 1% del valore massimo o 50 €) escluse dalle metriche
- **Risk-free configurabile** (`RISK_FREE_RATE_PCT`), convertito in giornaliero composto; Sortino con target = risk-free; TWRR annualizzato e Calmar solo con almeno un anno di dati
- **Avvisi "dati sospetti"** (`warnings`) se |rendimento giornaliero| > 20%, volatilità > 60%, Sharpe > 3 o miglior/peggior giorno > 15%
- **TWRR con proventi inclusi** (cedole, dividendi, interessi; costi FEE sottratti): prima i proventi erano esclusi
- **P&L per periodo**: `GET /portfolio/performance` restituisce valore iniziale, flussi netti, proventi, P&L = fine − inizio − flussi + proventi e Investito = inizio + flussi; `history_truncated` se lo storico è più corto del periodo (3Y = n/d nel report)
- **Doppia conversione valutaria** nello storico: i prezzi di `price_history` sono già in EUR e non vengono più moltiplicati per il cambio delle transazioni
- **P&L totale** (dashboard, sommario, report) include i proventi incassati e il realizzato delle posizioni chiuse; nuovo campo `income_eur`

### Fixed — classificazione e X-Ray
- **Asset class per sottostante** (`by_asset_class`): ETF obbligazionari e monetari riconosciuti dal nome/look-through, ETF bilanciati ripartiti; override manuale `asset_class_override` (migration `0024`, campo nel modale *Modifica titolo*)
- **Concentrazione singolo titolo** solo su azioni e obbligazioni singole: ETF e fondi esclusi
- **Riserva di liquidità**: solo monetario e obbligazioni con vita residua ≤ 12 mesi (scadenza da `bond_details` o dal nome, es. "Dc30"); un BTP 2030 non è più liquidità
- **Settori**: ETF obbligazionari in "Bonds" invece di "Non classificato"
- **Geografia** separata per azionario e obbligazionario (`by_continent_equity`, `by_continent_bond`); home bias sull'azionario; nuova regola **Esposizione Italia** (BTP inclusi, `italy_exposure_pct`)
- **Esposizione valutaria look-through** (`by_currency_exposure`, ETF hedged = EUR) usata dalla regola "Copertura EUR"

### Fixed — report e fiscalità
- Report: ticker al posto dell'ISIN nel campo simbolo, broker dedotto da nome/URL del conto se vuoto, imposta patrimoniale stimata per conto (IVAFE 0,2% sui conti esteri, bollo 0,2% sugli intermediari italiani)
- Report: nuova sezione Fiscalità con plusvalenze per tipo di reddito (redditi diversi vs redditi di capitale) e scadenziario a 4 anni delle minusvalenze
- **ETF con quota di titoli di Stato** (`govt_bond_share`, migration `0024`): plus/minus del fondo con base ridotta (quota al 48,08%)

### Fixed — motore fiscale
- **Titoli di Stato riconosciuti dal nome/emittente** (BTP/BOT/CCT/CTZ, Bund, OAT, Treasury, BEI, BIRS…) invece che dall'ISIN `IT`: le obbligazioni societarie italiane tornano al 26%, i titoli di Stato white list e sovranazionali passano al 12,5%
- **Zainetto unico al 48,08%**: plus/minus su titoli di Stato entrano nello stesso zainetto dei redditi diversi ponderate a 12,5/26, invece di due zainetti separati non compensabili
- **ETF/OICR**: le plusvalenze sono redditi di capitale (26% pieno, non compensabili con lo zainetto); le minusvalenze alimentano lo zainetto
- **Costo medio ponderato anche in regime dichiarativo** (art. 68 c.6 TUIR) al posto del FIFO; il simulatore vendita usa lo stesso costo (prima usava sempre FIFO, anche per i conti amministrati)
- **Cripto-attività al 33% dal 2026** (L. 207/2024), con zainetto separato
- PDF fiscale e "Cosa dichiarare": rimossi i numeri di rigo RT non verificati, aggiunte le voci cripto e ETF (quadro RM)
- `test_tax.py`: fixture allineate al modello (campo `isin`, conto con regime fiscale); nuovi test su PMC, titoli di Stato, zainetto, ETF, cripto e simulatore

### Changed (API)
- `GET /tax/report`: rimossi i campi dello zainetto separato dei titoli di Stato (`carryforward_applied_govt`, `net_taxable_govt`, `tax_govt`, `new_carryforward_govt`, `prior_carryforward_govt`, `*_tax_govt`); aggiunti `govt_weight`, `taxable_*`, `*_funds`, `*_crypto`, `crypto_rate`; `tax_bracket` degli eventi può valere anche `fund` e `crypto`

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
