# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (port 3433)
```bash
cd musicflow
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3433 --reload

pip install -r backend/requirements.txt
```

### Frontend (port 3434)
```bash
cd musicflow/frontend
npm run dev      # Vite dev server on :3434, proxies /api and /files to :3433
npm run build
npm run lint
```

Frontend: http://localhost:3434 | Backend: http://localhost:3433

## Default Admin Account

- Email: `admin@musicflow.com`
- Password: `admin123`
- Seeded on first boot in `main.py` → `seed_data()`

## Architecture

**MusicFlow** is a full-stack SaaS platform for AI music creation, built on MiniMax APIs.

### Backend (FastAPI + SQLAlchemy async + SQLite)

The backend follows a 4-layer pattern: **Router → Service → MiniMax Client → API**.

- `backend/main.py` — App entry, lifespan seeds admin user + default pricing rules
- `backend/config.py` — All env vars loaded from `../.env` (MiniMax keys, LLM config, JWT secrets, DB URL)
- `backend/database.py` — Async SQLAlchemy engine + session factory
- `backend/routers/` — FastAPI route handlers. Each router handles billing (deduct before call, refund on failure)
- `backend/services/` — Business logic. Each service builds MiniMax API payloads and processes responses
- `backend/services/minimax_client.py` — Single HTTP client for all MiniMax API calls (Bearer auth, 120s timeout)
- `backend/services/agent_tools.py` — **Largest file (~750 lines)**. Defines 13 OpenAI function-calling tools that the AI agent can invoke. Each tool has an `openai_schema`, `executor`, `service_type` (for billing), and `require_confirmation` flag
- `backend/services/agent_service.py` — Orchestrates LLM ↔ tool-calling loop with streaming SSE
- `backend/services/llm_client.py` — OpenAI-compatible LLM wrapper (currently using Gemini via proxy)
- `backend/schemas/` — Pydantic request/response models
- `backend/models/` — SQLAlchemy ORM models (User, Generation, Transaction, AgentSession, PricingRule, etc.)

### Frontend (React 19 + Vite + Tailwind CSS 4 + Zustand)

- `frontend/src/App.jsx` — React Router v7 route definitions
- `frontend/src/pages/agent/AgentWorkspace.jsx` — Main AI chat interface with tool confirmation cards
- `frontend/src/store/authStore.js` — Auth state (JWT tokens, user profile)
- `frontend/src/store/agentStore.js` — Agent conversation state, tool request handling
- `frontend/src/api/` — Axios HTTP client with token interceptor

### Key Data Flow: Agent Tool Calling

1. User sends message → `routers/agent.py` streams SSE
2. `agent_service.py` calls LLM with tool schemas from `agent_tools.py`
3. LLM returns `tool_calls` → agent pauses for user confirmation (if `require_confirmation=True`)
4. User confirms → executor runs the corresponding service function
5. Service function calls MiniMax API via `minimax_client.py`
6. Billing: `check_and_deduct()` before execution, `refund_credits()` on failure

### Credit System

Dual credits: paid credits (purchased) + free credits (daily check-in). Pricing is defined in `DEFAULT_PRICING` in `main.py` and seeded to `PricingRule` table on first boot. 1 credit = 0.01 CNY.

### Generated Files

Audio outputs go to `output/` directory, served at `/files/` via FastAPI StaticFiles mount.

## Environment Variables (.env)

Required in `musicflow/.env`:
- `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` — MiniMax API access
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` — OpenAI-compatible LLM for agent
- `SECRET_KEY` — JWT signing key
- `DATABASE_URL` — Default: `sqlite+aiosqlite:///./data/musicflow.db`

## MiniMax API Integration

All MiniMax calls go through `minimax_client.py`. The API endpoints used:
- `/v1/music_generation` — Music + cover generation
- `/v1/lyrics_generation` — Lyrics creation
- `/v1/t2a_v2` — Sync speech synthesis
- `/v1/t2a_async_v2` — Async speech synthesis (long text)
- `/v1/voice_clone`, `/v1/voice_design`, `/v1/get_voice`, `/v1/delete_voice` — Voice management
- `/v1/files/upload` — File upload for voice cloning

API documentation files are in the project root (`music-generation-api.md`, `sync-speech-synthesis-http.md`, etc.).
