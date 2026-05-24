# Nextfolio

Wealth management per il mercato italiano.

**Stack:** React + TypeScript · FastAPI · PostgreSQL · Redis

## Avvio rapido

```bash
# Copia variabili d'ambiente
cp .env.example .env

# Avvia database e Redis
docker compose -f docker-compose.dev.yml up -d

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (in un altro terminale)
cd frontend
npm install
npm run dev
```

API docs: http://localhost:8000/docs  
Frontend: http://localhost:5173
