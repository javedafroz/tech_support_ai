# Tech Support AI

Enterprise AI chat assistant for IT support. A **LangGraph** agent extracts intent from natural-language issues, offers classic-RAG self-help grounded in an Agent Handbook (**Qdrant** + citation-validated LLM), and creates validated tickets through a **deterministic policy/orchestration layer** on **Zammad** (or other providers via a pluggable adapter). Includes a React chat UI, admin SPA, and FastAPI backend.

See [`docs/`](docs/) for internal engineering documents and [`docs/external/`](docs/external/) for customer- and partner-facing documentation.

## Features

| Capability | Status |
| ---------- | ------ |
| Web chat UI with session resume | Implemented |
| Multi-turn conversational intake (OpenAI or mock LLM) | Implemented |
| CreateTicket end-to-end (LLM → orchestration → Zammad) | Implemented |
| CheckStatus (search tickets by number / customer) | Implemented |
| **L1 handbook troubleshoot (KB/RAG)** | **Implemented** — feature-flagged (`KB_RAG_ENABLED`) |
| **Admin KB** (upload / publish handbooks, Keycloak) | **Implemented** — `apps/admin` + `/api/v1/admin/kb/*` |
| Thought streaming (live processing steps over SSE) | Implemented — toggle via `.env` |
| Collapsible processing panel in UI | Implemented |
| Provider abstraction (`zammad` live, `servicenow` stub) | Partial |
| UpdateTicket, confirm-before-submit | Planned |
| **Attachments** (upload, create ticket, add to active ticket) | **Implemented (v1)** |

### How it works

```text
User (web chat)
    → FastAPI
    → LangGraph support_graph
         conversation (LLM — intent + slot filling)
         troubleshoot (optional — classic RAG: retrieve handbook chunks + grounded LLM guidance)
         orchestrate (Python — policy + workflow, no LLM)
         ticket_tool (Zammad REST API)
         respond
    → Assistant reply + ticket card (or deflection if self-help resolved)
```

**Design principle:** the LLM handles language and grounded troubleshooting presentation. Handbook retrieval, citation validation, policy, category→group mapping, and ticket execution are deterministic and auditable.

## Prerequisites

| Requirement | Detail |
| ----------- | ------ |
| **Zammad (required)** | Instance up and reachable with REST API + token. See [Zammad Integration Guide](docs/external/05-integration-guide-zammad.md). |
| Docker Desktop (or Docker Engine) with Compose | Latest stable |
| OpenAI API key | When not using `GRAPH_LLM_MODE=mock` |
| [uv](https://docs.astral.sh/uv/) or Python 3.12+ | Host tooling for `make install` / `make seed-kb` |
| Node.js 20+ | Host tooling for `make install` |

## Quick start (< 15 minutes)

**One path:** full stack via Docker Compose. Details and smoke tests: [docs/external/00-quick-start.md](docs/external/00-quick-start.md).

```bash
cp .env.example .env
# Required: Zammad must already be running — set ZAMMAD_BASE_URL + ZAMMAD_API_TOKEN
# Required: KB_RAG_ENABLED=true
# Required for live LLM: OPENAI_API_KEY (or GRAPH_LLM_MODE=mock)

docker compose up -d --build
make install
make seed-kb
```

| App | URL |
| --- | --- |
| Web chat | http://localhost:5173 |
| Admin KB | http://localhost:5174 (`kb-admin` / `admin`) |
| API docs | http://localhost:8000/docs |
| Docs site | http://localhost:8088 |

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Chat uses `X-User-Id: dev-user@company.com`. Admin KB uses Keycloak (not `X-User-Id`).

## Configuration

Key variables in `.env` (see [`.env.example`](.env.example) for the full list):

```env
# LangGraph agent
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai          # mock = offline; any other value enables LLM
LLM_PROVIDER=openai            # openai | azure_openai | anthropic (default: openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Azure OpenAI (when LLM_PROVIDER=azure_openai)
# AZURE_OPENAI_API_KEY=...
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Anthropic (when LLM_PROVIDER=anthropic)
# ANTHROPIC_API_KEY=...
# ANTHROPIC_MODEL=claude-3-5-haiku-latest

# Thought streaming — live "Processing" steps in the chat UI (SSE)
THOUGHT_STREAMING_ENABLED=true

# L1 KB / RAG (optional guided self-help before CreateTicket)
KB_RAG_ENABLED=false
VECTOR_BACKEND=qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=openai      # hash = offline/tests
KB_HANDBOOK_STORAGE_BACKEND=memory

# Admin Keycloak (handbook SPA + /api/v1/admin/kb/*)
KEYCLOAK_URL=http://localhost:8081
KEYCLOAK_REALM=tech-support

# Ticketing provider
TICKETING_PROVIDER=zammad      # zammad | servicenow (stub)
ZAMMAD_BASE_URL=https://your-zammad.example.com
ZAMMAD_API_TOKEN=...
```

| Variable | Purpose |
| -------- | ------- |
| `GRAPH_LLM_MODE=mock` | Offline dev/tests — no LLM API key required |
| `LLM_PROVIDER` | `openai` (default), `azure_openai`, or `anthropic` |
| `THOUGHT_STREAMING_ENABLED` | Enables `POST .../messages/stream` (SSE); UI reads this from `/api/v1/config/public` |
| `VITE_THOUGHT_STREAMING_ENABLED=false` | Optional UI-only override to force-disable streaming |
| `GRAPH_CHECKPOINT=true` | Optional Postgres checkpointer for LangGraph state |
| `KB_RAG_ENABLED` | Enable troubleshoot node (classic RAG guidance before ticket) |
| `KB_RAG_MAX_CONTEXT_CHARS` | Cap on retrieved handbook text passed into the RAG prompt |
| `KB_MIN_SCORE` | Retrieval similarity threshold (default `0.35`) |
| `QDRANT_URL` / `EMBEDDING_*` | Vector store and embeddings for handbook retrieval |
| `KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET` | Append chat transcript when escalating to CreateTicket |
| `KB_MAX_TROUBLESHOOT_STEPS` | Config ceiling; runtime still guides **one** step then escalate |

**Local Zammad on host:** use `http://localhost:8080` when running `make api` on the host. Docker Compose rewrites `localhost` → `host.docker.internal` automatically.

Category and group mapping: [`config/providers/zammad/mapping.yaml`](config/providers/zammad/mapping.yaml)

## Repository layout

```text
apps/
  api/              FastAPI BFF, Alembic migrations, chat + graph + admin KB endpoints
  web/              React + Vite chat UI
  admin/            React + Vite handbook admin SPA (Keycloak)
packages/
  agents/           LangGraph support_graph + LLMGateway + troubleshoot node
  knowledge/        Ingest, chunking, embeddings, Qdrant/memory store, Docling
  orchestration/    PolicyValidator, WorkflowEngine, OrchestrationEngine
  ticketing/        Provider gateway (Zammad adapter, ServiceNow stub)
  zammad-client/    Zammad HTTP client
  shared/           JSON schemas, reason codes
config/
  providers/zammad/mapping.yaml
  providers/servicenow/mapping.yaml
  knowledge/        Sample Agent Handbooks (Markdown)
  keycloak/         Local realm import for admin roles
docs/               Architecture, FSD, external pack, KB strategy
tests/integration/  Live OpenAI + Zammad + AI User Simulator
e2e/                Playwright browser tests (mock LLM + Wiremock)
scripts/            create_ticket CLI, seed_kb, Zammad sandbox E2E
```

## Development commands

| Command | Description |
| ------- | ----------- |
| `make up` | Start Postgres, Redis, MinIO, Qdrant, Keycloak |
| `make up-kb` | Start Postgres, Redis, Qdrant, Keycloak (no MinIO) |
| `make up-all` | Full Compose stack (api, web, admin, docs, infra) |
| `make migrate` | Apply Alembic migrations (includes KB tables) |
| `make seed-kb` | Ingest + publish sample handbooks from `config/knowledge/` |
| `make api` | Run FastAPI (reload in dev) |
| `make web` | Run Vite chat UI |
| `make admin` | Run Admin SPA (handbooks) at http://localhost:5174 |
| `make test` | pytest + vitest |
| `make test-live` | Live OpenAI + Zammad integration (API, with logging) |
| `make test-live-ui` | Same tests in **visible browser** |
| `make e2e` | Playwright E2E (mock LLM + Wiremock Zammad) |
| `make e2e-ui` | Playwright interactive UI mode |
| `make lint` | ruff + eslint |
| `make docs` | MkDocs dev server at http://127.0.0.1:8088 (or `docker compose up -d docs`) |
| `make docs-build` | Build static docs to `site/` |
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
| * | `/api/v1/admin/kb/*` | Handbook admin API (Keycloak Bearer; `kb_editor` / `kb_admin`) |

Admin KB routes: list/upload/publish/reindex/search preview — see [`docs/external/07-api-overview.md`](docs/external/07-api-overview.md).

Postman collection: [`docs/postman/Tech-Support-AI.postman_collection.json`](docs/postman/Tech-Support-AI.postman_collection.json)

**Session persistence:** the web UI stores `session_id` in `localStorage` and resumes on refresh.

**Thought streaming:** when enabled, the UI calls the `/messages/stream` endpoint. Processing steps (`Thinking…`, `Applying support rules…`, `Creating ticket…`, etc.) appear in a collapsible panel that auto-collapses when the turn completes.

## AI agent (`support_graph`)

LangGraph nodes:

| Node | Role |
| ---- | ---- |
| `conversation` | OpenAI structured output — NLU, clarifying questions, `StructuredIntent` |
| `troubleshoot` | KB/RAG — retrieve published handbook, guide **one** step, deflect or escalate to CreateTicket (`KB_RAG_ENABLED`) |
| `orchestrate` | Policy validation + workflow command building (pure Python) |
| `ticket_tool` | Execute approved commands against the ticketing provider |
| `respond` | Format assistant reply and UI cards |

Supported intents today:

| Intent | LLM detection | End-to-end execution |
| ------ | ------------- | -------------------- |
| CreateTicket | Yes | Yes |
| CheckStatus | Yes | Yes (search tickets) |
| UpdateTicket, EscalateIssue, CancelTicket | Yes (prompt) | Not yet |
| **AddAttachment** | Yes (file upload + active ticket) | **Yes** |

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

Docker Compose starts Postgres, Redis, and Wiremock; Playwright starts the API (`:8010`) and chat Vite (`:5175` by default, via `E2E_WEB_PORT`) so it does not clash with Admin (`:5174`).

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

Demo completion target is **Sprint 10** — all six FSD intents in sandbox.

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
| Confirm-before-submit, remaining intents | Planned (Sprints 7–10) |
| Attachments (MinIO/S3 → Zammad) | **v1 shipped** — see below |
| L1 handbook troubleshoot + Admin KB (Qdrant, Keycloak) | **Shipped** — see below |

### L1 handbook troubleshoot (KB/RAG)

When `KB_RAG_ENABLED=true` and a **published** handbook matches the user’s support issue:

1. Graph runs `troubleshoot` before CreateTicket slot-filling
2. Assistant retrieves handbook chunks and synthesizes adaptive grounded steps (empathetic copy; no handbook name)
3. User resolves → deflection (no ticket); fails / escalates → CreateTicket immediately with optional transcript enrichment

Handbooks are ingested via Docling (PDF→Markdown), chunked/embedded into Qdrant, and stored via S3-compatible object storage (`CEPH_RGW_*` — Ceph RGW in production; Compose may use MinIO with a dedicated `agent-handbooks` bucket; `memory` for host-run seed). Manage via Admin SPA (`make admin`) or `make seed-kb`.

On escalate, the **ticket description** may include “Handbook consulted” plus steps and transcript for agents — chat UI copy still never shows handbook names.

Deep dive: [`docs/kb-rag-l1-agent-strategy.md`](docs/kb-rag-l1-agent-strategy.md)

### Attachments (v1)

1. Click **📎** in the composer, select file(s) — uploaded to MinIO/S3 via `POST /api/v1/chat/sessions/{id}/attachments`
2. Send your message — files are linked to the user message
3. **New ticket:** attachments are included on the initial Zammad article when the ticket is created
4. **Active ticket:** files are attached via `AddAttachment` (no LLM required)
5. **Images (screenshots):** OpenAI vision reads error codes and on-screen text from attached images during the conversation — you do not need to re-type what is visible in the screenshot

Limits: 10 MB per file, 5 files per message. Blocked types: executables/scripts.

Requires MinIO (`make up`) and `S3_*` env vars (see `.env.example`).

Detailed architecture: [`docs/solution-architecture.md`](docs/solution-architecture.md)

## Documentation

### External (customer / partner)

Share [`docs/external/`](docs/external/) with evaluators, architects, and integrators — or browse via **MkDocs**:

```bash
make docs          # serve at http://127.0.0.1:8088
make docs-build    # static site in site/
```

Start with the [Quick Start](docs/external/00-quick-start.md) or [Executive Overview](docs/external/01-executive-solution-overview.md).

| Document | Description |
| -------- | ----------- |
| [`docs/external/README.md`](docs/external/README.md) | Index of all external documents (v1.3) |
| [`docs/external/00-quick-start.md`](docs/external/00-quick-start.md) | Get running in under 15 minutes |
| [`docs/external/01-executive-solution-overview.md`](docs/external/01-executive-solution-overview.md) | Business value and capability summary |
| [`docs/external/07-api-overview.md`](docs/external/07-api-overview.md) | REST API reference (chat + admin KB) |
| [`docs/external/05-integration-guide-zammad.md`](docs/external/05-integration-guide-zammad.md) | Zammad sandbox setup |
| [`docs/external/appendices/C-capability-matrix.md`](docs/external/appendices/C-capability-matrix.md) | Capability status matrix |

### Internal engineering

| Document | Description |
| -------- | ----------- |
| [`docs/functional-document.md`](docs/functional-document.md) | Functional requirements |
| [`docs/technical-strategy.md`](docs/technical-strategy.md) | Stack and component boundaries |
| [`docs/solution-architecture.md`](docs/solution-architecture.md) | As-built architecture |
| [`docs/kb-rag-l1-agent-strategy.md`](docs/kb-rag-l1-agent-strategy.md) | KB/RAG L1 agent design (deep dive) |
| [`docs/provider-abstraction-strategy.md`](docs/provider-abstraction-strategy.md) | Ticketing provider plug-in design |
| [`docs/test-strategy-live-integration.md`](docs/test-strategy-live-integration.md) | Live integration test harness |

## License

Copyright 2026 Tech Support AI contributors.

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for
attribution information.
