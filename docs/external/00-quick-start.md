# Quick Start

Get **Tech Support AI** running locally with **Docker Compose** — the only supported evaluation path. One command starts this project's stack: chat UI, **Admin KB**, API, Postgres, Redis, MinIO, Qdrant, and Keycloak. Then seed Agent Handbooks and open the apps.

**Time:** about 10–15 minutes (after Zammad is available).

## Prerequisites

Tech Support AI creates and looks up tickets in **Zammad**. A reachable Zammad instance is **required** — the product does not work end-to-end without it.

| Requirement | Detail |
| ----------- | ------ |
| **Zammad (required)** | Instance up and reachable from the API (sandbox or local). REST API enabled. Integration user + API token. Groups/priorities aligned with `config/providers/zammad/mapping.yaml`. Setup: [Zammad Integration Guide](05-integration-guide-zammad.md). |
| Docker Desktop or Docker Engine + Compose | Latest stable |
| OpenAI API key | Required when `GRAPH_LLM_MODE` is not `mock` (conversation LLM + embeddings) |
| Python 3.12+ and Node.js 20+ | For `make install` / `make seed-kb` on the host |
| Optional: [uv](https://docs.astral.sh/uv/) | Faster Python dependency sync |

Confirm Zammad before continuing, for example:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Token token=YOUR_ZAMMAD_API_TOKEN" \
  "https://your-zammad.example.com/api/v1/users/me"
```

Expect HTTP `200`. If Zammad runs on your machine and the API runs in Docker, use `http://host.docker.internal:8080` (or your Zammad port) as `ZAMMAD_BASE_URL`.

## 1. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```env
# Core agent
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai
OPENAI_API_KEY=sk-your-key-here

# Ticketing (required — Zammad must already be running)
TICKETING_PROVIDER=zammad
ZAMMAD_BASE_URL=https://your-zammad-sandbox.example.com
ZAMMAD_API_TOKEN=your-api-token

# L1 handbook troubleshoot (required)
KB_RAG_ENABLED=true
VECTOR_BACKEND=qdrant
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=openai
```

Compose overrides database, Redis, Qdrant, handbook storage, and Keycloak URLs inside the API container. Host-side `make seed-kb` uses the `localhost` ports from `.env.example` (Postgres `5433`, Qdrant `6333`, MinIO `9002`).

Align `config/providers/zammad/mapping.yaml` with your Zammad groups and priorities — see [Zammad Integration Guide](05-integration-guide-zammad.md).

## 2. Start the full stack

```bash
docker compose up -d --build
# equivalent: make up-all
```

Wait until services are healthy:

```bash
docker compose ps
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

The API container runs database migrations on startup (including KB tables).

## 3. Seed Agent Handbooks

From the repository root on the host:

```bash
make install
make seed-kb
```

This publishes sample Markdown from `config/knowledge/` into Postgres + Qdrant so chat L1 troubleshoot has content to retrieve.

## 4. Open the apps

| Service | URL |
| ------- | --- |
| Web chat | http://localhost:5173 |
| **Admin KB** | http://localhost:5174 |
| API docs (Swagger) | http://localhost:8000/docs |
| Documentation (MkDocs) | http://localhost:8088 |
| Keycloak | http://localhost:8081 |
| Qdrant | http://localhost:6333 |
| MinIO Console | http://localhost:9003 |

### Admin KB login (local Keycloak seed)

| User | Password | Roles |
| ---- | -------- | ----- |
| `kb-admin` | `admin` | `kb_editor`, `kb_admin` |
| `kb-editor` | `editor` | `kb_editor` |

## 5. Smoke test

**Admin KB** — sign in as `kb-admin` / `admin`. Confirm the seeded handbook is listed and **published**. You can upload, preview Markdown, reindex, and publish additional handbooks.

**Chat** — send:

> My VPN keeps disconnecting when working from home. It started yesterday and I cannot access internal tools.

**Expected:** one guided self-help step (empathetic copy; **no** handbook name). If you say it still fails, a **ticket card** with a Zammad ticket number. Ticket text may name the handbook for agents; chat UI never does.

## Service ports

| Service | Host port | Purpose |
| ------- | --------- | ------- |
| API | 8000 | FastAPI backend |
| Web | 5173 | React chat UI |
| Admin KB | 5174 | Handbook admin SPA |
| MkDocs | 8088 | External documentation site |
| PostgreSQL | 5433 | Sessions, messages, KB metadata |
| Redis | 6380 | Session hot state |
| MinIO API | 9002 | Attachments + handbook bucket |
| MinIO Console | 9003 | MinIO admin UI |
| Qdrant | 6333 | Handbook vectors |
| Keycloak | 8081 | Admin OIDC |

## What you have running

| Component | Role |
| --------- | ---- |
| Chat UI | End-user support conversation |
| Admin KB | Upload, publish, reindex, search-preview handbooks |
| Keycloak | Admin auth (`kb_editor` / `kb_admin`) |
| Qdrant | Vector retrieval for L1 troubleshoot |
| `KB_RAG_ENABLED=true` | Enables the graph `troubleshoot` node |

Details: [Functional Specification](02-functional-specification-summary.md), [API Overview](07-api-overview.md), [Deployment & Operations](06-deployment-and-operations.md).

## Verification checklist

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | `GET /health/live` | HTTP 200 |
| 2 | `GET /health/ready` | HTTP 200 |
| 3 | Open Admin KB, sign in | Handbook list loads; seeded doc is published |
| 4 | Open web chat | Welcome message, composer enabled |
| 5 | Send a VPN-style message | One guided self-help step (no handbook name) |
| 6 | Fail step / escalate | Ticket card with Zammad number |

## Authentication

**Chat** (local Compose):

```http
X-User-Id: dev-user@company.com
```

**Admin KB:** Keycloak Bearer JWT only. Chat-style `X-User-Id` is rejected on `/api/v1/admin/kb/*`. See [Security & Data Handling](04-security-and-data-handling.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| Containers unhealthy | Still starting | `docker compose ps`; wait; check `docker compose logs api` |
| API OpenAI error | Missing key with `GRAPH_LLM_MODE=openai` | Set `OPENAI_API_KEY` or set `GRAPH_LLM_MODE=mock` and recreate API |
| No guided self-help step | Flag off or no published handbook | `KB_RAG_ENABLED=true` in `.env`, recreate API, `make seed-kb` |
| Admin SPA won't log in | Keycloak not ready | Wait for Keycloak healthy; use `kb-admin` / `admin` |
| Admin upload fails | MinIO / handbook bucket | Confirm MinIO up; Compose sets handbook storage to MinIO automatically |
| `make seed-kb` fails | Host deps or embeddings | `make install`; set `OPENAI_API_KEY` or `EMBEDDING_PROVIDER=hash` |
| Ticket not created | Zammad down, wrong URL/token, or mapping mismatch | Confirm Zammad is up; verify `ZAMMAD_*`; check [Zammad Integration Guide](05-integration-guide-zammad.md) |
| Zammad unreachable from API | `localhost` inside the API container | Set `ZAMMAD_BASE_URL=http://host.docker.internal:<port>` and recreate the API |
| Port already in use | Conflicting local services | Stop the conflicting process or change ports in `docker-compose.yml` |

Stop the stack:

```bash
docker compose down
# or: make down
```

## Next steps

| Topic | Document |
| ----- | -------- |
| Architecture and components | [Solution Architecture](03-solution-architecture.md) |
| Zammad sandbox and field mapping | [Zammad Integration Guide](05-integration-guide-zammad.md) |
| Production deployment | [Deployment & Operations](06-deployment-and-operations.md) |
| API reference (chat + Admin KB) | [API Overview](07-api-overview.md) |
| Full capability list | [Capability Matrix](appendices/C-capability-matrix.md) |
