# Technical Strategy – Tech Support AI

## Document Control

| Item | Detail |
| ---- | ------ |
| **Related documents** | [Functional Document](functional-document.md) (FSD), [UI/UX Strategy](ui-ux-strategy.md) |
| **Stack (mandated)** | **LangGraph** (agents), **React** (UI), **PostgreSQL** (persistence), **Redis** (memory / hot state) |
| **Audience** | Engineering, architecture, DevOps, security |
| **Purpose** | Define target architecture, component boundaries, data stores, and implementation approach for v1 |

---

## 1. Executive Summary

Tech Support AI is delivered as a **React** web application talking to a **Python API** that runs **LangGraph** agent workflows. **PostgreSQL** holds durable data (sessions, messages, audit, policy config, job outbox). **Redis** holds conversational memory, session hot state, rate limits, and real-time streaming fan-out.

The FSD’s separation of concerns is preserved in code:

| FSD layer | Implementation |
| --------- | -------------- |
| Conversation Agent | LangGraph graph (LLM nodes + structured output) |
| Orchestration | Deterministic Python service (not LLM); invoked as a LangGraph node/tool |
| Ticket Management | LangGraph tool node + Zammad HTTP client |
| Integration Layer | Shared `zammad` module (retries, auth, errors) |
| Web Chat | React SPA / embeddable widget |

Business rules live in **versioned policy/workflow config** stored in Postgres, evaluated by orchestration—not in prompts.

---

## 2. Architecture Overview

### 2.1 Logical Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                     React Web Chat (UI)                          │
│  SSE/WebSocket · REST · Auth (SSO cookie / Bearer)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              API Gateway / BFF (FastAPI)                         │
│  /chat/sessions · /chat/messages · /chat/stream · /health        │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌────────────────┐   ┌───────────────┐
│  LangGraph    │   │ Orchestration  │   │  Zammad       │
│  Runtime      │──►│ Service        │──►│  Client       │
│  (agents)     │   │ (policy/rules) │   │  (HTTP)       │
└───────┬───────┘   └────────┬───────┘   └───────────────┘
        │                    │
        ▼                    ▼
┌───────────────┐   ┌────────────────┐
│    Redis      │   │  PostgreSQL    │
│  memory/cache │   │  durable store │
└───────────────┘   └────────────────┘
```

### 2.2 Request Path (Happy Path – Create Ticket)

```text
1. React POST /chat/sessions/{id}/messages + optional SSE subscribe
2. API loads Redis session memory + Postgres history tail
3. LangGraph: conversation node → structured intent (JSON schema)
4. LangGraph: orchestration node → PolicyValidator + WorkflowEngine
5. If approved → ticket_tool node → Zammad POST /api/v1/tickets
6. Persist assistant message + card payload + audit row in Postgres
7. Publish stream events via Redis pub/sub → SSE to React
8. Update Redis memory summary + active_ticket context
```

Rejected policy paths stop at step 4; Zammad is never called (FSD §13).

---

## 3. Technology Stack

### 3.1 Core Choices

| Layer | Technology | Role |
| ----- | ---------- | ---- |
| **Agents** | LangGraph + LangChain | Graph-based workflows, tool calling, structured outputs |
| **LLM** | Configurable provider (OpenAI / Azure OpenAI / Anthropic) | Conversation only; pluggable via env |
| **API** | Python 3.12+, FastAPI | REST, SSE, auth middleware, DI |
| **UI** | React 18+, TypeScript, Vite | Web chat per UI/UX strategy |
| **Durable DB** | PostgreSQL 15+ | Sessions, messages, audit, policies, outbox |
| **Memory / cache** | Redis 7+ | Turn memory, session state, rate limits, pub/sub |
| **Migrations** | Alembic | Postgres schema |
| **Policy engine** | Python + JSON Schema + rules DSL (YAML/JSON in Postgres) | Deterministic orchestration |
| **Observability** | OpenTelemetry, structured logging (JSON) | Traces across graph nodes and Zammad |

### 3.2 Monorepo Layout (Recommended)

```text
tech-support-ai/
├── apps/
│   ├── web/                 # React chat UI
│   └── api/                 # FastAPI + LangGraph entrypoints
├── packages/
│   ├── agents/              # LangGraph graphs, prompts, tools
│   ├── orchestration/       # Policy validator, workflow rules
│   ├── zammad-client/       # HTTP client, DTOs, retries
│   └── shared/              # Types, reason codes, event schemas
├── infra/
│   ├── docker/
│   └── migrations/          # Alembic
└── docs/
```

---

## 4. LangGraph Agent Design

### 4.1 Design Principles

1. **One primary graph** per chat session invocation (`support_graph`).
2. **LLM only in conversation nodes**—orchestration and Zammad mapping are deterministic code nodes.
3. **Structured outputs** via LangChain `with_structured_output` / JSON schema for `StructuredIntent` (FSD §6).
4. **Checkpointing**: LangGraph Postgres checkpointer for graph state recovery; Redis for fast conversational recall (see §6).
5. **Human-in-the-loop**: `interrupt_before` on `confirm_submit` when summary card requires explicit user confirmation (UI/UX §6.1).

### 4.2 Graph State Schema

```python
class SupportGraphState(TypedDict):
    session_id: str
    user_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    structured_intent: StructuredIntent | None
    orchestration_result: OrchestrationResult | None  # approve | reject | modify
    approved_command: ZammadCommand | None
    zammad_response: dict | None
    ui_events: list[UIEvent]  # cards, system status lines for frontend
    active_ticket_number: str | None
    error: str | None
```

### 4.3 Node Topology

```text
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
              ┌────│ conversation │────┐
              │    │   (LLM)      │    │
              │    └──────┬──────┘    │
              │           ▼           │
              │    ┌─────────────┐     │ no action yet
              │    │ route_intent│     │
              │    └──────┬──────┘     │
              │           ▼           │
              │    ┌─────────────┐     │
              │    │  await_user │◄────┘ (clarify / gather)
              │    │  _confirm   │ (interrupt if CreateTicket etc.)
              │    └──────┬──────┘
              │           ▼
              │    ┌─────────────┐
              │    │ orchestrate │  ← deterministic, no LLM
              │    └──────┬──────┘
              │      reject│approve
              │           ▼
              │    ┌─────────────┐
              │    │ zammad_tool │
              │    └──────┬──────┘
              │           ▼
              │    ┌─────────────┐
              └────│  respond    │ (LLM: NL wrap-up OR template)
                   │   (LLM)     │
                   └──────┬──────┘
                          ▼
                       END
```

### 4.4 Node Responsibilities

| Node | Type | Responsibility |
| ---- | ---- | -------------- |
| `conversation` | LLM | NLU, clarifying questions, populate `StructuredIntent` when ready |
| `route_intent` | Conditional | Branch: needs clarification vs ready for orchestration vs chit-chat |
| `await_user_confirm` | Interrupt | Pause graph until UI sends `confirm` / `edit` (UI/UX summary card) |
| `orchestrate` | Python | Call `PolicyValidator` + `WorkflowEngine`; set `approved_command` or rejection |
| `zammad_tool` | Python | Execute approved command via integration layer only |
| `respond` | LLM or template | Generate user message + `ui_events` (cards); **must not invent ticket IDs** |

### 4.5 Ticket Management as Tools (Not a Separate LLM Agent)

The FSD “Ticket Management Agent” is implemented as **typed tool functions** bound to the graph, not a second LLM:

```python
@tool
def create_ticket(cmd: CreateTicketCommand) -> ZammadTicketResult: ...

@tool
def get_ticket_status(cmd: GetTicketCommand) -> ZammadTicketResult: ...

@tool
def add_ticket_article(cmd: AddArticleCommand) -> ZammadArticleResult: ...
```

The `zammad_tool` node dispatches by `approved_command.type`. This prevents the model from calling Zammad directly.

### 4.6 Prompting Strategy

| Concern | Location |
| ------- | -------- |
| Tone, intake questions, summarization | `conversation` / `respond` system prompts |
| Field requirements checklist | Prompt references schema only; **enforcement in orchestration** |
| Priority/category/group mapping | Workflow rules in Postgres-backed config |
| Reason-code user messages | Mapping table in Postgres (`reason_code_messages`) |

### 4.7 LangGraph Runtime Configuration

```python
graph = builder.compile(
    checkpointer=PostgresSaver(conn_string),  # durable graph checkpoints
    interrupt_before=["await_user_confirm"],
)
```

Invoke with `thread_id = session_id` for idempotent resume after confirm or page refresh.

---

## 5. Orchestration Layer (Deterministic)

### 5.1 Module Boundaries

Package: `packages/orchestration/`

| Component | Input | Output |
| --------- | ----- | ------ |
| `PolicyValidator` | `StructuredIntent`, `UserContext` | `ValidationResult` (pass/fail, reason codes) |
| `WorkflowEngine` | Validated intent | `ZammadCommand` (approved, normalized fields) |
| `AuditRecorder` | All decisions | Rows in `policy_audit_log` (Postgres) |

### 5.2 Policy Configuration

* Stored in Postgres: `policy_rules`, `workflow_rules`, `field_mappings` (versioned, `effective_at`)
* Loaded into memory on change (Redis cache key `policy:current_version` with TTL + pub/sub invalidation)
* Evaluated with:
  * **JSON Schema** for `StructuredIntent.payload`
  * **Rule expressions** (recommended: `jsonlogic` or custom DSL compiled to Python predicates)

### 5.3 Reason Codes

Stable codes (e.g. `TICKET_ACCESS_DENIED`) flow to:

1. LangGraph state → `respond` node / template
2. API SSE event `policy_rejected`
3. UI/UX copy catalog (Postgres `reason_code_messages`)

---

## 6. Redis vs PostgreSQL — Data Responsibilities

### 6.1 Redis (Memory & Hot Path)

| Key pattern | Purpose | TTL |
| ----------- | ------- | --- |
| `session:{id}:memory` | Rolling conversation summary + salient slots (issue, device, ticket ref) | 24h (configurable) |
| `session:{id}:context` | `active_ticket_number`, last intent, UI state | 24h |
| `session:{id}:history` | Recent message window (last N turns) for fast graph hydrate | 24h |
| `session:{id}:stream` | Pub/sub channel for SSE fan-out | n/a |
| `ratelimit:user:{id}` | Per-user message rate (FSD policy) | 1h sliding |
| `policy:version` | Cached policy bundle version | 5m |

**LangGraph “memory”**: Use Redis to inject a **session memory block** into the `conversation` node system prompt (summary maintained by a small summarization step every K turns). Full message history tail is loaded from Postgres when Redis window is cold.

**Do not** store sole copy of audit or ticket outcomes in Redis.

### 6.2 PostgreSQL (Source of Truth)

| Table group | Purpose |
| ----------- | ------- |
| `chat_sessions` | Session metadata, user_id, org_id, status |
| `chat_messages` | Immutable message log (user, assistant, system, card JSON) |
| `policy_audit_log` | Intent, rule id, outcome, reason code (FSD §11) |
| `zammad_operations` | Approved command + API response snapshot (sanitized) |
| `policy_rules` / `workflow_rules` | Versioned configuration |
| `reason_code_messages` | UX copy mapping |
| `outbox_jobs` | Zammad unavailable queue (FSD §9) |
| `langgraph_checkpoints` | Via LangGraph `PostgresSaver` (official checkpointer table set) |

### 6.3 Consistency Pattern

* **Write-through**: On each completed turn, append `chat_messages` in Postgres, then update Redis memory.
* **Outbox worker**: Background process (API worker or Celery/Arq) retries `outbox_jobs` when Zammad is down.

---

## 7. React Frontend Architecture

### 7.1 Stack

| Concern | Choice |
| ------- | ------ |
| Framework | React 18 + TypeScript |
| Build | Vite |
| Routing | React Router (full page) or single-page embed mode |
| State | Zustand or React Query for server state |
| Styling | CSS Modules or Tailwind (org tokens via CSS variables per UI/UX §10) |
| Streaming | `EventSource` (SSE) primary; WebSocket optional for bidirectional |
| Forms / composer | Controlled textarea + file input; drag-drop |
| A11y | Headless UI primitives, `aria-live` regions per UI/UX §11 |

### 7.2 Key Modules

```text
apps/web/src/
├── components/
│   ├── ChatShell/
│   ├── MessageStream/      # user | assistant | system | error
│   ├── cards/              # TicketCreated, Status, Summary, Disambiguation
│   ├── Composer/
│   └── ContextStrip/
├── hooks/
│   ├── useChatSession.ts
│   ├── useSSEStream.ts
│   └── useSendMessage.ts
├── api/
│   └── chatClient.ts
└── types/
    └── events.ts           # mirrors backend UIEvent schema
```

### 7.3 API Contract (BFF)

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/chat/sessions` | Create session (auth required) |
| `GET` | `/api/v1/chat/sessions/{id}` | Session + context strip |
| `GET` | `/api/v1/chat/sessions/{id}/messages` | Paginated history |
| `POST` | `/api/v1/chat/sessions/{id}/messages` | User message → triggers graph |
| `GET` | `/api/v1/chat/sessions/{id}/stream` | SSE: tokens, system status, cards |
| `POST` | `/api/v1/chat/sessions/{id}/confirm` | Resume graph after `interrupt` |
| `POST` | `/api/v1/chat/sessions/{id}/attachments` | Upload to object store → URL in message |

### 7.4 SSE Event Types (align with UI/UX §7)

```typescript
type StreamEvent =
  | { type: "token"; content: string }
  | { type: "system_status"; label: "validating" | "creating_ticket" | ... }
  | { type: "card"; card: TicketCreatedCard | StatusCard | ... }
  | { type: "policy_rejected"; reason_code: string; message: string }
  | { type: "done"; message_id: string }
  | { type: "error"; code: string; message: string };
```

**Rule:** `card` events with ticket numbers are emitted only after Zammad success (UI/UX §3.1).

### 7.5 Embedding

* NPM package `@org/support-chat-widget` exporting `SupportChatWidget`
* `postMessage` bridge for parent portal SSO token when needed
* Lazy-loaded chunk (&lt; 150KB gzip target for widget shell)

---

## 8. API & Backend Services

### 8.1 FastAPI Application Layers

| Layer | Responsibility |
| ----- | -------------- |
| `routers/` | HTTP, auth, request validation |
| `services/chat_service.py` | Session lifecycle, invoke LangGraph |
| `services/stream_service.py` | Redis pub/sub → SSE |
| `dependencies/` | DB pool, Redis, graph compile singleton |
| `workers/outbox_worker.py` | Retry Zammad operations |

### 8.2 Authentication

| Mode | Implementation |
| ---- | -------------- |
| Enterprise SSO | OIDC → API issues session cookie or short-lived JWT |
| User identity | `user_id`, `email` in JWT claims → `UserContext` for orchestration |
| Zammad | Service account token in secrets manager; never exposed to browser |

### 8.3 Attachment Pipeline

```text
React upload → API (virus scan hook) → S3-compatible object store
  → message references storage_key
  → orchestration validates policy
  → zammad_tool base64-encodes for ticket_articles API
```

Postgres stores metadata only; blobs in object store.

---

## 9. Zammad Integration Layer

Package: `packages/zammad-client/`

| Feature | Implementation |
| ------- | -------------- |
| HTTP | `httpx` async client |
| Auth | `Authorization: Bearer` or `Token token=` per env |
| Retries | Exponential backoff on 502/503/timeout (FSD §9) |
| Circuit breaker | `pybreaker` or custom; opens → outbox queue |
| Idempotency | `Idempotency-Key` header on create (client-generated UUID per confirm) |
| DTOs | Pydantic models mirroring Zammad ticket/article shapes |
| Errors | Map to `ZammadErrorCode` enum → orchestration / UI |

Commands from workflow engine use **Zammad-native** names (`group`, `priority`, custom object keys)—not LLM suggestions.

---

## 10. Security Architecture

| Control | Approach |
| ------- | -------- |
| TLS | Terminate at ingress; TLS to Postgres/Redis in prod |
| Secrets | Vault / K8s secrets; rotate Zammad token |
| RBAC | API enforces `user_id` scope; orchestration re-checks ticket ownership |
| PII in logs | Redact attachment bodies; truncate article text in debug logs |
| CSP | Strict script-src for React embed |
| Rate limiting | Redis sliding window per user + per session |
| Command signing | `approved_command` HMAC or internal-only type serialized in graph state—`zammad_tool` rejects unsigned payloads |

---

## 11. Observability & Operations

| Signal | Tooling |
| ------ | ------- |
| Traces | OpenTelemetry: FastAPI → LangGraph nodes → Zammad HTTP |
| Metrics | Latency histograms: `first_token`, `orchestration_ms`, `zammad_ms`, policy reject rate |
| Logs | JSON struct logs with `session_id`, `intent`, `reason_code` |
| LangGraph debug | LangSmith (optional env flag) for graph visualization in non-prod |
| Health | `/health/live`, `/health/ready` (Postgres + Redis + Zammad reachability) |

### 11.1 SLO Alignment (FSD §10, §17)

| SLO | Measurement |
| --- | ----------- |
| First token &lt; 3s | SSE `token` event timestamp − request start |
| Ticket create &lt; 5s (API) | `zammad_operations.duration_ms` |
| 99.9% API availability | Ingress + API replicas |

---

## 12. Deployment Topology

### 12.1 Recommended Production (Kubernetes)

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Ingress    │────►│  web (CDN)  │     │  React static│
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  api x N    │────►│  Redis      │     │  Postgres   │
│  (FastAPI)  │     │  (HA)       │     │  (HA)       │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ outbox      │     │  Zammad     │
│ worker x1   │     │  (external) │
└─────────────┘     └─────────────┘
```

### 12.2 Environments

| Env | Purpose |
| --- | ------- |
| `dev` | Local Docker Compose: api, web, postgres, redis, mock Zammad |
| `staging` | Real Zammad sandbox; LangSmith on |
| `prod` | HA, no mock, strict secrets |

### 12.3 Local Development (Docker Compose)

Services: `api`, `web`, `postgres`, `redis`, `minio` (attachments), optional `zammad` or wiremock.

---

## 13. Schema Sketch (PostgreSQL)

```sql
-- Core session
CREATE TABLE chat_sessions (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  org_id TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  active_ticket_number TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES chat_sessions(id),
  role TEXT NOT NULL,  -- user | assistant | system
  content TEXT,
  card JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE policy_audit_log (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL,
  intent TEXT NOT NULL,
  payload JSONB,
  outcome TEXT NOT NULL,  -- approved | rejected | modified
  reason_code TEXT,
  rule_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE zammad_operations (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL,
  command_type TEXT NOT NULL,
  command JSONB NOT NULL,
  response JSONB,
  status TEXT NOT NULL,
  duration_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE outbox_jobs (
  id UUID PRIMARY KEY,
  command JSONB NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  next_run_at TIMESTAMPTZ NOT NULL,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Indexes: `(session_id, created_at)` on messages; `(user_id, created_at)` on sessions; `(next_run_at)` on outbox where `status = pending`.

---

## 14. Implementation Phases

### Phase 1 — Foundation (Weeks 1–4)

* Monorepo, Docker Compose, Postgres + Redis + Alembic
* FastAPI skeleton, auth stub, session/message CRUD
* React ChatShell + MessageStream + Composer (no AI)
* Zammad client: create ticket + get ticket (integration tests)

### Phase 2 — LangGraph Core (Weeks 5–8)

* `support_graph` with conversation + orchestrate + zammad_tool nodes
* Structured intent schema; policy validator v1 (required fields, attachment limits)
* SSE streaming; Redis memory + pub/sub
* Summary card confirm flow (`interrupt_before`)
* Postgres audit + zammad_operations

### Phase 3 — Full FSD Intents (Weeks 9–11)

* CheckStatus, UpdateTicket, AddAttachment, EscalateIssue, CancelTicket
* Disambiguation in graph routing + UI cards
* Outbox worker; degraded modes
* OTel + metrics dashboards

### Phase 4 — Hardening (Weeks 12+)

* SSO integration, policy admin API, load testing
* WCAG audit fixes, CSAT endpoint
* Production runbooks

---

## 15. Key Technical Decisions (ADRs Summary)

| Decision | Rationale | Alternatives rejected |
| -------- | --------- | ---------------------- |
| LangGraph for agents | Explicit flow, interrupts, checkpointing, tool gating | Raw LangChain AgentExecutor (opaque loops) |
| Orchestration outside LLM | FSD mandate; auditable, testable rules | LLM-as-judge for policy |
| Redis for memory | Sub-ms session hydrate; pub/sub for SSE | Postgres-only (higher latency per turn) |
| Postgres for durability | ACID audit, compliance, LangGraph checkpointer | Redis-only persistence |
| React SPA | UI/UX strategy; embeddable widget | Server-rendered only |
| FastAPI + async | Matches async httpx Zammad + graph invoke | Node.js (split agent ecosystem) |
| SSE over WebSocket v1 | Simpler one-way stream for tokens/cards | WS first (more ops complexity) |

---

## 16. Testing Strategy

| Layer | Approach |
| ----- | -------- |
| Orchestration | Unit tests per rule fixture; table-driven reason codes |
| Zammad client | Wiremock / recorded cassettes |
| LangGraph | Graph integration tests with mock LLM returning fixed structured intents |
| API | pytest + TestClient; contract tests for SSE event shapes |
| React | Vitest + Testing Library; Storybook for cards |
| E2E | Playwright: create ticket happy path + policy rejection |

**CI gate:** No graph deploy if orchestration coverage on critical rules &lt; agreed threshold.

---

## 17. Risks & Mitigations

| Risk | Mitigation |
| ---- | ---------- |
| LLM bypasses orchestration | `zammad_tool` only accepts `approved_command` type |
| Redis memory loss | Postgres history tail rebuilds context |
| Graph hang on interrupt | Session timeout; UI “Cancel request” clears interrupt |
| Zammad rate limits | Client-side limiter + outbox |
| Prompt injection | Orchestration validates payloads; tools are fixed enum |
| Checkpoint bloat | TTL job archiving old checkpoints |

---

## 18. Document Cross-Reference

| Technical topic | Source doc |
| --------------- | ---------- |
| Use cases & intents | FSD §5–§6 |
| Orchestration behavior | FSD §3.3, §13 |
| UI cards & SSE events | UI/UX §6–§7, §12.1 |
| Ticket ID rules | FSD §9 |
| Audit requirements | FSD §11 |
| NFRs / KPIs | FSD §10, §17 |

---

## 19. Conclusion

The technical strategy implements the FSD’s three-tier model—**LangGraph for conversation**, **deterministic orchestration for control**, **Zammad tools for execution**—with **React** delivering the web chat experience. **PostgreSQL** is the system of record for compliance and history; **Redis** powers fast session memory and real-time streaming. This split is testable, enterprise-appropriate, and aligned with both the functional and UX strategies without embedding business logic in LLM prompts.
