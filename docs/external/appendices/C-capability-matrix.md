# Appendix C — Capability Matrix

Status of **Tech Support AI** features as of the current release. Use this for procurement, UAT scoping, and roadmap discussions.

**Legend:** ✅ Available · 🟡 Partial · 🔲 Planned · ➖ Out of scope (current release)

## User channel

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Web chat | ✅ | React SPA |
| Microsoft Teams | ➖ | Future channel |
| Slack | ➖ | Future channel |
| Mobile app | ➖ | Web responsive only |
| Voice | ➖ | — |

## Conversation

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Multi-turn dialogue | ✅ | Session history in PostgreSQL |
| Session resume | ✅ | List and reopen sessions |
| Clarifying questions | ✅ | Agent-driven intake |
| L1 handbook troubleshoot (KB/RAG) | ✅ | Feature-flagged (`KB_RAG_ENABLED`); one guided step |
| Ticket deflection on resolve | ✅ | No ticket when user confirms fix |
| Mock LLM (offline) | ✅ | `GRAPH_LLM_MODE=mock` |
| OpenAI integration | ✅ | Default `LLM_PROVIDER=openai` |
| Azure OpenAI integration | ✅ | `LLM_PROVIDER=azure_openai` |
| Anthropic Claude integration | ✅ | `LLM_PROVIDER=anthropic` |
| Image / screenshot vision | ✅ | Multimodal in conversation node (all live providers) |
| Token streaming (assistant text) | 🔲 | Thought streaming only today |

## Intents

| Intent | Status | Notes |
| ------ | ------ | ----- |
| CreateTicket | ✅ | E2E with Zammad |
| CheckStatus | ✅ | Search + status card |
| UpdateTicket | 🔲 | Schema defined |
| AddAttachment | ✅ | New ticket + active ticket via Zammad article |
| EscalateIssue | 🔲 | — |
| CancelTicket | 🔲 | — |

## Orchestration & policy

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| JSON schema validation | ✅ | Shared schemas |
| Required field checks | ✅ | PolicyValidator |
| Category → group mapping | ✅ | YAML per provider |
| Confidence threshold | ✅ | Configurable rejection |
| Reason code catalog | ✅ | User-facing messages |
| Confirm-before-submit | 🔲 | Interrupt flow planned |
| Access control per ticket | 🔲 | Planned |

## Help desk integration

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Zammad create ticket | ✅ | Via TicketGateway |
| Zammad search / status | ✅ | CheckStatus intent |
| Provider abstraction | ✅ | `packages/ticketing` |
| ServiceNow adapter | 🟡 | Registered stub only |
| Attachment upload to ticket | ✅ | MinIO/S3 → Zammad article |
| Comment / update ticket | 🔲 | — |

## API

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| REST chat API | ✅ | `/api/v1/chat/*` |
| Health live / ready | ✅ | `/health/*` |
| Public feature config | ✅ | Thought streaming flag |
| Thought streaming (SSE) | ✅ | Configurable |
| OpenAPI docs | ✅ | `/docs` |
| Attachment upload API | ✅ | `POST .../attachments` |
| Admin KB API | ✅ | `/api/v1/admin/kb/*` (Keycloak Bearer) |
| Graph invoke (test) | ✅ | `POST /api/v1/chat/sessions/{id}/graph/invoke` |

## Web UI

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Message stream | ✅ | User + assistant |
| Assistant Markdown rendering | ✅ | Lists, bold in chat replies |
| Ticket created card | ✅ | `ticket_created` |
| Ticket status card | ✅ | `ticket_status` |
| Context strip (active ticket) | ✅ | — |
| Processing status line | ✅ | `system_statuses` |
| Thought stream panel | ✅ | When enabled |
| Summary confirm card | 🔲 | `ticket_summary` scaffolded |
| File upload in composer | ✅ | 📎 upload + chips |
| Screenshot vision intake | ✅ | OpenAI reads on-screen errors |
| Admin SPA (handbooks) | ✅ | Separate app (`apps/admin`); upload / publish |

## Knowledge / RAG

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Qdrant vector retrieval | ✅ | Published handbooks only |
| Docling PDF → Markdown | ✅ | Handbook ingest |
| Handbook object storage | ✅ | Ceph RGW / S3-compatible; `memory` for local |
| Chunk + embed pipeline | ✅ | `packages/knowledge` |
| Search preview (admin) | ✅ | Does not affect live chat |
| Transcript on escalate | ✅ | Configurable (`KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET`) |

## Data & audit

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| PostgreSQL message store | ✅ | Durable |
| Redis session cache | ✅ | TTL-based |
| Object storage (attachments) | ✅ | MinIO/S3 |
| KB document metadata | ✅ | `kb_documents`, ingest jobs, deflection events |
| Policy audit table | 🟡 | Schema ready; chat wiring planned |
| Provider operation audit | 🟡 | Schema ready; chat wiring planned |
| Retention automation | 🔲 | Organizational process |

## Security & auth

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Dev header auth | ✅ | `X-User-Id` (chat only) |
| JWT auth | 🟡 | Stub for chat (`AUTH_MODE=jwt`) |
| Keycloak OIDC (admin) | ✅ | `kb_editor` / `kb_admin` roles |
| End-user OIDC / SSO | 🔲 | Production target for chat |
| Server-side secrets only | ✅ | No tokens in browser |
| CORS configuration | ✅ | Environment-driven |

## Operations

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Docker Compose | ✅ | Dev / demo |
| Database migrations | ✅ | Alembic |
| Structured logging | ✅ | structlog |
| OpenTelemetry | 🔲 | Planned |
| Kubernetes manifests | 🔲 | Target deployment |

## Testing

| Capability | Status | Notes |
| ---------- | ------ | ----- |
| Unit tests (packages) | ✅ | pytest |
| API integration tests | ✅ | — |
| Live Zammad integration tests | ✅ | `make test-live` |
| Browser E2E (mock) | ✅ | `make e2e` (Vite on `:5175` by default) |
| Live UI integration | ✅ | `make test-live-ui` (real OpenAI + Zammad) |
| Postman collection | ✅ | `docs/postman/` |

## Roadmap summary

**Near term:** confirm-before-submit, audit wiring, UpdateTicket / Escalate / Cancel, end-user OIDC for chat.

**Medium term:** PDF text extraction for attachment context, ServiceNow adapter, production observability.

**Long term:** additional channels (Teams/Slack).

## Related documents

- [Executive Solution Overview](../01-executive-solution-overview.md)
- [Test & Acceptance](../09-test-and-acceptance.md)
