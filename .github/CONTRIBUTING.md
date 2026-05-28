# Contributing to Nextfolio

Thank you for your interest in contributing! This document explains how to get set up, the conventions we follow, and what a good pull request looks like.

---

## Development Setup

### Requirements

- Docker ≥ 24 and Docker Compose v2
- Node.js ≥ 20 (optional — only if you want to run the frontend outside Docker)
- Python ≥ 3.11 (optional — only if you want to run the backend outside Docker)

### Start the Dev Stack

```bash
git clone https://github.com/your-username/nextfolio.git
cd nextfolio
docker compose -f docker-compose.dev.yml up -d
```

The dev compose mounts source code as volumes, so edits to `frontend/src/` and `backend/app/` hot-reload without rebuilding containers.

### Running Tests

```bash
# Backend unit + integration tests
docker exec nextfolio_backend pytest -v --cov=app

# Frontend type check
docker exec nextfolio_frontend npm run type-check
```

---

## Project Structure

```
frontend/src/
├── components/       # Reusable UI components
│   ├── ui/           # Generic design-system primitives
│   ├── portfolio/    # Portfolio-specific components
│   └── layout/       # App shell (sidebar, nav)
├── pages/            # One file per route
├── services/         # Axios API clients
├── store/            # Zustand global state
└── hooks/            # Custom React hooks

backend/app/
├── api/v1/endpoints/ # FastAPI route handlers
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic I/O schemas
├── services/         # Business logic
└── tasks/            # Celery async tasks
```

---

## Conventions

### Git Branches

| Pattern | Purpose |
|---|---|
| `feat/short-description` | New feature |
| `fix/short-description` | Bug fix |
| `refactor/short-description` | Refactoring with no behaviour change |
| `docs/short-description` | Documentation only |
| `chore/short-description` | Build, tooling, dependencies |

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
feat: add dividend projection chart
fix: correct FIFO lot matching when quantity is fractional
docs: add API rate limit section
chore: upgrade FastAPI to 0.112
```

### Python Style

- Formatter: **Ruff** (`ruff format`)
- Linter: **Ruff** (`ruff check`)
- Type hints on all public functions
- Async wherever I/O is involved

### TypeScript / React Style

- Formatter: **Prettier**
- Linter: **ESLint**
- Functional components only — no class components
- Props typed with explicit interfaces, not inline `{}` types

---

## Database Migrations

If your change requires schema changes, create a new Alembic migration:

```bash
docker exec nextfolio_backend \
  alembic revision --autogenerate -m "add_column_x_to_table_y"
```

Review the generated file in `backend/alembic/versions/` — autogenerate is not always perfect.

---

## Pull Request Guidelines

1. **One concern per PR.** Split unrelated changes into separate PRs.
2. **Write tests** for any new business logic (especially P&L or tax calculations).
3. **No secrets** — double-check that no API keys, passwords, or `.env` values are included.
4. **Update docs** if you change behaviour that is documented in `docs/`.
5. Fill in the PR template completely.

---

## Reporting Issues

Use the GitHub issue templates:

- **Bug report** — for unexpected behaviour or errors
- **Feature request** — for new functionality proposals

Search existing issues before opening a new one.
