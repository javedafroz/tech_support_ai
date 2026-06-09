# Solution Architecture – Tech Support AI

## Document Control

| Item | Detail |
| ---- | ------ |
| **Version** | 1.0 |
| **Date** | 2026-05-29 |
| **Status** | As-built through Sprint 5; target state through Sprint 14 |
| **Audience** | Engineering, architecture, DevOps, security, product |
| **Related documents** | [Functional Document](functional-document.md), [Technical Strategy](technical-strategy.md), [Implementation Strategy](implementation-strategy.md), [UI/UX Strategy](ui-ux-strategy.md), [Live Integration Test Strategy](test-strategy-live-integration.md) |
| **Purpose** | Describe the end-to-end solution architecture, what is implemented today, and what remains to reach production MVP |

---

## 1. Executive Summary

**Tech Support AI** is an enterprise web chat assistant that integrates with **Zammad** for IT support ticket management. Employees describe issues in natural language; a **LangGraph** agent extracts structured intent, a **deterministic orchestration layer** validates business rules, and approved actions execute against the Zammad REST API.

The solution is delivered as a **Python + React monorepo** with:

- **FastAPI** backend (BFF / API gateway)
- **LangGraph** agent runtime (`support_graph`)
- **PostgreSQL** for durable sessions, messages, and audit tables
- **Redis** for session hot state
- **MinIO** (local) / S3 (production target) for attachments
- **React + Vite** web chat UI

### Current maturity

| Milestone | Target (Implementation Strategy) | Actual status |
| --------- | -------------------------------- | ------------- |
| **M1** — Foundation skeleton | End Week 4 | **Complete** |
| **M2** — Create ticket E2E | End Week 8 | **Partially complete** — CreateTicket works end-to-end with real OpenAI + Zammad; SSE streaming and confirm interrupt not yet built |
| **M3** — All intents + resilience | End Week 11 | **Not started** |
| **M4** — Production pilot | End Week 14 | **Not started** |

The project is approximately at **Sprint 5 complete** (LangGraph core + CreateTicket path). Sprints 6–14 remain.

---

## 2. Business Context

### 2.1 Objectives

| Objective | How the solution addresses it |
| --------- | ------------------------------ |
| Reduce manual support intake effort | AI gathers issue details conversationally before ticket creation |
| Improve ticket quality and categorization | Structured intent + workflow engine maps category/priority/group deterministically |
| Provide 24/7 support interaction | Web chat available anytime; LLM handles intake |
| Automate repetitive operations | Ticket creation, status lookup, updates (planned) via Zammad API |
| Maintain enterprise control | Orchestration gates every Zammad call; audit tables record decisions |

### 2.2 Scope

**In scope (v1 target)**

- Web chat as the sole user channel
- Conversational AI for intake and ticket operations
- Deterministic orchestration between AI and Zammad
- Zammad REST API integration for ticket lifecycle

**Out of scope (v1)**

- Microsoft Teams, Slack, mobile, WhatsApp channels
- Voice assistant
- Knowledge base / RAG layer
- In-chat human handoff
- Policy admin UI (API/config-only acceptable for v1)

---

## 3. Solution Overview

### 3.1 Logical Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     React Web Chat (apps/web)                        │
│  REST (implemented) · SSE (planned) · Auth (dev header / JWT stub)   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS
┌──────────────────────────────▼──────────────────────────────────────┐
│              FastAPI BFF (apps/api)                                  │
│  /health/* · /api/v1/chat/sessions · /api/v1/chat/.../messages       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  LangGraph      │  │  Orchestration   │  │  Zammad Client  │
│  support_graph  │─►│  (deterministic) │─►│  (HTTP/httpx)   │
│  (packages/     │  │  packages/       │  │  packages/      │
│   agents)       │  │  orchestration   │  │  zammad-client  │
└────────┬────────┘  └────────┬─────────┘  └────────┬────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  Redis 7        │  │  PostgreSQL 16   │  │  Zammad         │
│  session context│  │  sessions, audit │  │  (external SaaS)│
│  recent turns   │  │  messages        │  │                 │
└─────────────────┘  └──────────────────┘  └─────────────────┘
```

### 3.2 Design Principles

1. **LLM for language only** — The conversation node handles NLU, clarifying questions, and structured intent proposals. Business rules are never embedded in prompts.
2. **Orchestration gates Zammad** — Every ticket operation passes through `PolicyValidator` + `WorkflowEngine` before any HTTP call.
3. **Zammad-grounded ticket IDs** — Ticket numbers shown to users come only from Zammad API responses, never from LLM output.
4. **Separation of durable vs hot state** — PostgreSQL is the source of truth; Redis holds fast session context and a rolling turn window.
5. **Testability** — Mock LLM mode, Wiremock Zammad, and live integration tests with an AI User Simulator.

### 3.3 FSD Layer Mapping

| Functional layer (FSD §3) | Implementation package / component |
| ------------------------- | ---------------------------------- |
| Conversation Agent | `packages/agents` — `conversation` node + OpenAI/Mock LLM |
| Orchestration Layer | `packages/orchestration` — `PolicyValidator`, `WorkflowEngine`, `OrchestrationEngine` |
| Ticket Management Agent | `packages/agents` — `zammad_tool` node + `packages/zammad-client` |
| Integration Layer | `packages/zammad-client` — retries, auth, error mapping |
| Web Chat UI | `apps/web` — ChatShell, MessageStream, Composer |

---

## 4. Component Architecture

### 4.1 Web Frontend (`apps/web`)

**Stack:** React 18, TypeScript, Vite, CSS Modules, Vitest

**Implemented components**

| Component | Path | Status |
| --------- | ---- | ------ |
| `ChatShell` | `components/ChatShell/` | Implemented — main layout, header, new chat |
| `MessageStream` | `components/MessageStream/` | Implemented — user/assistant/system messages |
| `MessageCard` | `components/MessageStream/MessageCard.tsx` | Implemented — renders `ticket_created`, `ticket_status`, `ticket_summary` card types |
| `Composer` | `components/Composer/` | Implemented — text input, send |
| `ContextStrip` | `components/ContextStrip/` | Implemented — active ticket, session context, detected intent |
| `SystemStatusLine` | `components/SystemStatusLine/` | Implemented — client-side status cycling during send (not SSE-driven) |

**Implemented hooks / client**

| Module | Status |
| ------ | ------ |
| `useChatSession` | Implemented — session bootstrap, resume from `localStorage`, send message, reload history |
| `api/chatClient.ts` | Implemented — REST calls to session/message endpoints |
| `lib/sessionStorage.ts` | Implemented — persists `session_id` in browser |
| `types/api.ts`, `types/events.ts` | Implemented — aligned with backend schemas |

**Not yet implemented**

| Item | Planned sprint | Notes |
| ---- | -------------- | ----- |
| `useSSEStream` hook | Sprint 6 | Real-time token and status streaming |
| Summary confirm card + edit flow | Sprint 7 | Requires graph interrupt + `POST /confirm` |
| Disambiguation card (≤5 tickets) | Sprint 9 | UI types exist; no backend events yet |
| Attachment upload in Composer | Sprint 8 | Drag-drop, file input |
| Degraded mode banners | Sprint 11 | LLM/Zammad outage messaging |
| Embeddable widget package | Phase 2 | `@org/support-chat-widget` |
| Storybook for cards | Sprint 8 | Component catalog |
| CSAT prompt | Sprint 13 | Post-resolution feedback |

### 4.2 API / BFF (`apps/api`)

**Stack:** Python 3.12+, FastAPI, SQLAlchemy (async), Alembic, Pydantic Settings

**Implemented routers**

| Method | Path | Status |
| ------ | ---- | ------ |
| GET | `/health/live` | Implemented |
| GET | `/health/ready` | Implemented — checks Postgres + Redis (not Zammad) |
| GET | `/api/v1/chat/sessions` | Implemented — list recent sessions for user |
| POST | `/api/v1/chat/sessions` | Implemented — create session with welcome message |
| GET | `/api/v1/chat/sessions/{id}` | Implemented |
| GET | `/api/v1/chat/sessions/{id}/context` | Implemented — Redis session context |
| GET | `/api/v1/chat/sessions/{id}/messages` | Implemented — paginated history |
| POST | `/api/v1/chat/sessions/{id}/messages` | Implemented — send message, invoke graph, persist |
| POST | `/api/v1/chat/sessions/{id}/graph/invoke` | Implemented — stateless graph turn (no persistence) |

**Implemented services**

| Service | Status | Notes |
| ------- | ------ | ----- |
| `ChatService` | Implemented | Session lifecycle, message send, graph invocation |
| `GraphService` | Implemented | Singleton graph runner, optional Postgres checkpointer |
| `RedisSessionStore` | Implemented | Context + rolling recent turns (max 20) |
| `MockGraph` | Implemented | Fallback when `GRAPH_ENABLED=false` |
| `AuditService` | Partial | Implemented but **only wired in CLI** (`scripts/create_ticket.py`), not in chat message flow |
| `TicketPipeline` | Implemented | Used by CLI for orchestration + Zammad without LangGraph |

**Not yet implemented**

| Endpoint / service | Planned sprint |
| ------------------ | -------------- |
| `GET /api/v1/chat/sessions/{id}/stream` (SSE) | Sprint 6 |
| `POST /api/v1/chat/sessions/{id}/confirm` | Sprint 7 |
| `POST /api/v1/chat/sessions/{id}/attachments` | Sprint 8 |
| `StreamService` (Redis pub/sub → SSE) | Sprint 6 |
| `OutboxWorker` | Sprint 11 |
| Rate limiting middleware | Sprint 12 |
| OIDC auth integration | Sprint 12 |
| CSAT endpoint | Sprint 13 |

### 4.3 LangGraph Agent Runtime (`packages/agents`)

**Stack:** LangGraph, LangChain Core, LangChain OpenAI, LangGraph Postgres Checkpointer

#### 4.3.1 Graph topology (as built)

```text
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │ conversation│  ← OpenAI or Mock LLM
                    │   (LLM)     │
                    └──────┬──────┘
                           │
              needs_clarification / no intent
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       ┌─────────────┐           ┌─────────────┐
       │ orchestrate │           │   respond   │──► END
       │ (Python)    │           └─────────────┘
       └──────┬──────┘
              │
     rejected │ approved (CreateTicket only)
              │
       ┌──────┴──────┐
       ▼             ▼
┌─────────────┐ ┌─────────────┐
│ zammad_tool │ │   respond   │──► END
│ (Create only)│ └─────────────┘
└──────┬──────┘
       ▼
┌─────────────┐
│   respond   │──► END
└─────────────┘
```

**Implemented nodes**

| Node | File | Status |
| ---- | ---- | ------ |
| `conversation` | `nodes/conversation.py` | Implemented — calls LLM, produces `StructuredIntent` or clarification |
| `orchestrate` | `nodes/orchestrate.py` | Implemented — calls `OrchestrationEngine`, sets rejection messages |
| `zammad_tool` | `nodes/zammad_tool.py` | Partial — **CreateTicket only**; other command types return error |
| `respond` | `nodes/respond.py` | Implemented — template-based replies; does not invent ticket IDs |

**Implemented infrastructure**

| Item | Status |
| ---- | ------ |
| `SupportGraphState` | Implemented |
| `SupportGraphRunner.invoke_turn` | Implemented |
| `MockConversationLLM` | Implemented — regex-based for tests/offline |
| `OpenAIConversationLLM` | Implemented — structured output via Pydantic schema |
| Postgres checkpointer | Implemented (optional) — enabled with `GRAPH_CHECKPOINT=true` |
| LLM factory (`configure_llm`) | Implemented — loaded from FastAPI lifespan |

**Not yet implemented**

| Item | Planned sprint | Notes |
| ---- | -------------- | ----- |
| `await_user_confirm` interrupt node | Sprint 7 | Summary card before ticket submit |
| `route_intent` conditional for all intents | Sprint 9–10 | Currently only CreateTicket routes to Zammad |
| Conversation history hydration from Postgres/Redis | Sprint 6 | Graph receives `message_count` but not full history tail on each turn |
| Rolling memory summarization | Sprint 6 | Redis stores recent turns; no LLM summarization step |
| `respond` node LLM wrap-up | Sprint 7 | Currently template-only |
| Additional zammad_tool handlers | Sprint 9–10 | GetTicket, SearchTickets, UpdateTicket, AddAttachment, Escalate, Close |

### 4.4 Orchestration Layer (`packages/orchestration`)

**Design:** Pure Python — no LLM calls. All business logic is unit-testable.

**Implemented**

| Component | Status | Details |
| --------- | ------ | ------- |
| `StructuredIntent` model | Implemented | All six FSD intents defined as enum |
| `ZammadCommand` model | Implemented | CREATE_TICKET, GET_TICKET, SEARCH_TICKETS, UPDATE_TICKET, ADD_ATTACHMENT, ESCALATE_TICKET |
| `PolicyValidator` | Partial | JSON Schema validation, confidence threshold (0.6), CreateTicket required-field checks |
| `WorkflowEngine` | Partial | **CreateTicket** and **CheckStatus** command builders only |
| `OrchestrationEngine` | Implemented | Validates then builds command |
| `FieldMappingConfig` | Implemented | Loads `config/zammad-field-mapping.yaml` |
| Reason code integration | Implemented | Maps rejection codes to user messages via `packages/shared` |

**Policy rules currently enforced (CreateTicket)**

- Valid JSON Schema for intent document
- Confidence ≥ 0.6
- Non-empty title, description, customer email

**Not yet implemented**

| Rule / capability | Planned sprint |
| ----------------- | -------------- |
| CheckStatus access policy (cross-user denial) | Sprint 9 |
| UpdateTicket state transition rules | Sprint 9 |
| Attachment size/type/count limits | Sprint 8 |
| Escalation rules (VIP, keywords) | Sprint 10 |
| Duplicate ticket detection | Sprint 10 |
| Rate limiting per user/session | Sprint 12 |
| Policy rules stored in Postgres (versioned) | Future — currently Python + YAML mapping file |
| `config/policy/v1/` rules DSL | Not started — directory exists but is empty |

### 4.5 Zammad Integration (`packages/zammad-client`)

**Implemented**

| Capability | Status |
| ---------- | ------ |
| `create_ticket` | Implemented — with idempotency key header |
| `get_ticket` | Implemented |
| `search_tickets` | Implemented |
| Retry on 502/503/504/timeout | Implemented — exponential backoff, max 3 attempts |
| Error mapping (`ZammadErrorCode`) | Implemented |
| Auth schemes (Bearer / Token) | Implemented |
| Pydantic DTOs (`CreateTicketRequest`, `Ticket`, etc.) | Implemented |

**Not yet implemented**

| Capability | Planned sprint |
| ---------- | -------------- |
| `add_article` / update ticket | Sprint 9 |
| Attachment base64 encoding for articles | Sprint 10 |
| Circuit breaker → outbox queue | Sprint 11 |
| Close ticket (state transition, not DELETE) | Sprint 10 |
| Zammad reachability in `/health/ready` | Sprint 11 |

### 4.6 Shared Contracts (`packages/shared`)

**Implemented JSON schemas**

| Schema | Path | Used by |
| ------ | ---- | ------- |
| `StructuredIntent` | `schemas/intent.json` | PolicyValidator, OpenAI LLM |
| `ZammadCommand` | `schemas/command.json` | Orchestration, agents |
| UI cards | `schemas/cards.json` | MessageCard, respond node |
| Stream events | `schemas/stream-event.json` | Defined; SSE not yet implemented |

**Implemented Python modules**

- `reason_codes.py` — stable reason code enum + default user messages
- `schemas.py` — schema path resolution

---

## 5. Data Architecture

### 5.1 PostgreSQL (source of truth)

**Implemented tables** (Alembic migrations `001`, `002`)

| Table | Purpose | Populated in chat flow? |
| ----- | ------- | ----------------------- |
| `chat_sessions` | Session metadata, user_id, active_ticket_number | Yes |
| `chat_messages` | Immutable message log (user, assistant, system, card JSONB) | Yes |
| `policy_audit_log` | Orchestration decisions | **No** — table exists; only CLI writes rows |
| `zammad_operations` | Zammad API call audit | **No** — table exists; only CLI writes rows |
| `reason_code_messages` | UX copy for rejection codes | Seeded (EN v1) |

**Not yet implemented tables**

| Table | Purpose | Planned sprint |
| ----- | ------- | -------------- |
| `outbox_jobs` | Retry queue when Zammad unavailable | Sprint 11 |
| `policy_rules` / `workflow_rules` | Versioned policy config in DB | Future |
| LangGraph checkpoint tables | Via `AsyncPostgresSaver.setup()` | Optional — enabled with `GRAPH_CHECKPOINT=true` |

### 5.2 Redis (hot state)

**Implemented key patterns**

| Key | Purpose | TTL |
| --- | ------- | --- |
| `session:{id}:context` | active_ticket_number, message_count, last_message_at | 24h (configurable) |
| `session:{id}:memory` | Rolling recent turns (last 20, truncated to 500 chars) | 24h |

**Not yet implemented**

| Key | Purpose | Planned sprint |
| --- | ------- | -------------- |
| `session:{id}:stream` | Pub/sub channel for SSE fan-out | Sprint 6 |
| `ratelimit:user:{id}` | Per-user message rate limiting | Sprint 12 |
| `policy:version` | Cached policy bundle | Future |

### 5.3 Object Storage

| Item | Status |
| ---- | ------ |
| MinIO in Docker Compose | Provisioned — bucket `attachments` created by `minio-init` |
| S3 env vars in settings | Defined in `.env.example` |
| Upload API | **Not implemented** |
| Attachment metadata in Postgres | **Not implemented** |
| Zammad article attachment pipeline | **Not implemented** |

---

## 6. Request Flows

### 6.1 Create Ticket — Happy Path (implemented)

```text
1. User types message in React Composer
2. POST /api/v1/chat/sessions/{id}/messages
3. ChatService persists user message; loads Redis context (message_count)
4. SupportGraphRunner.invoke_turn(session_id, user_input, ...)
5. conversation node → OpenAI structured output → StructuredIntent (CreateTicket)
6. orchestrate node → PolicyValidator pass → WorkflowEngine builds ZammadCommand
7. zammad_tool node → ZammadClient.create_ticket → ticket number returned
8. respond node → assistant reply + ui_card (ticket_created)
9. ChatService persists system status messages + assistant message + card
10. Redis context updated with active_ticket_number
11. React reloads message history; MessageCard renders ticket
```

**Gap:** Steps 3–10 are synchronous REST — no SSE streaming, no confirm interrupt, no audit row writes.

### 6.2 Create Ticket — Policy Rejection (implemented)

```text
5. conversation node → StructuredIntent (CreateTicket, missing fields)
6. orchestrate node → PolicyValidator fail → reason code + user message
7. respond node → clarification message (needs_clarification=true)
8. Zammad is NOT called
```

### 6.3 Check Status (partially implemented)

| Layer | Status |
| ----- | ------ |
| OpenAI prompt | Can classify `CheckStatus` intent |
| WorkflowEngine | Can build `SEARCH_TICKETS` command |
| PolicyValidator | No CheckStatus-specific validation |
| Graph routing | Does not route to zammad_tool for CheckStatus |
| zammad_tool | Does not handle SEARCH_TICKETS |
| UI status card | Component exists; never emitted |

### 6.4 Target flows (not implemented)

- Update ticket (add comment/article)
- Add attachment
- Escalate issue
- Cancel/close ticket
- Confirm interrupt before ticket creation
- Outbox retry when Zammad returns 503

---

## 7. Security Architecture

### 7.1 Implemented

| Control | Implementation |
| ------- | -------------- |
| User identity on API | `require_user_id` dependency — dev header or JWT Bearer |
| Session ownership | ChatService verifies `user_id` matches session owner |
| Zammad credentials | Server-side only (`ZAMMAD_API_TOKEN` in env, never sent to browser) |
| CORS | Configurable origins (default localhost:5173) |
| LLM cannot call Zammad directly | `zammad_tool` only accepts `approved_command` from orchestration |

### 7.2 Not yet implemented

| Control | Planned sprint |
| ------- | -------------- |
| OIDC / enterprise SSO | Sprint 12 |
| Rate limiting (Redis sliding window) | Sprint 12 |
| Ticket access policy (user can only see own tickets) | Sprint 9 |
| PII redaction in logs | Sprint 12 |
| Command signing on approved_command | Sprint 12 |
| TLS termination / secrets manager | Production (Sprint 14) |
| CSP for embeddable widget | Phase 2 |

---

## 8. Deployment Architecture

### 8.1 Local development (implemented)

**Docker Compose services**

| Service | Host port | Status |
| ------- | --------- | ------ |
| PostgreSQL 16 | 5433 | Implemented |
| Redis 7 | 6380 | Implemented |
| MinIO | 9002 (API), 9003 (console) | Implemented |
| API (optional container) | 8000 | Implemented |
| Web (optional container) | 5173 | Implemented |

**Local dev workflow (recommended)**

```bash
docker compose up -d postgres redis minio minio-init
make install && make migrate
make api    # Terminal A — :8000
make web    # Terminal B — :5173
```

### 8.2 Production target (not implemented)

```text
Ingress → React static (CDN) + FastAPI replicas (K8s)
              ↓
         Redis HA + Postgres HA
              ↓
         Outbox worker + external Zammad
```

Environments, K8s manifests, secrets management, and runbooks are planned for Sprints 13–14.

### 8.3 CI/CD

| Item | Status |
| ---- | ------ |
| GitHub Actions workflows | **Removed** — not currently automated on push |
| `make lint` | Available locally (ruff + eslint) |
| `make test` | Available locally (pytest + vitest) |
| `make e2e` | Available locally (Playwright + Wiremock) |

---

## 9. Testing Architecture

### 9.1 Implemented test layers

| Layer | Location | Scope |
| ----- | -------- | ----- |
| Unit / integration (Python) | `apps/api/tests`, `packages/*/tests` | API, auth, Redis, graph, orchestration, Zammad client |
| Unit (React) | `apps/web/src/**/*.test.tsx` | ChatShell, SystemStatusLine |
| E2E (Playwright) | `e2e/tests/` | Session bootstrap, create ticket (Wiremock), session resume — mock LLM |
| Live integration | `tests/integration/` | 10 scenarios, real OpenAI + Zammad, AI User Simulator |

### 9.2 Live integration scenarios (implemented)

Defined in `tests/integration/scenarios.py`:

| Scenario ID | Category |
| ----------- | -------- |
| `vpn_network` | Network / VPN |
| `email_outlook` | Email |
| `access_locked` | Access management |
| `hardware_boot` | Hardware |
| `hardware_printer` | Hardware |
| `network_wifi` | Network |
| `access_mfa` | Access management |
| `security_phishing` | Security |
| `software_excel` | Software |
| `infrastructure_wiki` | Infrastructure |

Run via `make test-live` (API-only) or `make test-live-ui` (visible browser).

### 9.3 Not yet implemented

| Test capability | Planned sprint |
| --------------- | -------------- |
| SSE contract tests | Sprint 6 |
| Confirm interrupt E2E | Sprint 7 |
| Policy reject Playwright spec | Sprint 11 |
| Load smoke (50 concurrent sessions) | Sprint 13 |
| CI gate on PR | Sprint 4 (removed; needs restoration) |

---

## 10. Configuration

### 10.1 Environment variables (key)

| Variable | Purpose | Required for |
| -------- | ------- | ------------ |
| `DATABASE_URL` | Async Postgres connection | API |
| `REDIS_URL` | Session store | API |
| `GRAPH_ENABLED` | Enable LangGraph (vs mock graph) | Chat AI |
| `GRAPH_LLM_MODE` | `openai` or `mock` | Chat AI |
| `OPENAI_API_KEY` | OpenAI API key | Live conversation |
| `OPENAI_MODEL` | Model name (default `gpt-4o-mini`) | Live conversation |
| `ZAMMAD_BASE_URL` | Zammad instance URL | Ticket creation |
| `ZAMMAD_API_TOKEN` | Zammad API token | Ticket creation |
| `GRAPH_CHECKPOINT` | Enable Postgres LangGraph checkpointer | Optional |
| `AUTH_MODE` | `dev` or `jwt` | Auth |

See `.env.example` for the full list.

### 10.2 Committed configuration

| File | Purpose |
| ---- | ------- |
| `config/zammad-field-mapping.yaml` | Group, priority, category mappings for Zammad sandbox |
| `packages/shared/schemas/*.json` | Contract schemas for intent, commands, cards, stream events |
| `docs/postman/Tech-Support-AI.postman_collection.json` | API collection for manual testing |

---

## 11. Implementation Status Matrix

Legend: ✅ Implemented · 🟡 Partial · ❌ Not started

### 11.1 By functional use case (FSD §5)

| Use case | LLM intent | Orchestration | Zammad execution | UI card | E2E test | Overall |
| -------- | ---------- | ------------- | ---------------- | ------- | -------- | ------- |
| Create ticket | ✅ | ✅ | ✅ | ✅ | ✅ | **✅ Complete** |
| Get ticket status | 🟡 | 🟡 | ❌ | 🟡 | ❌ | **🟡 Partial** |
| Update ticket | 🟡 | ❌ | ❌ | 🟡 | ❌ | **❌ Not started** |
| Add attachment | 🟡 | ❌ | ❌ | ❌ | ❌ | **❌ Not started** |
| Escalate issue | 🟡 | ❌ | ❌ | ❌ | ❌ | **❌ Not started** |
| Cancel ticket | 🟡 | ❌ | ❌ | ❌ | ❌ | **❌ Not started** |

🟡 LLM "Partial" = OpenAI prompt lists the intent but downstream nodes do not execute it.

### 11.2 By sprint (Implementation Strategy §5)

| Sprint | Theme | Status |
| ------ | ----- | ------ |
| **1** | Monorepo & runtime | ✅ Complete |
| **2** | Session API & UI stream | ✅ Complete |
| **3** | Zammad client & orchestration skeleton | ✅ Complete |
| **4** | M1 demo — vertical skeleton | ✅ Complete (CI workflows since removed) |
| **5** | LangGraph bootstrap | ✅ Complete |
| **6** | SSE & Redis memory | ❌ Not started |
| **7** | Create ticket confirm interrupt | ❌ Not started |
| **8** | M2 — attachments, audit in chat, Storybook | ❌ Not started |
| **9** | CheckStatus & UpdateTicket | ❌ Not started |
| **10** | Attach, Escalate, Close | ❌ Not started |
| **11** | M3 — outbox, observability, degraded UI | ❌ Not started |
| **12** | SSO & security hardening | ❌ Not started |
| **13** | Performance & UAT | ❌ Not started |
| **14** | M4 — production pilot | ❌ Not started |

### 11.3 By infrastructure component

| Component | Status | Notes |
| --------- | ------ | ----- |
| Monorepo (uv workspace) | ✅ | 5 Python packages + 2 apps |
| Docker Compose | ✅ | Full stack optional |
| PostgreSQL + Alembic | ✅ | 2 migrations applied |
| Redis session store | ✅ | Context + recent turns |
| MinIO | 🟡 | Provisioned; upload not wired |
| LangGraph support_graph | 🟡 | CreateTicket path only |
| OpenAI LLM | ✅ | Structured output |
| Mock LLM | ✅ | Offline / E2E |
| Zammad HTTP client | 🟡 | Create, get, search — no update/attach |
| Audit logging (chat) | 🟡 | Service exists; not called from ChatService |
| SSE streaming | ❌ | |
| Outbox worker | ❌ | |
| OIDC auth | ❌ | JWT stub only |
| OpenTelemetry | ❌ | |
| CI/CD | ❌ | Workflows removed |
| Production K8s | ❌ | |

---

## 12. Remaining Work — Detailed Backlog

### 12.1 Sprint 6 — Real-time streaming & memory (next priority)

| ID | Deliverable | Acceptance criteria |
| -- | ----------- | --------------------- |
| S6.1 | Redis pub/sub + `GET .../stream` SSE endpoint | Browser receives events |
| S6.2 | Stream `token`, `system_status`, `done` event types | Contract test against `stream-event.json` |
| S6.3 | Hydrate graph with Postgres/Redis history tail | Multi-turn context preserved |
| S6.4 | `useSSEStream` hook + typing indicator | Indicator appears within 300ms |
| S6.5 | Wire conversation node to use history | OpenAI receives prior turns |

### 12.2 Sprint 7 — Confirm before submit

| ID | Deliverable | Acceptance criteria |
| -- | ----------- | --------------------- |
| S7.1 | `interrupt_before` confirm node in graph | Graph pauses before Zammad call |
| S7.2 | `POST .../confirm` endpoint | Resumes graph with user confirmation |
| S7.3 | Summary card component | User sees title, description, category before submit |
| S7.4 | Ticket created card only after Zammad success | No ticket number before API response |
| S7.5 | Policy reject via SSE `policy_rejected` event | Reason code shown in UI |
| S7.6 | Audit rows written on every orchestration outcome | `policy_audit_log` populated from ChatService |

### 12.3 Sprints 8–11 — Full FSD intents & resilience

See [Implementation Strategy §5](implementation-strategy.md) for task-level detail. Summary:

- **Sprint 8:** Attachment upload, audit in chat flow, Storybook, Playwright create-ticket CI
- **Sprint 9:** CheckStatus + UpdateTicket graph routing, access policy, disambiguation card
- **Sprint 10:** AddAttachment, EscalateIssue, CancelTicket, fallback panel
- **Sprint 11:** Outbox worker, degraded mode banners, OpenTelemetry, metrics dashboard

### 12.4 Sprints 12–14 — Production readiness

- **Sprint 12:** OIDC, rate limiting, PII redaction, session timeout
- **Sprint 13:** Load testing, WCAG fixes, CSAT, UAT sign-off
- **Sprint 14:** Production deploy, runbooks, pilot cohort, hypercare

### 12.5 Known technical debt

| Item | Impact | Recommended action |
| ---- | ------ | ------------------ |
| Audit not wired to chat flow | Compliance gap — orchestration decisions not persisted during normal use | Wire `AuditService` in `ChatService.send_message` (Sprint 7) |
| Policy rules in Python code | Harder to change without deploy | Migrate to Postgres-backed config (post-M3) |
| No CI on push | Regressions may slip through | Restore GitHub Actions (Sprint 4 task S4.4) |
| Graph lacks history on invoke | Multi-turn quality depends on LLM seeing only current message | Sprint 6 history hydration |
| System status is client-side cycling | Status labels don't reflect actual graph node progress | Replace with SSE-driven status (Sprint 6) |
| `config/policy/v1/` empty | Policy versioning not started | Populate or remove placeholder directory |

---

## 13. Observability (target vs actual)

| Signal | Target (Technical Strategy §11) | Actual |
| ------ | ------------------------------- | ------ |
| Structured JSON logs | All services | Basic Python logging; not structured JSON |
| OpenTelemetry traces | FastAPI → graph nodes → Zammad | Not implemented |
| Metrics (first_token, zammad_ms, reject rate) | Dashboards | Not implemented |
| Health endpoints | `/health/live`, `/health/ready` | Implemented (Postgres + Redis only) |
| LangSmith debug | Optional non-prod | Not configured |

---

## 14. Document Cross-Reference

| Topic | Primary document | This document section |
| ----- | ---------------- | --------------------- |
| Business requirements & use cases | [Functional Document](functional-document.md) | §2, §11.1 |
| Target technical design | [Technical Strategy](technical-strategy.md) | §3–§8 |
| Sprint plan & milestones | [Implementation Strategy](implementation-strategy.md) | §11.2, §12 |
| UI cards & interaction patterns | [UI/UX Strategy](ui-ux-strategy.md) | §4.1 |
| Live test approach | [Live Integration Test Strategy](test-strategy-live-integration.md) | §9 |
| Developer setup | [README](../README.md) | §8.1 |

---

## 15. Conclusion

Tech Support AI has a **solid architectural foundation** aligned with the functional and technical strategy documents. The monorepo, Docker-based local stack, LangGraph agent graph, deterministic orchestration layer, Zammad client, and React chat UI are in place. The **CreateTicket** happy path works end-to-end with real OpenAI and Zammad, validated by live integration tests.

The primary gap between current state and production MVP is **breadth and polish**:

1. **Streaming UX** (SSE) and confirm-before-submit flow
2. **Remaining five FSD intents** (status, update, attach, escalate, cancel)
3. **Resilience** (outbox, degraded modes, observability)
4. **Enterprise auth** (OIDC) and operational hardening
5. **Audit persistence** in the normal chat path

Completing Sprints 6–14 as defined in the [Implementation Strategy](implementation-strategy.md) closes these gaps and delivers the v1 production pilot.
