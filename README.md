# Tech Support AI

Enterprise web chat assistant for IT support ticket management. Employees describe issues in natural language; a **LangGraph** agent extracts structured intent, a **deterministic orchestration layer** validates business rules, and approved actions execute against **Zammad** (or other ticketing providers via a pluggable adapter).

See [`docs/`](docs/) for functional, technical, UI/UX, and implementation strategy documents.

## Features

| Capability | Status |
| ---------- | ------ |
| Web chat UI with session resume | Implemented |
| Multi-turn conversational intake (OpenAI or mock LLM) | Implemented |
| CreateTicket end-to-end (LLM → orchestration → Zammad) | Implemented |
| CheckStatus (search tickets by number / customer) | Implemented |
| Thought streaming (live processing steps over SSE) | Implemented — toggle via `.env` |
| Collapsible processing panel in UI | Implemented |
| Provider abstraction (`zammad` live, `servicenow` stub) | Partial |
| UpdateTicket, attachments, confirm-before-submit | Planned |

### How it works

```text
User (web chat)
    → FastAPI
    → LangGraph support_graph
         conversation (LLM — intent + slot filling)
         orchestrate (Python — policy + workflow, no LLM)
         ticket_tool (Zammad REST API)
         respond
    → Assistant reply + ticket card
```

**Design principle:** the LLM handles language only. Business rules, category→group mapping, and ticket execution are deterministic and auditable.

## Prerequisites

- Docker Desktop (or Docker Engine) with Compose
- [uv](https://docs.astral.sh/uv/) or Python 3.12+
- Node.js 20+

## Quick start (< 15 minutes)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY and Zammad credentials for live ticket creation
```

### 2. Start infrastructure

**Local dev** (run API/web on the host):

```bash
docker compose up -d postgres redis minio minio-init
```

**Full stack in Docker** (API + web + Postgres + Redis + MinIO):

```bash
docker compose up -d --build
# Web UI: http://localhost:5173  ·  API: http://localhost:8000/docs
```

Wait until services are healthy (`docker compose ps`).

| Service | Host port |
| ------- | --------- |
| Postgres | 5433 |
| Redis | 6380 |
| MinIO API | 9002 |
| MinIO Console | 9003 |

### 3. Install dependencies

Creates a Python virtualenv at **`.venv/`** in the project root:

```bash
make install
```

### 4. Run database migrations

```bash
make migrate
```

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

The web app sends `X-User-Id: dev-user@company.com` for local auth (OIDC planned).

### 6. Verify health

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/config/public
```

## Configuration

Key variables in `.env` (see [`.env.example`](.env.example) for the full list):

```env
# LangGraph agent
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai          # openai | mock
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Thought streaming — live "Processing" steps in the chat UI (SSE)
THOUGHT_STREAMING_ENABLED=true

# Ticketing provider
TICKETING_PROVIDER=zammad      # zammad | servicenow (stub)
ZAMMAD_BASE_URL=https://your-zammad.example.com
ZAMMAD_API_TOKEN=...
```

| Variable | Purpose |
| -------- | ------- |
| `GRAPH_LLM_MODE=mock` | Offline dev/tests — no OpenAI key required |
| `THOUGHT_STREAMING_ENABLED` | Enables `POST .../messages/stream` (SSE); UI reads this from `/api/v1/config/public` |
| `VITE_THOUGHT_STREAMING_ENABLED=false` | Optional UI-only override to force-disable streaming |
| `GRAPH_CHECKPOINT=true` | Optional Postgres checkpointer for LangGraph state |

**Local Zammad on host:** use `http://localhost:8080` when running `make api` on the host. Docker Compose rewrites `localhost` → `host.docker.internal` automatically.

Category and group mapping: [`config/providers/zammad/mapping.yaml`](config/providers/zammad/mapping.yaml)

## Repository layout

```text
apps/
  api/              FastAPI BFF, Alembic migrations, chat + graph endpoints
  web/              React + Vite chat UI
packages/
  agents/           LangGraph support_graph (conversation, orchestrate, ticket_tool, respond)
  orchestration/    PolicyValidator, WorkflowEngine, OrchestrationEngine
  ticketing/        Provider gateway (Zammad adapter, ServiceNow stub)
  zammad-client/    Zammad HTTP client
  shared/           JSON schemas, reason codes
config/
  providers/zammad/mapping.yaml
  providers/servicenow/mapping.yaml
docs/               Architecture, FSD, test strategy
tests/integration/  Live OpenAI + Zammad + AI User Simulator
e2e/                Playwright browser tests (mock LLM + Wiremock)
scripts/            create_ticket CLI, Zammad sandbox E2E
```

## Development commands

| Command | Description |
| ------- | ----------- |
| `make up` | Start Postgres, Redis, MinIO |
| `make up-all` | Full Docker stack (API + web) |
| `make migrate` | Apply Alembic migrations |
| `make api` | Run FastAPI (reload in dev) |
| `make web` | Run Vite dev server |
| `make test` | pytest + vitest |
| `make test-live` | Live OpenAI + Zammad integration (API, with logging) |
| `make test-live-ui` | Same tests in **visible browser** |
| `make e2e` | Playwright E2E (mock LLM + Wiremock Zammad) |
| `make e2e-ui` | Playwright interactive UI mode |
| `make lint` | ruff + eslint |
| `make create-ticket` | CLI create-ticket via orchestration + Zammad |

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health/live` | Liveness |
| GET | `/health/ready` | Readiness (Postgres + Redis) |
| GET | `/api/v1/config/public` | Public feature flags (e.g. thought streaming) |
| GET | `/api/v1/chat/sessions` | List recent sessions for user |
| POST | `/api/v1/chat/sessions` | Create session (`X-User-Id` or `Bearer` JWT) |
| GET | `/api/v1/chat/sessions/{id}` | Get session |
| GET | `/api/v1/chat/sessions/{id}/context` | Redis session context |
| GET | `/api/v1/chat/sessions/{id}/messages` | Paginated message history |
| POST | `/api/v1/chat/sessions/{id}/messages` | Send message (REST response) |
| POST | `/api/v1/chat/sessions/{id}/messages/stream` | Send message with SSE thought streaming |
| POST | `/api/v1/chat/sessions/{id}/graph/invoke` | Stateless graph turn (no persistence) |

Postman collection: [`docs/postman/Tech-Support-AI.postman_collection.json`](docs/postman/Tech-Support-AI.postman_collection.json)

**Session persistence:** the web UI stores `session_id` in `localStorage` and resumes on refresh.

**Thought streaming:** when enabled, the UI calls the `/messages/stream` endpoint. Processing steps (`Thinking…`, `Applying support rules…`, `Creating ticket…`, etc.) appear in a collapsible panel that auto-collapses when the turn completes.

## AI agent (`support_graph`)

LangGraph nodes:

| Node | Role |
| ---- | ---- |
| `conversation` | OpenAI structured output — NLU, clarifying questions, `StructuredIntent` |
| `orchestrate` | Policy validation + workflow command building (pure Python) |
| `ticket_tool` | Execute approved commands against the ticketing provider |
| `respond` | Format assistant reply and UI cards |

Supported intents today:

| Intent | LLM detection | End-to-end execution |
| ------ | ------------- | -------------------- |
| CreateTicket | Yes | Yes |
| CheckStatus | Yes | Yes (search tickets) |
| UpdateTicket, AddAttachment, EscalateIssue, CancelTicket | Yes (prompt) | Not yet |

Multi-turn intake hydrates conversation history from Redis (with Postgres fallback) on each turn so the LLM can synthesize facts across the full thread.

Use `GRAPH_LLM_MODE=mock` for offline tests, E2E, and local dev without an API key.

## Create ticket (CLI)

```bash
make migrate
export ZAMMAD_BASE_URL=https://your-zammad.example.com
export ZAMMAD_API_TOKEN=your-api-token
make create-ticket ARGS='--email john@company.com --title "VPN issue" --description "Cannot connect" --category network --priority high'
```

Dry-run (orchestration only):

```bash
.venv/bin/python scripts/create_ticket.py --dry-run --email john@company.com --title "VPN" --description "Test"
```

## Testing

### Unit / integration (default)

```bash
make test
```

Runs pytest (API, agents, orchestration, ticketing) and vitest (web).

### E2E (Playwright)

Fully automated browser tests. Uses **mock LLM** and **Wiremock** for Zammad — no OpenAI or sandbox credentials required.

```bash
make e2e
# Interactive debugger: make e2e-ui
```

Docker Compose starts Postgres, Redis, and Wiremock; Playwright starts the API (`:8010`) and Vite (`:5174`) on alternate ports.

### Live integration (OpenAI + Zammad)

Ten multi-turn scenarios using **real OpenAI**, **real Zammad**, and an **AI User Simulator** that role-plays an employee — no scripted follow-ups.

Strategy: [`docs/test-strategy-live-integration.md`](docs/test-strategy-live-integration.md)

```bash
docker compose up -d postgres redis
make migrate
make test-live          # API-only, headless
make test-live-ui       # visible Chromium
```

Required `.env`: `OPENAI_API_KEY`, `ZAMMAD_BASE_URL`, `ZAMMAD_API_TOKEN`, `ZAMMAD_TEST_EMAIL`, `GRAPH_ENABLED=true`, `GRAPH_LLM_MODE=openai`.

Transcripts: `tests/integration/artifacts/` (gitignored). Expect several minutes runtime and OpenAI API cost.

## Implementation status

| Sprint / milestone | Status |
| ------------------ | ------ |
| Foundation (monorepo, Docker, sessions, chat UI) | Complete |
| Redis context, auth stub, orchestration, Zammad client | Complete |
| LangGraph `support_graph`, CreateTicket E2E | Complete |
| OpenAI structured intent extraction | Complete |
| Multi-turn history hydration | Complete |
| Thought streaming (SSE) + collapsible UI panel | Complete |
| CheckStatus via ticket search | Complete |
| Ticketing provider abstraction (Zammad + ServiceNow stub) | Partial |
| Confirm-before-submit, all intents, attachments, OIDC | Planned |

Detailed architecture: [`docs/solution-architecture.md`](docs/solution-architecture.md)

## Documentation

| Document | Description |
| -------- | ----------- |
| [`docs/functional-document.md`](docs/functional-document.md) | Functional requirements |
| [`docs/technical-strategy.md`](docs/technical-strategy.md) | Stack and component boundaries |
| [`docs/solution-architecture.md`](docs/solution-architecture.md) | As-built architecture |
| [`docs/provider-abstraction-strategy.md`](docs/provider-abstraction-strategy.md) | Ticketing provider plug-in design |
| [`docs/test-strategy-live-integration.md`](docs/test-strategy-live-integration.md) | Live integration test harness |
