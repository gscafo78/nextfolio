# ── Stage 1: build (installa dipendenze con compilatori) ──────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime (immagine finale senza build tools) ──────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copia dipendenze pre-compilate
COPY --from=builder /install /usr/local

# Copia sorgenti e rimuove file dev-only
COPY . .
RUN rm -rf tests/ .pytest_cache

# Utente non-root per limitare la blast radius in caso di compromissione
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# --forwarded-allow-ips: uvicorn si fida degli header X-Forwarded-For da nginx
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --forwarded-allow-ips '*'"]
