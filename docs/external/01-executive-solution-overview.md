# Executive Solution Overview

## What is Tech Support AI?

**Tech Support AI** is an enterprise web chat assistant that helps employees report IT issues and manage support tickets through natural conversation. The solution integrates with **Zammad** (and other help desk platforms via a pluggable adapter) while keeping business rules deterministic and auditable.

Employees describe problems in plain language. An AI agent gathers details, proposes structured actions, and a **policy orchestration layer** validates every ticket operation before it reaches the help desk.

## Business value

| Objective | How the solution delivers |
| --------- | ------------------------- |
| Reduce manual intake effort | Conversational intake replaces static forms for common requests |
| Improve ticket quality | Structured extraction + workflow mapping for category, group, and priority |
| 24/7 availability | Web chat and AI intake available outside support hours |
| Faster time-to-ticket | Multi-turn dialogue collects required fields before submission |
| Enterprise control | Orchestration gates every help desk API call; ticket numbers come only from the provider |

## How it works (high level)

```text
Employee (web chat)
    → FastAPI (ChatService — persistence, attachments)
    → LangGraph workflow (when GRAPH_ENABLED=true)
        → conversation node (LLMGateway)
        → troubleshoot node (optional; KB/RAG when KB_RAG_ENABLED=true)
        → orchestrate node (policy + workflow — no LLM)
        → ticket_tool node (TicketGateway → Zammad)
        → respond node
    → Assistant reply + ticket card in chat
```

When `GRAPH_ENABLED=false`, the API uses a legacy rule-based mock graph instead — no LangGraph and no live tickets.

**Design principle:** the language model runs in the `conversation` node (intent/slots) and in `troubleshoot` for classic RAG presentation of retrieved handbook chunks. Retrieval, citation validation, category mapping, policy approval, and ticket execution remain deterministic. The end user never sees handbook titles or that a knowledge base was consulted.

## Scope

### In scope (current release target)

- Web chat as the user channel
- Conversational intake and ticket operations
- Zammad integration via REST API
- Create ticket and check ticket status (search)
- **L1 handbook troubleshoot (KB/RAG)** — optional guided self-help before ticket creation (`KB_RAG_ENABLED`)
- **Admin handbook UI** — separate SPA with Keycloak login to upload, publish, and preview Agent Handbooks
- File attachments on new and active tickets (MinIO/S3 → Zammad)
- Screenshot vision intake for error codes and on-screen text (LLM vision)
- Pluggable LLM provider abstraction (OpenAI default; Azure OpenAI, Anthropic)
- Multi-turn conversation with session history
- Optional live “processing” feedback in the UI (thought streaming)
- Pluggable ticketing provider abstraction (Zammad live; ServiceNow stub)

### Out of scope (current release)

- Microsoft Teams, Slack, mobile apps, WhatsApp
- Voice assistant
- In-chat human agent handoff
- Self-service **policy** administration UI (ticket mapping remains YAML + environment)

## Capability snapshot

| Capability | Status |
| ---------- | ------ |
| Web chat with session resume | Available |
| Create support ticket end-to-end | Available |
| Check ticket status (search) | Available |
| L1 handbook troubleshoot (KB/RAG) | Available (`KB_RAG_ENABLED`) |
| Admin KB (upload / publish handbooks) | Available (Keycloak) — core module |
| Multi-turn intake with history | Available |
| Thought streaming (processing panel) | Available (configurable) |
| Update ticket, escalate, cancel | Planned |
| File attachments (upload → Zammad) | Available |
| Screenshot / image vision intake | Available (LLM multimodal) |
| Multi-provider LLM | Available (OpenAI, Azure OpenAI, Anthropic) |
| Confirm-before-submit summary card | Planned |
| Enterprise SSO for end-user chat | Planned |

See [Capability Matrix](appendices/C-capability-matrix.md) for detail.

## Technology summary

| Layer | Technology |
| ----- | ---------- |
| Web UI | React 18, TypeScript, Vite (`apps/web`) |
| Admin UI | React SPA (`apps/admin`) — handbook maintenance |
| API | Python 3.12+, FastAPI |
| AI runtime | LangGraph, LLMGateway (OpenAI / Azure OpenAI / Anthropic) |
| Knowledge / RAG | Qdrant, embeddings, Docling (PDF→Markdown), `packages/knowledge` |
| Orchestration | Python policy engine + YAML mapping |
| Durable data | PostgreSQL 16 |
| Session cache | Redis 7 |
| Object storage | MinIO (attachments); Ceph RGW or S3-compatible for handbooks (Compose may use MinIO with a dedicated handbook bucket) |
| Admin auth | Keycloak (OIDC) — admin API and admin SPA only |
| Help desk | Zammad REST API (primary) |
| Containers | Docker Compose (dev); Kubernetes (production target) |

## Integration model

- **Not MCP-based.** Zammad is accessed through a native HTTP client and provider gateway — not Model Context Protocol.
- **Provider abstraction.** `TICKETING_PROVIDER` selects the adapter (`zammad` today; `servicenow` registered as stub).
- **Field mapping.** Groups, priorities, and categories are configured in YAML per provider — no secrets in configuration files.

## Security posture (summary)

- Help desk API tokens are server-side only — never exposed to the browser
- User identity required on every API request (dev header or JWT)
- Orchestration prevents the LLM from calling Zammad directly
- Audit tables designed for policy and provider operation logging
- See [Security & Data Handling](04-security-and-data-handling.md) for full detail

## Typical deployment

| Environment | Pattern |
| ----------- | ------- |
| Evaluation | Docker Compose + mock LLM (no external credentials) |
| Sandbox / UAT | Docker or host-run API + Zammad sandbox + OpenAI |
| Production | Container orchestration, managed Postgres/Redis, secrets manager, OIDC |

## Documentation map

| Need | Start here |
| ---- | ---------- |
| Run it locally | [Quick Start](00-quick-start.md) |
| Architecture detail | [Solution Architecture](03-solution-architecture.md) |
| Connect Zammad | [Zammad Integration Guide](05-integration-guide-zammad.md) |
| Deploy and operate | [Deployment & Operations](06-deployment-and-operations.md) |
| API integration | [API Overview](07-api-overview.md) |
| UAT / acceptance | [Test & Acceptance](09-test-and-acceptance.md) |

## Document control

| Item | Detail |
| ---- | ------ |
| **Audience** | Executives, sponsors, procurement, product leadership |
| **Classification** | External |
