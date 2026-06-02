# Changelog

Tutte le modifiche rilevanti sono documentate in questo file.
Formato: [Keep a Changelog](https://keepachangelog.com/it/1.0.0/) · Versioning: [SemVer](https://semver.org/lang/it/)

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
