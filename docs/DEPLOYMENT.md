# Deployment Guide

This guide covers three production deployment modes and one development setup.

---

## Prerequisites

- **Docker** ≥ 24 and **Docker Compose** v2 on the target host
- A domain name pointed at your server (for HTTPS modes)
- At least 1 GB RAM and 10 GB disk

---

## 1. Development

Use the dedicated dev compose file. It mounts source code as volumes so changes hot-reload without rebuilding.

```bash
cp .env.example .env          # defaults are already filled for dev
docker compose -f docker-compose.dev.yml up -d
```

| Service   | URL                        |
|-----------|----------------------------|
| Frontend  | http://localhost:5173       |
| Backend   | http://localhost:8000       |
| API docs  | http://localhost:8000/docs  |

No credentials required — PostgreSQL and Redis run without passwords in dev mode.

---

## 2. Production — Cloudflare Tunnel (Recommended)

This mode exposes **no inbound ports** on the server. Traffic flows through Cloudflare's network over an outbound-only tunnel. Ideal for servers behind NAT or without a public IP.

### Setup

1. Create a tunnel at [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → Networks → Tunnels.
2. Copy the tunnel token from the install command.
3. In the tunnel dashboard, add a public hostname pointing to the internal service `http://frontend` (port 80).
4. Configure `.env`:

```bash
cp .env.example .env
# Fill in all required values (see docs/CONFIGURATION.md)
CLOUDFLARE_TUNNEL_TOKEN=your-token-here
```

5. Start with the `cloudflare` profile:

```bash
COMPOSE_PROFILES=cloudflare docker compose up -d
```

### First Run

```bash
# Apply database migrations
docker exec nextfolio_backend alembic upgrade head
```

Register the first user (becomes Superadmin) via the API or the app's registration page — depending on whether it is accessible yet.

---

## 3. Production — HTTPS with Let's Encrypt

Use this mode when the server has a public IP and you want Nginx to handle TLS directly.

### Obtain the Certificate (First Time Only)

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml \
  run --rm certbot certonly --webroot \
    -w /var/www/certbot \
    --cert-name nextfolio \
    --email admin@yourdomain.com \
    -d yourdomain.com \
    --agree-tos --no-eff-email
```

### Start the Stack

```bash
cp .env.example .env
# Fill in all required values
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

Certificates renew automatically — the certbot container checks every 12 hours and renews when expiry is within 30 days.

### Apply Migrations

```bash
docker exec nextfolio_backend alembic upgrade head
```

---

## 4. Production — HTTP (LAN / Internal)

For private networks where TLS is not required (e.g., behind a corporate proxy that handles TLS).

1. Uncomment the `ports` section in `docker-compose.yml` for the frontend service.
2. Start normally:

```bash
cp .env.example .env
docker compose up -d
docker exec nextfolio_backend alembic upgrade head
```

---

## Upgrading

```bash
# Pull latest images / rebuild
git pull
docker compose -f docker-compose.yml pull     # for pre-built images
docker compose -f docker-compose.yml build    # for custom Dockerfiles
docker compose -f docker-compose.yml up -d

# Always run migrations after upgrading
docker exec nextfolio_backend alembic upgrade head
```

---

## Backup & Restore

A backup script is provided at `scripts/backup-postgres.sh`.

```bash
# Manual backup
bash scripts/backup-postgres.sh

# Restore
docker exec -i nextfolio_postgres psql \
  -U nextfolio nextfolio < backup.sql
```

Schedule via cron for automated backups:

```cron
0 3 * * * /opt/nextfolio/scripts/backup-postgres.sh
```

---

## Remote Access via SSH Tunnel

If the app runs on a headless server without a public domain, forward ports locally:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@server-ip
```

Then open http://localhost:5173 in your local browser.

---

## Monitoring & Logs

```bash
# Stream all container logs
docker compose logs -f

# Single service
docker compose logs -f backend

# Resource usage
docker stats
```

### Sentry (Optional)

Set `SENTRY_DSN` (backend) and `VITE_SENTRY_DSN` (frontend) in `.env` to enable automatic error reporting. See [CONFIGURATION.md](CONFIGURATION.md) for details.

---

## Production Checklist

- [ ] All `REQUIRED` variables in `.env` are set (non-empty)
- [ ] `SECRET_KEY` is a random 64-char hex string (`openssl rand -hex 32`)
- [ ] `POSTGRES_PASSWORD` and `REDIS_PASSWORD` are strong random values
- [ ] `CORS_ORIGINS` and `APP_URL` match your public domain
- [ ] Migrations applied: `docker exec nextfolio_backend alembic upgrade head`
- [ ] First Superadmin user created
- [ ] Automated database backups scheduled
- [ ] Log rotation configured (Docker `json-file` driver is pre-configured with 10 MB / 5 files)
