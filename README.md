# Tech Support AI

AI-powered web chat for Zammad ticket management. See `docs/` for functional, technical, UI/UX, and implementation strategy documents.

## Prerequisites

- Docker Desktop (or Docker Engine) with Compose
- [uv](https://docs.astral.sh/uv/) (Python 3.12+)
- Node.js 20+

## Quick start (&lt; 15 minutes)

### 1. Clone and configure

```bash
cp .env.example .env
```

### 2. Start the stack (Docker Compose)

**Infrastructure only** (run API/web locally with `make api` / `make web`):

```bash
docker compose up -d postgres redis minio minio-init
```

**Full stack** (API + web + Postgres + Redis + MinIO in containers):

```bash
docker compose up -d --build
# Web UI: http://localhost:5173  ·  API: http://localhost:8000/docs
```

Wait until services are healthy (`docker compose ps`).

**Local port mapping** (avoids conflicts with existing services):

| Service | Host port |
| ------- | --------- |
| Postgres | 5433 |
| Redis | 6380 |
| MinIO API | 9002 |
| MinIO Console | 9003 |

### 3. Install dependencies

Creates a Python virtualenv at **`.venv/`** in the project root (required for `make migrate` and `make api`):

```bash
make install
```

If you prefer [uv](https://docs.astral.sh/uv/), install it first — `make install` will use `uv sync` automatically.

### 4. Run database migrations

```bash
make migrate
```

If you see `No such file or directory` for `.venv/bin`, run `make install` first.

### 5. Start API and web UI

Terminal A:

```bash
make api
# API: http://localhost:8000 — docs at /docs
```

Terminal B:

```bash
make web
# UI: http://localhost:5173
```

The web app sends `X-User-Id: dev-user@company.com` for local auth (Sprint 12 adds OIDC).

### 6. Verify health

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Repository layout

```text
apps/
  api/          FastAPI + Alembic
  web/          React + Vite chat UI
packages/
  shared/       JSON schemas, reason codes
  orchestration/  Policy + workflow (Sprint 3)
  zammad-client/  Zammad HTTP client (Sprint 3)
  agents/       LangGraph graphs (Sprint 5)
config/
  providers/zammad/mapping.yaml
  policy/v1/
docs/
```

## Development commands

| Command | Description |
| ------- | ----------- |
| `make up` | Start Postgres, Redis, MinIO |
| `make migrate` | Apply Alembic migrations |
| `make api` | Run FastAPI (reload in dev) |
| `make web` | Run Vite dev server |
| `make test` | pytest + vitest |
| `make test-live` | Live OpenAI + Zammad integration (API, with logging) |
| `make test-live-ui` | Same tests in **visible browser** — watch the User Sim chat |
| `make e2e` | Playwright E2E (Docker + Wiremock + mock LLM) |
| `make e2e-ui` | Playwright interactive UI mode |
| `make lint` | ruff + eslint |

## API (Sprint 2)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health/live` | Liveness |
| GET | `/health/ready` | Readiness (Postgres + Redis) |
| GET | `/api/v1/chat/sessions` | List recent sessions for user |
| POST | `/api/v1/chat/sessions` | Create session (`X-User-Id` or `Bearer` JWT) |
| GET | `/api/v1/chat/sessions/{id}` | Get session |
| GET | `/api/v1/chat/sessions/{id}/context` | Redis session context |
| GET | `/api/v1/chat/sessions/{id}/messages` | Paginated message history |
| POST | `/api/v1/chat/sessions/{id}/messages` | Send message (LangGraph + OpenAI when enabled) |
| POST | `/api/v1/chat/sessions/{id}/graph/invoke` | Stateless graph turn |

Postman collection: `docs/postman/Tech-Support-AI.postman_collection.json`

**Session persistence:** The web UI stores `session_id` in `localStorage` and resumes on refresh.

## Implementation status

- **Sprint 1:** Monorepo, Docker Compose, sessions/messages, health API, ChatShell UI
- **Sprint 2:** Redis context, JWT auth stub, session resume, shared TS types
- **Sprint 3:** Zammad client, orchestration, audit tables, create-ticket CLI
- **Sprint 4:** Mock graph in chat, system status UI, Zammad sandbox E2E script
- **Sprint 5:** LangGraph `support_graph`, orchestrate + zammad nodes, Postgres checkpointer option
- **OpenAI LLM:** Direct OpenAI via `GRAPH_LLM_MODE=openai` (structured intent extraction)

## OpenAI (conversation LLM)

Set in `.env` (see `.env.example`):

```env
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

The API loads these at startup and uses OpenAI structured output to classify intents and extract ticket fields. Orchestration and Zammad calls remain deterministic (not in the LLM prompt).

Use `GRAPH_LLM_MODE=mock` for offline tests or when no API key is available.

## Zammad sandbox

Configure `config/providers/zammad/mapping.yaml` against your Zammad sandbox and set `ZAMMAD_BASE_URL` / `ZAMMAD_API_TOKEN` in `.env`.

### Create ticket (Sprint 3 CLI)

```bash
make migrate
export ZAMMAD_BASE_URL=https://your-zammad.example.com
export ZAMMAD_API_TOKEN=your-api-token
make create-ticket ARGS='--email john@company.com --title "VPN issue" --description "Cannot connect" --category network --priority high'
```

Dry-run (orchestration only; uses `.venv` automatically if present):

```bash
python3 scripts/create_ticket.py --dry-run --email john@company.com --title "VPN" --description "Test"
# or: .venv/bin/python scripts/create_ticket.py --dry-run ...
```

If you see `ModuleNotFoundError`, run `make install` first, or use `.venv/bin/python` explicitly.

## E2E tests (Playwright)

Fully automated browser tests against the real API and web UI. Uses **mock LLM** (`GRAPH_LLM_MODE=mock`) and **Wiremock** for Zammad — no OpenAI or sandbox credentials required.

```bash
make e2e
# Interactive debugger: make e2e-ui
```

**What runs:** Docker Compose starts Postgres, Redis, and Wiremock; Playwright starts the API (`:8010`) and Vite dev server (`:5174`) so they do not conflict with `make api` / `make web`.

**Specs:** `e2e/tests/` — session bootstrap, greeting, create ticket (#22042 from Wiremock), session resume, new chat.

## Live integration tests (OpenAI + Zammad)

Ten multi-turn scenarios using **real OpenAI**, **real Zammad**, and an **AI User Simulator** that role-plays an employee reporting each issue — no scripted follow-ups, no mocks.

Full strategy: [`docs/test-strategy-live-integration.md`](docs/test-strategy-live-integration.md)

**Required `.env` variables:**

```env
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ZAMMAD_BASE_URL=https://your-zammad.example.com
ZAMMAD_API_TOKEN=...
ZAMMAD_TEST_EMAIL=you@company.com
```

**Optional:**

```env
USER_SIM_MODEL=gpt-4o-mini      # defaults to OPENAI_MODEL
USER_SIM_TEMPERATURE=0.4
INTEGRATION_MAX_TURNS=12
```

**Run (API — headless, with console logging):**

```bash
docker compose up -d postgres redis   # required
make migrate
make test-live
```

**Run (browser — watch progress in Chromium):**

```bash
make test-live-ui

# Single scenario in browser:
INTEGRATION_HEADLESS=false .venv/bin/pytest tests/integration -m live_ui -k vpn_network -v -s --log-cli-level=INFO
```

Logs go to the terminal and to `tests/integration/artifacts/live_integration.log`. Each run also saves a JSON transcript per scenario.

**Optional tuning:**

```env
INTEGRATION_HEADLESS=false       # show browser (default true for test-live, false for test-live-ui)
INTEGRATION_SLOW_MO=350            # ms delay between UI actions (browser mode)
INTEGRATION_UI_PAUSE_MS=2500     # pause on success so ticket card stays visible
LIVE_API_PORT=8020                 # API port for browser mode (default)
LIVE_WEB_PORT=5175                 # Web UI port for browser mode (default)
```

- Scenarios: `tests/integration/scenarios.py` (fact sheets + personas)
- User Sim: `tests/integration/user_sim/`
- Transcripts (on failure or success): `tests/integration/artifacts/` (gitignored)

Expect several minutes runtime and OpenAI API cost (two LLM calls per turn). Tickets are created in your Zammad sandbox — safe to close after the run.
