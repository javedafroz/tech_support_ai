# Solution Architecture

## Overview

**Tech Support AI** is a **React** web chat UI, an **Admin SPA** for Agent Handbook maintenance, and a **FastAPI** backend. The API owns session persistence, attachment staging, graph invocation, and KB admin routes. Each user message runs through a **LangGraph** workflow (`packages/agents`) that calls an **LLMGateway** for conversation, a **troubleshoot** node when `KB_RAG_ENABLED=true` (Qdrant retrieval via `packages/knowledge`), and a **TicketGateway** for help desk operations. **PostgreSQL** is the durable store; **Redis** caches session context and recent turns; **MinIO/S3** holds attachment bytes; **Qdrant** holds handbook vectors; handbook source files use **Ceph RGW** (or S3-compatible / in-memory for local dev).

## Runtime modes

Two independent flags control behaviour. They are often confused in diagrams — both matter.

| `GRAPH_ENABLED` | `GRAPH_LLM_MODE` | What runs on `POST .../messages` |
| --------------- | ---------------- | -------------------------------- |
| `false` | *(any)* | **`MockSupportGraph`** in `apps/api` — rule-based stub, **no LangGraph**, **no Zammad** |
| `true` | `mock` | **LangGraph** + **`MockConversationLLM`** — full orchestration and ticket_tool **can** call Zammad |
| `true` | not `mock` | **LangGraph** + live **LLMGateway** (`LLM_PROVIDER`: OpenAI, Azure OpenAI, or Anthropic) |

`GRAPH_LLM_MODE=mock` only applies when `GRAPH_ENABLED=true`. It selects the agents-package mock LLM, not the API-layer `MockSupportGraph`.

Optional: `GRAPH_CHECKPOINT=true` persists LangGraph thread state to PostgreSQL via `langgraph-checkpoint-postgres` (off by default).

## Logical architecture (as implemented)

```mermaid
flowchart TB
    subgraph Clients["Clients"]
        Web["React chat<br/>apps/web<br/>REST · SSE · upload"]
        Admin["Admin SPA<br/>apps/admin<br/>Handbook upload / publish"]
        KC["Keycloak<br/>Admin OIDC"]
    end

    subgraph API["FastAPI BFF — apps/api"]
        ChatSvc["ChatService"]
        AttSvc["AttachmentService"]
        KbSvc["KbService"]
        Runner["SupportGraphRunner"]
        Routes["/health · /api/v1/chat/* · /api/v1/admin/kb/* · /api/v1/config/public"]
    end

    subgraph Stores["Data stores"]
        PG[("PostgreSQL<br/>sessions · messages · KB metadata")]
        RD[("Redis<br/>context · recent turns")]
        MinIO[("MinIO/S3<br/>attachments")]
        QD[("Qdrant<br/>handbook vectors")]
        HB[("Handbook store<br/>Ceph RGW / S3 / MinIO bucket / memory")]
    end

    subgraph Graph["LangGraph — packages/agents"]
        direction LR
        Conv["conversation"] --> TS["troubleshoot"]
        TS --> Orch["orchestrate"]
        Orch --> TT["ticket_tool"]
        TT --> Resp["respond"]
    end

    subgraph Externals["External / packages"]
        LLM["LLMGateway<br/>OpenAI / Azure / Anthropic"]
        Know["packages/knowledge<br/>retrieve chunks"]
        OrchEng["OrchestrationEngine<br/>policy + workflow"]
        TG["TicketGateway<br/>Zammad"]
    end

    Web -->|"HTTPS"| Routes
    Admin -->|"Bearer JWT"| Routes
    Admin --> KC
    KC -.->|"JWKS / roles"| Routes

    Routes --> ChatSvc
    Routes --> AttSvc
    Routes --> KbSvc
    ChatSvc --> Runner

    ChatSvc --> PG
    ChatSvc --> RD
    AttSvc --> MinIO
    AttSvc --> PG
    KbSvc --> PG
    KbSvc --> HB
    KbSvc --> QD

    Runner -->|"GRAPH_ENABLED=true"| Graph
    Conv --> LLM
    TS --> Know
    Know --> QD
    Orch --> OrchEng
    TT --> TG
```

**What the diagram shows:**

- **ChatService** (not LangGraph) reads/writes PostgreSQL and Redis, stages attachments, then invokes the graph.
- **KbService** + Admin routes manage handbook ingest/publish; chat retrieval only uses **published** documents in Qdrant.
- **Orchestration** is a **LangGraph node** (`orchestrate_node`), not a separate service the API calls directly.
- **LLMGateway** and **TicketGateway** are built inside graph nodes (`get_conversation_llm()`, `build_ticket_gateway()`), not singleton microservices.
- **Object storage:** attachments via `AttachmentService` (`S3_*`); handbooks via `CEPH_RGW_*` / `KB_HANDBOOK_*` (Compose may point both at MinIO with **different buckets**).
- **Troubleshoot** is classic RAG: deterministic retrieval + grounded LLM guidance with citation validation.

## Design principles

1. **LLM for language only** — Conversation, clarification, structured intent proposals, and screenshot text extraction. Not business policy.
2. **Orchestration gates every help desk call** — `PolicyValidator` + `WorkflowEngine` in the `orchestrate` node before `ticket_tool` runs.
3. **Provider-grounded ticket IDs** — Ticket numbers in the UI come only from Zammad API responses.
4. **Pluggable LLM** — `LLMGateway` protocol; OpenAI (default), Azure OpenAI, Anthropic; mock when `GRAPH_LLM_MODE=mock`.
5. **Pluggable ticketing** — `TicketGateway` protocol; Zammad live, ServiceNow stub.
6. **API owns persistence** — Graph nodes are stateless per turn; messages and sessions are saved by `ChatService` after the graph completes.
7. **Attachments staged before the graph** — Upload → object storage → link on user message → `pending_attachments` in graph state.
8. **No MCP** — Direct REST/SDK integration.
9. **Troubleshoot uses classic RAG** — Handbook retrieval uses Python + Qdrant; the configured LLM synthesizes adaptive grounded steps with validated source citations. Chat never reveals handbook titles; ticket enrichment may name the handbook for agents.

## End-to-end flow: send message

This is the actual path implemented in `ChatService.send_message` / `send_message_stream`. Attachment upload (`POST .../attachments`) is a separate step before the message is sent — files are already in MinIO when the message arrives.

```mermaid
sequenceDiagram
    autonumber
    participant U as User Web UI
    participant API as FastAPI ChatService
    participant PG as PostgreSQL
    participant RD as Redis
    participant G as LangGraph

    U->>API: POST chat sessions messages
    API->>API: Authenticate X-User-Id or JWT
    API->>PG: Load session and verify ownership
    API->>RD: Load session context
    alt Redis memory hit
        API->>RD: Load recent turns max 20
    else Redis miss
        API->>PG: Load chat_messages history
    end
    API->>PG: Insert user ChatMessage
    opt attachment_ids present
        API->>PG: Link session_attachments to message
        API->>API: Build pending_attachments payload
    end
    API->>G: Invoke graph turn
    G-->>API: assistant_reply ui_card system_statuses intent
    API->>PG: Persist system status messages
    API->>PG: Persist assistant message and card JSON
    API->>PG: Update session active_ticket_number
    API->>RD: record_turn context and memory
    API-->>U: Return user and assistant messages
```

## LangGraph flow (GRAPH_ENABLED=true)

Compiled graph: `packages/agents/graph.py` → `SupportGraphRunner` in `packages/agents/runner.py`.

### Topology

Routing overview (control flow):

```mermaid
flowchart TD
    START([START]) --> conversation
    conversation -->|KB on + support issue / guiding| troubleshoot
    conversation -->|needs_clarification / no intent| respond
    conversation -->|structured intent ready| orchestrate
    troubleshoot -->|guiding or resolved| respond
    troubleshoot -->|escalated| orchestrate
    troubleshoot -->|skipped| respond_or_orch{clarifying?}
    respond_or_orch -->|yes| respond
    respond_or_orch -->|no| orchestrate
    orchestrate -->|rejected / no command| respond
    orchestrate -->|approved CREATE / SEARCH / ADD_ATTACHMENT| ticket_tool
    ticket_tool --> respond
    respond --> END([END])
```

Typical **single-turn** execution through graph nodes:

```mermaid
sequenceDiagram
    autonumber
    participant API as ChatService
    participant G as SupportGraphRunner
    participant Conv as conversation
    participant TS as troubleshoot
    participant Orch as orchestrate
    participant TT as ticket_tool
    participant Resp as respond

    API->>G: ainvoke or astream_turn
    G->>Conv: Run node
    Conv-->>G: structured_intent routing flags
    alt KB troubleshoot path
        G->>TS: Run node
        TS-->>G: guiding resolved escalated or skipped
    end
    alt Needs ticket search or attachment command
        G->>Orch: Run node
        Orch-->>G: approved_command or rejection
        opt Approved command
            G->>TT: Run node
            TT-->>G: ui_card provider_response
        end
    end
    G->>Resp: Run node
    Resp-->>G: final assistant_reply
    G-->>API: SupportGraphState
```

`KB_RAG_ENABLED=false` skips the troubleshoot branch entirely (legacy CreateTicket path).

### Node responsibilities (actual code)

| Node | Module | What it does |
| ---- | ------ | ------------ |
| `conversation` | `nodes/conversation.py` | Adds user message to state; **short-circuits LLM** when `pending_attachments` + `active_ticket_number` → builds `AddAttachment` intent directly; else calls `LLMGateway.propose_intent()`; sets `structured_intent`, `is_support_issue`, `problem_summary`, and optional clarify `assistant_reply` |
| `troubleshoot` | `nodes/troubleshoot.py` | Retrieves handbook chunks via `packages/knowledge`; calls `LLMGateway.generate_troubleshoot_guidance` for adaptive grounded steps (citation-validated; empathetic copy, no handbook name); on fail/escalate synthesizes/enriches `CreateTicket`; on resolve deflects (no ticket) |
| `orchestrate` | `nodes/orchestrate.py` | `OrchestrationEngine.process()` — policy validation + workflow mapping → `approved_command` or rejection message |
| `ticket_tool` | `nodes/ticket_tool.py` | `build_ticket_gateway().execute(TicketCommand)` — create ticket, search, or add attachment; sets `ui_card`, `active_ticket_number`, `provider_response` |
| `respond` | `nodes/respond.py` | Formats final `assistant_reply` (prefers ticket-created confirmation over stale clarify text) |

### Routing rules

| From | Condition | To |
| ---- | --------- | -- |
| `conversation` | `kb_rag_enabled` and (`troubleshoot` guiding, or support issue / CreateTicket) and **no** `active_ticket_number` and status not skipped/resolved/escalated | `troubleshoot` |
| `conversation` | `needs_clarification` or no `structured_intent` (and not routing to troubleshoot) | `respond` |
| `conversation` | `structured_intent` present | `orchestrate` |
| `troubleshoot` | status `guiding` or `resolved` | `respond` |
| `troubleshoot` | status `escalated` | `orchestrate` |
| `troubleshoot` | status `skipped` | `respond` if clarifying; else `orchestrate` |
| `orchestrate` | not `APPROVED` or no command | `respond` |
| `orchestrate` | approved `CREATE_TICKET`, `SEARCH_TICKETS`, or `ADD_ATTACHMENT` | `ticket_tool` |
| `ticket_tool` | always | `respond` |

Sessions with an **active ticket** skip L1 troubleshoot (attachment / status flows continue normally).

### Graph state (`SupportGraphState`)

Key fields: `user_input`, `messages`, `pending_attachments`, `structured_intent`, `orchestration_result`, `approved_command`, `system_statuses`, `ui_card`, `active_ticket_number`, `assistant_reply`, `needs_clarification`, `kb_rag_enabled`, `is_support_issue`, `problem_summary`, `troubleshoot`, `troubleshoot_deflection`.

## Request flow: L1 troubleshoot then ticket (KB on)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as ChatService
    participant G as LangGraph
    participant Conv as conversation
    participant TS as troubleshoot
    participant QD as Qdrant
    participant Orch as orchestrate
    participant TT as ticket_tool
    participant Z as Zammad
    participant PG as PostgreSQL

    U->>API: Describes support problem
    API->>G: Invoke graph
    G->>Conv: NLU + support issue detection
    Conv-->>G: is_support_issue, problem_summary
    G->>TS: Retrieve + guide
    TS->>QD: Vector search published handbooks
    QD-->>TS: Chunk matches
    TS-->>G: status guiding one step
    G-->>API: Empathetic step no handbook name
    API-->>U: Guided self-help reply

    alt User confirms fix deflection
        U->>API: That worked
        API->>G: Invoke graph
        G->>TS: Classify resolve
        TS-->>G: status resolved
        G-->>API: Deflection reply
        API->>PG: Record kb_deflection_events
        API-->>U: Acknowledgement no ticket
    else User still blocked escalate
        U->>API: Still not working
        API->>G: Invoke graph
        G->>TS: Escalate
        TS-->>G: CreateTicket intent steps and transcript
        G->>Orch: Policy and workflow
        Orch-->>G: Approved CREATE_TICKET
        G->>TT: Execute command
        TT->>Z: POST api v1 tickets
        Z-->>TT: Ticket number
        TT-->>G: ticket_created card
        G-->>API: Ticket confirmation only
        API-->>U: Ticket card
    end
```

## Request flow: create ticket (happy path, KB off or no match)

```mermaid
sequenceDiagram
    autonumber
    participant U as User Web UI
    participant API as ChatService
    participant S3 as MinIO S3
    participant G as LangGraph
    participant Conv as conversation
    participant LLM as LLMGateway
    participant Orch as orchestrate
    participant TT as ticket_tool
    participant Z as Zammad
    participant RD as Redis

    opt Screenshot or file attached
        U->>API: POST attachments multipart
        API->>S3: put_object
        API-->>U: attachment_id
    end
    U->>API: POST messages with content and attachment_ids
    API->>G: Invoke with pending_attachments
    G->>Conv: propose_intent
    Conv->>LLM: Structured intent extraction with optional vision
    LLM-->>Conv: CreateTicket StructuredIntent
    Conv-->>G: Intent and merged attachments
    G->>Orch: OrchestrationEngine.process
    Orch-->>G: Approved TicketCommand from YAML mapping
    G->>TT: Execute CREATE_TICKET
    TT->>S3: get_object and encode for Zammad
    TT->>Z: POST api v1 tickets with attachments
    Z-->>TT: ticket number and state
    TT-->>G: ui_card ticket_created
    G-->>API: Assistant reply and card
    API->>RD: Update active_ticket_number
    API-->>U: Ticket card in chat
```

If orchestration rejects, `ticket_tool` is never reached — the graph routes to `respond` with a clarification or rejection message.

## Request flow: add attachment to active ticket

Two paths exist in code:

**A — LLM bypass:** session already has `active_ticket_number` and user sends new files.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as ChatService
    participant G as LangGraph
    participant Conv as conversation
    participant Orch as orchestrate
    participant TT as ticket_tool
    participant S3 as MinIO S3
    participant Z as Zammad

    U->>API: POST attachments then messages
    API->>G: Invoke with active_ticket_number set
    G->>Conv: Short-circuit no LLM call
    Conv-->>G: AddAttachment StructuredIntent
    G->>Orch: Validate and map command
    Orch-->>G: Approved ADD_ATTACHMENT
    G->>TT: Execute
    TT->>S3: Load attachment bytes
    TT->>Z: POST ticket article with attachment
    Z-->>TT: OK
    TT-->>G: Confirmation
    G-->>API: Assistant reply
    API-->>U: Attachment added message
```

**B — New ticket with attachments:** `CreateTicket` intent includes `attachments` in the payload; Zammad receives them on the initial article (see create-ticket flow above).

## LLM provider abstraction

```mermaid
sequenceDiagram
    autonumber
    participant Conv as conversation_node
    participant Factory as llm_factory
    participant GW as LLMGateway
    participant Prov as Provider adapter
    participant Ext as LLM provider

    Conv->>Factory: get_conversation_llm
    Factory->>GW: Resolved by LLM_PROVIDER
    Conv->>GW: propose_intent with history and attachments
    GW->>Prov: Structured output request
    alt openai
        Prov->>Ext: ChatOpenAI plus ConversationAnalysis schema
    else azure_openai
        Prov->>Ext: AzureChatOpenAI plus schema
    else anthropic
        Prov->>Ext: ChatAnthropic plus schema and vision blocks
    else mock GRAPH_LLM_MODE mock
        Prov-->>GW: MockConversationLLM deterministic
    end
    Ext-->>Prov: StructuredIntent fields
    Prov-->>GW: ConversationAnalysis
    GW-->>Conv: Intent and clarify flags
```

| Module | Role |
| ------ | ---- |
| `llm_gateway.py` | `LLMGateway` protocol |
| `llm_settings.py` | `LLMSettings`, `configure_llm()`, `resolved_provider()` |
| `llm_factory.py` | `build_llm_gateway()` |
| `conversation_analysis.py` | Shared prompt, `ConversationAnalysis` schema, intent mapping |
| `providers/*.py` | Provider adapters |
| `attachment_content.py` | Vision blocks (OpenAI `image_url` vs Anthropic base64 `image`) |

| Variable | Effect |
| -------- | ------ |
| `GRAPH_LLM_MODE=mock` | `MockConversationLLM` — no external LLM API |
| `LLM_PROVIDER` | `openai` (default), `azure_openai`, `anthropic` when LLM mode is not `mock` |
| `LLM_TEMPERATURE` | Shared temperature (default `0.2`) |

Settings applied at API startup in `main.py` lifespan via `configure_llm()`.

## Ticketing provider abstraction

```mermaid
sequenceDiagram
    autonumber
    participant TT as ticket_tool_node
    participant GW as TicketGateway
    participant Adp as Provider adapter
    participant Map as mapping.yaml
    participant Z as Zammad REST API

    TT->>GW: build_ticket_gateway
    TT->>GW: execute TicketCommand
    GW->>Adp: Provider-specific mapping
    Adp->>Map: Category to group and priority IDs
    Map-->>Adp: Resolved IDs
    alt CREATE_TICKET
        Adp->>Z: POST api v1 tickets
        Z-->>Adp: ProviderTicket
    else SEARCH_TICKETS
        Adp->>Z: GET search tickets
        Z-->>Adp: Matches
    else ADD_ATTACHMENT
        Adp->>Z: POST api v1 ticket_articles with mime-type
        Z-->>Adp: OK
    end
    Adp-->>GW: ProviderTicket result
    GW-->>TT: ui_card and active_ticket_number
```

- `TICKETING_PROVIDER=zammad|servicenow`
- Mapping: `config/providers/{provider}/mapping.yaml`
- Attachments on Zammad articles require `mime-type` (hyphenated); `ZammadClient` uses `model_dump(by_alias=True)`

Orchestration (`packages/orchestration`) is **only** invoked from the `orchestrate` graph node — not from API routes directly (except `scripts/create_ticket.py` CLI).

## Component map

| Layer | Location | Responsibility |
| ----- | -------- | -------------- |
| Web UI | `apps/web` | ChatShell, Composer (📎), MessageStream (Markdown), cards |
| Admin UI | `apps/admin` | Handbook upload/publish/preview (Keycloak) |
| API | `apps/api` | REST/SSE, chat auth, **ChatService**, **AttachmentService**, **KbService**, admin KB routes, graph lifecycle |
| API mock (legacy) | `apps/api/services/mock_graph.py` | `MockSupportGraph` when `GRAPH_ENABLED=false` |
| Agents | `packages/agents` | LangGraph, **LLMGateway**, conversation / troubleshoot / ticket nodes |
| Knowledge | `packages/knowledge` | Ingest, chunking, embeddings, Qdrant/memory store, Docling, handbook storage |
| Orchestration | `packages/orchestration` | `OrchestrationEngine`, policy, workflow, YAML mapping |
| Ticketing | `packages/ticketing` | **TicketGateway**, Zammad/ServiceNow adapters, attachment encoding |
| Storage | `packages/storage` | MinIO/S3 for attachments; shared S3 helpers for handbook backend |
| Zammad client | `packages/zammad-client` | HTTP client, DTOs, retries |
| Shared | `packages/shared` | JSON schemas, reason codes |

## Data stores

### PostgreSQL (source of truth)

| Table | Written by | Purpose |
| ----- | ---------- | ------- |
| `chat_sessions` | ChatService | Session metadata, `active_ticket_number` |
| `chat_messages` | ChatService | User, assistant, system messages; optional `card` and `attachments` JSONB |
| `session_attachments` | AttachmentService | Staged uploads before/after message link |
| `kb_documents` | KbService | Handbook metadata (slug, status, object keys, chunk counts) |
| `kb_ingest_jobs` | KbService | Ingest/publish/reindex job status |
| `kb_deflection_events` | ChatService | Resolved / escalated outcomes after troubleshoot |
| `policy_audit_log` | *(schema only)* | Not wired to chat flow yet |
| `zammad_operations` | *(schema only)* | Used by CLI `create_ticket.py` + AuditService |
| `reason_code_messages` | Seed/migration | Rejection copy catalog |

### Redis (ephemeral acceleration)

| Key | Purpose |
| --- | ------- |
| `session:{id}:context` | `active_ticket_number`, `message_count`, `last_message_at`, `troubleshoot` progress |
| `session:{id}:memory` | Rolling recent turns (max 20) for graph history hydrate |

TTL defaults to 24h (`REDIS_SESSION_TTL_SECONDS`). Loss of Redis does not lose messages — PostgreSQL rebuilds history on next turn.

### Object storage

| Key pattern | Purpose |
| ----------- | ------- |
| `sessions/{session_id}/{attachment_id}/{filename}` | Attachment bytes |

## Attachment pipeline

```mermaid
sequenceDiagram
    autonumber
    participant U as User Composer
    participant API as AttachmentService
    participant S3 as MinIO S3
    participant PG as PostgreSQL
    participant G as LangGraph
    participant TT as ticket_tool
    participant Z as Zammad

    U->>API: POST attachments file
    API->>API: Validate MIME size and count
    API->>S3: put_object under sessions path
    API->>PG: session_attachments pending
    API-->>U: attachment_id

    U->>API: POST messages with attachment_ids
    API->>PG: link_to_message and chat_messages metadata
    API->>G: pending_attachments in graph state

    alt CreateTicket
        G->>TT: CREATE with attachments
        TT->>S3: get_object and base64 encode
        TT->>Z: Initial article with attachments
    else AddAttachment active ticket
        G->>TT: ADD_ATTACHMENT
        TT->>S3: get_object
        TT->>Z: New article on existing ticket
    end
```

| Limit | Default |
| ----- | ------- |
| Max file size | 10 MB |
| Max per message | 5 files |
| Blocked | Executables |

## Admin KB handbook lifecycle

Handbook upload, ingest, and publish are separate from the chat message path. Only **published** documents are retrieved by the troubleshoot node.

```mermaid
sequenceDiagram
    autonumber
    participant A as Admin SPA
    participant KC as Keycloak
    participant API as KbService
    participant S3 as Handbook store
    participant PG as PostgreSQL
    participant Ing as knowledge package
    participant QD as Qdrant

    A->>KC: OIDC login Authorization Code plus PKCE
    KC-->>A: Access token
    A->>API: POST admin kb documents Bearer JWT multipart
    API->>API: Require kb_editor or kb_admin role
    API->>S3: Store source file PDF or Markdown
    API->>PG: kb_documents and kb_ingest_jobs
    API->>Ing: Docling convert then chunk then embed
    Ing->>QD: Upsert vectors
    Ing-->>API: Job complete
    A->>API: POST admin kb documents publish kb_admin
    API->>PG: status published
    Note over API,QD: Chat troubleshoot retrieves published handbooks only
```

## Authentication

| Mode | Behaviour |
| ---- | --------- |
| `dev` | `X-User-Id` header |
| `jwt` | Bearer JWT, `sub` claim *(stub)* |
| OIDC | Planned |

Sessions are user-scoped; cross-user access returns 403.

## Streaming

| Feature | Implementation |
| ------- | -------------- |
| Thought streaming | `POST .../messages/stream` — `SupportGraphRunner.astream_turn` yields `system_statuses` as SSE events |
| Token streaming | Not implemented |

Gated by `THOUGHT_STREAMING_ENABLED`; UI reads `/api/v1/config/public`.

```mermaid
sequenceDiagram
    autonumber
    participant U as Web UI
    participant API as ChatService
    participant G as SupportGraphRunner
    participant PG as PostgreSQL

    U->>API: POST messages stream SSE
    API->>API: Same persist hydrate as REST send
    API->>G: astream_turn
    loop Graph nodes
        G-->>API: system_status event
        API-->>U: SSE status event
    end
    G-->>API: Final turn state
    API->>PG: Persist messages same as REST path
    API-->>U: SSE done with assistant_message and card
```

## Diagnostic endpoint

`POST /api/v1/chat/sessions/{id}/graph/invoke` — runs a graph turn **without persisting** messages (testing). Same `GRAPH_ENABLED` / mock branching as chat.

## Configuration artifacts

| File | Purpose |
| ---- | ------- |
| `config/providers/zammad/mapping.yaml` | Category → group/priority |
| `packages/shared/schemas/*.json` | Intent, command, card contracts |
| `.env` | Secrets and flags |

See [Environment Variables](appendices/B-environment-variables.md).

## Planned enhancements

- Confirm-before-submit interrupt flow
- UpdateTicket, Escalate, Cancel intents
- Policy/provider audit wired to chat message flow
- PDF text extraction for **attachment** context (handbook PDFs already convert via Docling)
- End-user OIDC / SSO for chat (admin Keycloak is available)
- LLM token streaming
- OpenTelemetry

See [Capability Matrix](appendices/C-capability-matrix.md).

## Related documents

- [Functional Specification Summary](02-functional-specification-summary.md)
- [Zammad Integration Guide](05-integration-guide-zammad.md)
- [Security & Data Handling](04-security-and-data-handling.md)
- [API Overview](07-api-overview.md)
