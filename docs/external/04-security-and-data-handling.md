# Security & Data Handling

This document describes how **Tech Support AI** protects data, credentials, and user identity. It is intended for security reviewers, compliance stakeholders, and operations teams.

## Security model summary

| Principle | Implementation |
| --------- | -------------- |
| Least privilege | Help desk API tokens are server-side only |
| Separation of concerns | LLM never calls help desk APIs directly |
| Identity on every request | User ID required via header or JWT |
| Auditability | Database tables for policy and provider operations |
| No secrets in config files | YAML mapping contains IDs only; tokens in environment |

## Trust boundaries

```text
┌─────────────────────────────────────────────────────────────┐
│  Untrusted: Browser (chat SPA + admin SPA)                   │
│  - No Zammad tokens                                          │
│  - No OpenAI keys                                            │
│  - Chat: session ID + user identity                          │
│  - Admin: Keycloak access token (Bearer) only                │
│  - Attachment bytes uploaded to API (not directly to Zammad) │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────┐
│  Trusted: API + agent runtime (FastAPI, LangGraph)             │
│  - Validates chat identity / admin JWT                       │
│  - Holds provider, LLM, and handbook storage credentials     │
│  - Orchestration gates all ticket operations                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ TLS (recommended)
┌──────────────────────────▼──────────────────────────────────┐
│  External: Zammad, OpenAI, PostgreSQL, Redis, MinIO/S3 (attachments +     │
│            optional local handbook bucket), Qdrant, Keycloak,             │
│            Ceph RGW (production handbooks)                                │
└─────────────────────────────────────────────────────────────┘
```

Handbook bytes use `CEPH_RGW_*` / `KB_HANDBOOK_*` credentials (not chat `X-User-Id`). Local Compose may point those vars at MinIO with a dedicated `agent-handbooks` bucket — production should use Ceph RGW or equivalent, separate from attachment storage.

## Authentication

### Chat API (`/api/v1/chat/*`)

| Mode | Mechanism | Use case |
| ---- | --------- | -------- |
| Development | `X-User-Id` request header | Local and sandbox testing |
| JWT stub | `Authorization: Bearer <token>` with `sub` claim | Integration testing |
| OIDC / SSO for end users | Planned | Production target |

Every chat endpoint requires a resolvable user identity. Anonymous access is not supported for ticket operations.

### Admin KB API (`/api/v1/admin/kb/*`)

| Mechanism | Detail |
| --------- | ------ |
| Keycloak OIDC | Authorization Code + PKCE in Admin SPA; API validates Bearer JWT via JWKS |
| Roles | `kb_editor` (upload/edit/reindex); `kb_admin` (publish/delete) |
| Rejected | Chat-style `X-User-Id` headers — admin routes require a valid Keycloak token |

Local realm import: `config/keycloak/tech-support-realm.json` (seed users for evaluation only).

### Session ownership

- Chat sessions are scoped to the authenticated user ID.
- API rejects access to sessions belonging to another user.

## Credential handling

| Secret | Storage | Exposure |
| ------ | ------- | -------- |
| `ZAMMAD_API_TOKEN` | Environment / secrets manager | API process only |
| `OPENAI_API_KEY` | Environment / secrets manager | API process only |
| `DATABASE_URL` | Environment | API process only |
| `REDIS_URL` | Environment | API process only |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Environment | API process only (attachments) |
| `CEPH_RGW_ACCESS_KEY` / `CEPH_RGW_SECRET_KEY` | Environment | API process only (handbooks) |
| `QDRANT_API_KEY` | Environment (optional) | API process only |

**Never** commit `.env` files or paste tokens into chat logs, mapping YAML, or client-side code.

### Chat transcript on tickets

When troubleshoot escalates to CreateTicket, the ticket body may include the full chat transcript. Control with `KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET` (default `true`). Treat ticket descriptions as containing potential PII accordingly.

## Attachments

| Control | Implementation |
| ------- | -------------- |
| Upload path | Browser → API only; API writes to MinIO/S3 |
| Type allowlist | MIME validation in `AttachmentService`; executables blocked |
| Size limits | 10 MB per file, 5 per message (configurable) |
| Zammad transfer | Server-side base64 encoding; no presigned browser URLs to Zammad |
| Vision | Image bytes sent to OpenAI when `GRAPH_LLM_MODE=openai` — review data-processing policy |

Attachment content may include screenshots with sensitive error details or PII visible on screen.

## Data classification

| Data type | Examples | Handling |
| --------- | -------- | -------- |
| User messages | Issue descriptions, emails, attachment filenames | Stored in PostgreSQL; may contain PII |
| Attachment files | Screenshots, logs, documents | Stored in MinIO/S3; may be sent to OpenAI for vision |
| Agent Handbooks | Markdown/PDF source, chunks, embeddings | Ceph RGW (or S3-compatible) + Qdrant; metadata in PostgreSQL |
| Structured intents | Category, priority, title | Stored in message metadata; used for orchestration |
| Ticket data | Numbers, states from Zammad | Returned to user; cached in session context |
| Audit logs | Policy decisions, API calls | PostgreSQL; operator access only |
| LLM prompts | System + conversation context; image bytes for vision | Sent to OpenAI when not in mock mode |

Organizations should treat chat content as **internal/confidential** and align retention with corporate policy.

## Orchestration as security control

The orchestration layer is a **control plane**, not a convenience layer:

1. Validates structured intent against JSON schema
2. Enforces required fields and confidence thresholds
3. Maps categories to allowed groups and priorities
4. Emits neutral `TicketCommand` objects for the gateway
5. On rejection, returns a reason code — **no provider API call**

This prevents prompt injection or model hallucination from creating unauthorized tickets.

## Provider API access

- All Zammad calls go through `ZammadClient` → `ZammadAdapter` → `TicketGateway`.
- Retries and timeouts are centralized in the HTTP client.
- Ticket numbers displayed to users originate from provider responses only.

## Transport security

| Segment | Recommendation |
| ------- | -------------- |
| Browser ↔ API | HTTPS in all non-local environments |
| API ↔ Zammad | HTTPS; verify TLS in production |
| API ↔ OpenAI | HTTPS (provider default) |
| API ↔ Qdrant / Keycloak / handbook storage | TLS in production; private network |
| API ↔ Postgres / Redis | TLS in production; private network |

## Logging and observability

| Logged | Not logged (target) |
| ------ | ------------------- |
| Request IDs, session IDs | Full API tokens |
| Orchestration decisions | Raw JWT secrets |
| Provider HTTP status / errors | Complete user message bodies in production *(configurable)* |

Structured logging via `structlog` is used in the API layer. Production deployments should configure log redaction and centralized aggregation.

## Data retention

| Store | Default behavior | Notes |
| ----- | ---------------- | ----- |
| PostgreSQL messages | Durable until deleted | Define retention policy per organization |
| Redis session cache | TTL ~24 hours | Ephemeral; not authoritative |
| Object storage (attachments) | Durable until deleted | Align with message retention policy |
| Handbook storage + Qdrant | Durable until deleted / reindexed | Align with content governance |
| Audit tables | Durable | Support compliance review |

Retention policies are **not** auto-enforced in the application today — operators should define backup and purge procedures.

## Compliance considerations

| Topic | Current state |
| ----- | ------------- |
| GDPR / data subject access | Chat messages in DB; export/delete procedures are organizational |
| SOC 2 | Depends on hosting and operational controls |
| AI data processing | OpenAI API usage when not in mock mode — review OpenAI enterprise terms |
| EU data residency | Configure OpenAI and hosting region per policy |

## Hardening checklist (production)

- [ ] Enable HTTPS termination at load balancer or ingress
- [ ] Store secrets in a vault or cloud secrets manager
- [ ] Implement OIDC / enterprise SSO
- [ ] Restrict CORS to known web origins
- [ ] Enable database and Redis TLS
- [ ] Configure log redaction for PII and tokens
- [ ] Network isolate API from public internet except through gateway
- [ ] Rotate Zammad API tokens on schedule
- [ ] Review Zammad role permissions for the integration user

## Incident response

| Scenario | Response |
| -------- | -------- |
| Leaked API token | Revoke in Zammad; rotate `ZAMMAD_API_TOKEN`; review audit logs |
| Unauthorized session access | Verify auth middleware; check session ownership checks |
| Erroneous ticket creation | Trace `policy_audit_log` and `zammad_operations` *(when wired)* |

## Related documents

- [Deployment & Operations](06-deployment-and-operations.md)
- [Environment Variables](appendices/B-environment-variables.md)
- [API Overview](07-api-overview.md)
