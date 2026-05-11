# 🍽️  AI Restaurant Receptionist — FastAPI Backend

A production-ready FastAPI backend for an AI-powered restaurant receptionist.
Guests chat with the system in natural language; the AI uses tool-calling to
check availability, create, and cancel reservations against a PostgreSQL store.

## Features

- **OpenAI integration** with function/tool calling so the model can take real actions
- **Conversation memory** — every session is persisted; the last N messages are replayed as context
- **Reservation system** with capacity checks, opening-hour validation, and a full status lifecycle
- **PostgreSQL** via async SQLAlchemy 2.x + asyncpg
- **Clean architecture**: API → Service → Repository → Model
- **12-factor configuration** through Pydantic `BaseSettings` + `.env`
- **Fully async** end to end (no blocking DB or HTTP calls)
- **Alembic migrations** with a baseline migration included
- **Dockerized** (Dockerfile + docker-compose)
- **Test suite** using pytest + httpx with an in-memory SQLite override

## Architecture

```
app/
├── api/
│   ├── dependencies.py        # FastAPI DI wiring
│   └── v1/
│       ├── endpoints/
│       │   ├── chat.py
│       │   └── reservations.py
│       └── router.py
├── core/
│   ├── config.py              # Pydantic settings (env vars)
│   ├── exceptions.py
│   └── logging.py
├── db/
│   ├── base.py                # Declarative base + timestamp mixin
│   └── session.py             # Async engine + get_db()
├── models/                    # SQLAlchemy ORM models
├── schemas/                   # Pydantic request/response schemas
├── repositories/              # Data-access layer
├── services/                  # Business logic
│   ├── ai_service.py          # OpenAI + memory + tool dispatch
│   └── reservation_service.py
└── main.py                    # App factory + lifespan
alembic/                       # DB migrations
tests/                         # pytest suite
```

Each chat turn flows: resolve session → persist user message → load history
window → call OpenAI with tools → if tool called, dispatch via
`ReservationService` and loop → persist assistant reply → return.

## Quick start

```bash
# 1. Configure
cp .env.example .env       # then fill in OPENAI_API_KEY

# 2a. With Docker Compose (recommended)
docker compose up --build

# 2b. Local Python
pip install -r requirements.txt
docker compose up -d db    # just the DB
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## API

| Method | Path | Purpose |
|---|---|---|
| POST   | `/api/v1/chat` | Send a message to the receptionist |
| GET    | `/api/v1/chat/{session_id}/history` | Full transcript |
| POST   | `/api/v1/reservations` | Create a reservation |
| GET    | `/api/v1/reservations` | List reservations |
| GET    | `/api/v1/reservations/{id}` | Get one |
| PATCH  | `/api/v1/reservations/{id}` | Update |
| DELETE | `/api/v1/reservations/{id}` | Cancel (soft) |
| GET    | `/health` | Liveness probe |

### Example

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hi, can I book a table for 4 tomorrow at 7pm? Name Ada, phone 555-1234."}'
```

Send the returned `session_id` back on subsequent calls to maintain memory.

## Tests

```bash
pytest -v
```

Tests run against in-memory SQLite — no PostgreSQL required.

## Production notes

- Set `ENVIRONMENT=production` and `DEBUG=false` to disable `/docs` and `/redoc`
- Pin `CORS_ORIGINS` to your frontend domain
- Run behind a reverse proxy for TLS
- Scale with `uvicorn --workers N` or gunicorn-uvicorn workers
- Add rate limiting (e.g. slowapi) and an auth layer before exposing publicly
