# Nextfolio

Wealth management per il mercato italiano.

**Stack:** React + TypeScript · FastAPI · PostgreSQL · Redis · Celery

## Avvio rapido (Docker)

```bash
# Copia variabili d'ambiente
cp .env.example .env

# Avvia tutti i servizi (backend, frontend, postgres, redis)
docker compose -f docker-compose.dev.yml up -d

# Segui i log (opzionale)
docker compose -f docker-compose.dev.yml logs -f
```

Frontend: http://localhost:5173  
API docs: http://localhost:8000/docs

> **Primo avvio:** registra il primo utente tramite `POST /api/v1/auth/register`
> — diventa automaticamente **Superadmin**. Le registrazioni successive sono bloccate;
> nuovi utenti si creano dalla pagina **Amministrazione** nell'app.

## Accesso SSH con port forwarding

Se l'app gira su un server remoto, raggiungi l'UI in locale con:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 utente@ip-server
```

Poi apri http://localhost:5173 nel browser locale.

## Architettura prezzi

| Fonte               | Asset                          | Frequenza            |
|---------------------|--------------------------------|----------------------|
| Yahoo Finance       | Azioni .MI, ETF, Bond MOT      | ogni 15 min (borsa)  |
| CoinGecko           | Crypto                         | ogni 5 min           |
| Borsa Italiana API  | ISIN su MIL / EuroTLX / MOT   | ogni 15 min (borsa)  |
| BCE (Frankfurter)   | Tassi di cambio FX             | on-demand            |

I prezzi sono cachati su Redis (5 min azioni, 1 min crypto) e trasmessi
in real-time ai client via WebSocket (`/ws/prices`).

## Ruoli e permessi

| Ruolo       | Permessi                                                          |
|-------------|-------------------------------------------------------------------|
| SUPERADMIN  | Tutto: crea/modifica/elimina utenti, resetta 2FA altrui           |
| USER        | Solo impostazioni personali (valuta, tema) e 2FA del proprio account |

## Autenticazione a due fattori (TOTP)

La 2FA è opzionale per tutti gli utenti e si configura dalla pagina **Impostazioni**:

1. Clicca "Configura 2FA" → scansiona il QR code con un'app TOTP (Google Authenticator, Aegis, ecc.)
2. Inserisci il codice a 6 cifre per attivare
3. Al prossimo login verrà richiesto il codice dopo email e password

## Comandi utili

```bash
# Ricostruire un singolo servizio (es. dopo modifica requirements.txt)
docker compose -f docker-compose.dev.yml build backend
docker compose -f docker-compose.dev.yml up -d backend

# Installare un pacchetto npm nel container frontend in esecuzione
docker exec nextfolio_frontend npm install <pacchetto>

# Eseguire migration manualmente
docker exec nextfolio_backend alembic upgrade head

# Eseguire test backend
docker exec nextfolio_backend pytest -v --cov=app

# Avviare Celery worker (non incluso nel compose dev di default)
cd backend && celery -A app.tasks.celery_app:celery_app worker --loglevel=info
```
