# Tech Support AI

> Resolve IT issues before they become tickets.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776ab.svg)](https://www.python.org/)
[![Node 20+](https://img.shields.io/badge/node-20+-339933.svg)](https://nodejs.org/)
[![Docker Compose](https://img.shields.io/badge/run-docker%20compose-2496ed.svg)](https://docs.docker.com/compose/)

**Tech Support AI** is an enterprise web chat assistant for IT support. Employees
describe a problem in plain language; a [LangGraph](https://langchain-ai.github.io/langgraph/)
agent understands the intent, offers grounded self-help from your own handbooks
(classic RAG over [Qdrant](https://qdrant.tech/) with citation-validated LLM
guidance), and — only if that doesn't resolve it — opens a well-formed ticket in
[Zammad](https://zammad.com/) (or another help desk via a pluggable adapter).

The guiding principle: **the LLM handles language; deterministic Python handles
consequences.** Retrieval, policy, category→group routing, and ticket execution
are auditable code — so a hallucination or prompt injection can never create,
route, or escalate a ticket on its own.

## Table of contents

- [Features](#features)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features

- **Conversational intake** — multi-turn natural-language triage that synthesizes
  a ticket across the whole thread instead of forcing a form.
- **L1 self-help (classic RAG)** — retrieves your published handbooks, presents a
  grounded, empathetic troubleshooting step, and deflects the issue when the user
  resolves it — no ticket created.
- **Deterministic ticketing** — every ticket action passes a Python policy and
  workflow layer before it reaches the help desk. Create and check-status flows
  run end-to-end against Zammad today.
- **Enriched escalations** — when self-help fails, the ticket arrives pre-triaged
  with the steps attempted and the full transcript, so agents start ahead.
- **Attachments & vision** — upload screenshots and logs; the model reads error
  codes and on-screen text from images during the conversation.
- **Admin knowledge base** — a dedicated SPA (Keycloak-secured) to upload, convert
  (PDF→Markdown via [Docling](https://github.com/docling-project/docling)),
  publish, and search handbooks.
- **Live processing view** — optional SSE "thought streaming" surfaces the agent's
  steps in a collapsible panel in the chat UI.
- **Pluggable providers** — swap the LLM (OpenAI / Azure OpenAI / Anthropic) and
  the ticketing backend (Zammad live; ServiceNow adapter stubbed) via config.
- **Runs offline** — a mock LLM and in-memory backends let the full stack and test
  suite run with no external API keys.

## Quick start

The whole stack runs with Docker Compose. Full walkthrough and smoke tests:
[docs/external/00-quick-start.md](docs/external/00-quick-start.md).

### Prerequisites

| Requirement | Notes |
| ----------- | ----- |
| **Zammad (required)** | A reachable Zammad instance with a REST API token — the product does not complete ticket flows without it. See the [Zammad integration guide](docs/external/05-integration-guide-zammad.md). |
| Docker Desktop / Engine with Compose | Latest stable |
| OpenAI API key | Needed unless you run with `GRAPH_LLM_MODE=mock` |
| [uv](https://docs.astral.sh/uv/) or Python 3.12+ | Host tooling for `make install` / `make seed-kb` |
| Node.js 20+ | Host tooling for `make install` |

### Run it

```bash
cp .env.example .env
# Set these in .env before starting:
#   ZAMMAD_BASE_URL, ZAMMAD_API_TOKEN   (required)
#   KB_RAG_ENABLED=true                 (enables L1 self-help; ships as false)
#   OPENAI_API_KEY                      (or GRAPH_LLM_MODE=mock for offline)

docker compose up -d --build
make install
make seed-kb          # ingest + publish the sample handbooks
```

| App | URL | Notes |
| --- | --- | ----- |
| Web chat | http://localhost:5173 | Uses `X-User-Id` (e.g. `you@example.com`) |
| Admin KB | http://localhost:5174 | Keycloak login `kb-admin` / `admin` |
| API docs | http://localhost:8000/docs | OpenAPI / Swagger UI |
| Docs site | http://localhost:8088 | MkDocs |

Verify the API is healthy:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Then open the chat and try: *"My VPN keeps disconnecting after about 30 seconds."*
With a matching handbook published, the agent guides a fix first and only opens a
ticket if you say it didn't work.

## How it works

```text
User (web chat)
    → FastAPI
    → LangGraph support graph
         conversation   LLM — intent detection + slot filling
         troubleshoot   classic RAG — retrieve handbook chunks + grounded guidance
         orchestrate    Python — policy + workflow (no LLM)
         ticket_tool    Zammad REST API
         respond        assistant reply + ticket card
    → Reply, or a deflection when self-help resolved the issue
```

The LLM produces language and grounded troubleshooting; handbook retrieval,
citation validation, policy checks, category→group mapping, and ticket execution
are deterministic and auditable.

| Node | Role |
| ---- | ---- |
| `conversation` | Structured-output NLU — clarifying questions and a typed intent |
| `troubleshoot` | Retrieve the published handbook, guide one grounded step, then deflect or escalate (enabled by `KB_RAG_ENABLED`) |
| `orchestrate` | Policy validation + workflow command building (pure Python) |
| `ticket_tool` | Execute approved commands against the ticketing provider |
| `respond` | Format the assistant reply and UI cards |

## Configuration

Copy [`.env.example`](.env.example) to `.env` — it documents every setting. The
most common ones:

```env
GRAPH_LLM_MODE=openai          # "mock" runs offline with no API key
LLM_PROVIDER=openai            # openai | azure_openai | anthropic
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

KB_RAG_ENABLED=true            # enable L1 handbook self-help (ships as false)
VECTOR_BACKEND=qdrant          # "memory" for offline/tests
EMBEDDING_PROVIDER=openai      # "hash" for offline/tests

TICKETING_PROVIDER=zammad      # zammad | servicenow (stub)
ZAMMAD_BASE_URL=https://your-zammad.example.com
ZAMMAD_API_TOKEN=...
```

Notable flags: `GRAPH_LLM_MODE=mock` (no API key needed),
`THOUGHT_STREAMING_ENABLED` (live processing view), and the `KB_*` retrieval
tuning knobs. Category and group routing lives in
[`config/providers/zammad/mapping.yaml`](config/providers/zammad/mapping.yaml).

> **Running the API on the host** (via `make api`): point `ZAMMAD_BASE_URL` at
> `http://localhost:8080`. Docker Compose rewrites `localhost` →
> `host.docker.internal` automatically.

## Architecture

```text
apps/
  api/              FastAPI backend — Alembic migrations, chat + graph + admin KB endpoints
  web/              React + Vite chat UI
  admin/            React + Vite handbook admin SPA (Keycloak)
packages/
  agents/           LangGraph support graph, LLM gateway, troubleshoot node
  knowledge/        Ingest, chunking, embeddings, Qdrant/memory store, Docling
  orchestration/    Policy validator, workflow engine, orchestration engine
  ticketing/        Provider gateway (Zammad adapter, ServiceNow stub)
  zammad-client/    Zammad HTTP client
  storage/          S3-compatible object storage (attachments, handbooks)
  shared/           JSON schemas, reason codes
config/             Provider mappings, sample handbooks, Keycloak realm
docs/               Architecture, functional spec, guides, KB/RAG strategy
tests/integration/  Live OpenAI + Zammad tests with an AI user simulator
e2e/                Playwright browser tests (mock LLM + Wiremock Zammad)
scripts/            create-ticket CLI, KB seeder, Zammad sandbox runner
```

Common tasks are wrapped in the `Makefile`:

| Command | Description |
| ------- | ----------- |
| `make up` | Start infra (Postgres, Redis, MinIO, Qdrant, Keycloak) |
| `make install` | Install Python (uv) + web/admin npm dependencies |
| `make migrate` | Apply database migrations |
| `make seed-kb` | Ingest and publish the sample handbooks |
| `make api` / `make web` / `make admin` | Run each service in dev mode |
| `make test` | Run the unit/integration suite (pytest + vitest) |
| `make e2e` | Playwright browser tests (mock LLM + Wiremock) |
| `make lint` | ruff + eslint |
| `make docs` | Serve the docs site locally |

The REST API is documented interactively at `/docs` when the API is running; a
[Postman collection](docs/postman/Tech-Support-AI.postman_collection.json) and an
[API reference](docs/external/07-api-overview.md) are also included.

## Documentation

| Document | Description |
| -------- | ----------- |
| [Quick start](docs/external/00-quick-start.md) | Get running in under 15 minutes |
| [Solution overview](docs/external/01-executive-solution-overview.md) | Capabilities and value at a glance |
| [Solution architecture](docs/solution-architecture.md) | As-built architecture with diagrams |
| [API reference](docs/external/07-api-overview.md) | REST API (chat + admin KB) |
| [Zammad integration guide](docs/external/05-integration-guide-zammad.md) | Connecting a Zammad instance |
| [KB/RAG L1 agent strategy](docs/kb-rag-l1-agent-strategy.md) | Deep dive on the self-help design |
| [Provider abstraction](docs/provider-abstraction-strategy.md) | Pluggable ticketing design |
| [Live integration test strategy](docs/test-strategy-live-integration.md) | The AI-user-simulator harness |

Browse the full set with MkDocs:

```bash
make docs          # serve at http://127.0.0.1:8088
```

## Testing

```bash
make test          # pytest (API, agents, orchestration, ticketing) + vitest (web)
make e2e           # Playwright browser tests — mock LLM + Wiremock, no keys needed
```

Live integration tests exercise the real graph against real OpenAI and Zammad
using an AI "user simulator" that role-plays an employee across multi-turn
scenarios:

```bash
docker compose up -d postgres redis
make migrate
make test-live     # headless; make test-live-ui for a visible browser
```

Live runs require `OPENAI_API_KEY`, `ZAMMAD_BASE_URL`, `ZAMMAD_API_TOKEN`, and
`ZAMMAD_TEST_EMAIL`, take several minutes, and incur OpenAI API cost. See the
[live test strategy](docs/test-strategy-live-integration.md).

## Roadmap

- Confirm-before-submit (human-in-the-loop approval before ticket creation)
- Remaining ticket intents end-to-end: update, escalate, cancel
- A production-ready ServiceNow adapter alongside Zammad

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the
development workflow, coding standards, and how to run the checks, and note our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Please do not open public issues for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for how to report them responsibly.

## License

Copyright 2026 Tech Support AI contributors.

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for
attribution details.

## Acknowledgements

Built with [LangGraph](https://langchain-ai.github.io/langgraph/),
[FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/),
[Qdrant](https://qdrant.tech/), [Docling](https://github.com/docling-project/docling),
[Keycloak](https://www.keycloak.org/), and [Zammad](https://zammad.com/).
