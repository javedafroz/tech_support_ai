# API Overview

This document describes the **Tech Support AI** REST API for integrators and developers. Interactive documentation is available at `/docs` when the API is running.

**Base URL (local):** `http://localhost:8000`

**API prefix:** `/api/v1`

## Authentication

Chat and admin APIs use **different** identity mechanisms.

### Chat API (`/api/v1/chat/*`, graph invoke)

Controlled by `AUTH_MODE`.

#### Development mode (`AUTH_MODE=dev`)

Send the configured header with a user identifier:

```http
X-User-Id: alice@company.com
```

#### JWT mode (`AUTH_MODE=jwt`)

```http
Authorization: Bearer <jwt>
```

The token must include a `sub` claim used as the user ID.

### Admin KB API (`/api/v1/admin/kb/*`)

Requires a **Keycloak** access token. Chat-style `X-User-Id` is **not** accepted.

```http
Authorization: Bearer <keycloak-access-token>
```

| Role | Capabilities |
| ---- | ------------ |
| `kb_editor` | List, upload, edit, reindex, markdown preview, search preview |
| `kb_admin` | Everything above, plus publish and delete |

## Health endpoints

No authentication required.

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/health/live` | Process is running |
| `GET` | `/health/ready` | Dependencies available |

**Example:**

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Public configuration

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/config/public` | Feature flags for the web UI |

**Response:**

```json
{
  "thought_streaming_enabled": false
}
```

## Chat sessions

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/chat/sessions` | List recent sessions for user |
| `POST` | `/api/v1/chat/sessions` | Create session |
| `GET` | `/api/v1/chat/sessions/{session_id}` | Get session metadata |
| `GET` | `/api/v1/chat/sessions/{session_id}/context` | Redis session context |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | Paginated message history |

### Create session

```http
POST /api/v1/chat/sessions
X-User-Id: alice@company.com
Content-Type: application/json

{}
```

Optional body:

```json
{
  "org_id": "acme-corp"
}
```

**Response (201):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "alice@company.com",
  "org_id": null,
  "status": "active",
  "active_ticket_number": null,
  "created_at": "2026-06-02T10:00:00Z",
  "updated_at": "2026-06-02T10:00:00Z"
}
```

### List messages

```http
GET /api/v1/chat/sessions/{session_id}/messages?limit=100&offset=0
X-User-Id: alice@company.com
```

Messages include optional `card` JSON for rich UI elements (ticket created, status, etc.) and optional `attachments` metadata on user messages.

## Attachments

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/chat/sessions/{session_id}/attachments` | Upload a file (multipart form) |
| `GET` | `/api/v1/chat/sessions/{session_id}/attachments` | List staged attachments for session |

### Upload attachment

```http
POST /api/v1/chat/sessions/{session_id}/attachments
X-User-Id: alice@company.com
Content-Type: multipart/form-data

file=<binary>
```

**Response (201):**

```json
{
  "id": "a1b2c3d4-...",
  "session_id": "...",
  "filename": "blue.png",
  "mime_type": "image/png",
  "size_bytes": 48231,
  "status": "pending",
  "created_at": "..."
}
```

Use the returned `id` when sending a message.

## Send message

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages` | Send message (synchronous response) |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages/stream` | Send message with SSE thought streaming |

### Synchronous message

```http
POST /api/v1/chat/sessions/{session_id}/messages
X-User-Id: alice@company.com
Content-Type: application/json

{
  "content": "My VPN won't connect since this morning.",
  "attachment_ids": ["a1b2c3d4-..."]
}
```

**Response (201):**

```json
{
  "user_message": {
    "id": "...",
    "session_id": "...",
    "role": "user",
    "content": "My VPN won't connect since this morning.",
    "card": null,
    "created_at": "..."
  },
  "assistant_message": {
    "id": "...",
    "role": "assistant",
    "content": "I've created ticket #22042 for your VPN issue.",
    "card": {
      "card_type": "ticket_created",
      "ticket_number": "22042",
      "group": "IT Support",
      "priority": "2 normal",
      "state": "new"
    },
    "created_at": "..."
  },
  "system_statuses": ["Understanding your request", "Creating ticket"],
  "detected_intent": "CreateTicket"
}
```

| Field | Description |
| ----- | ----------- |
| `system_statuses` | Processing labels shown in UI during graph execution |
| `detected_intent` | Orchestration-detected intent name (informational) |
| `assistant_message.card` | Structured UI card when applicable |
| `attachment_ids` | Optional request field — staged attachment UUIDs from upload endpoint |

### Thought streaming (SSE)

Available when `THOUGHT_STREAMING_ENABLED=true`.

```http
POST /api/v1/chat/sessions/{session_id}/messages/stream
X-User-Id: alice@company.com
Content-Type: application/json

{
  "content": "What's the status of ticket 22042?"
}
```

**Response:** `text/event-stream`

Events are JSON objects in SSE `data:` lines. Types include processing step labels and the final message payload. See `packages/shared/schemas/stream-event.json`.

Returns `404` when thought streaming is disabled.

## Graph invoke (advanced)

Direct graph invocation for testing and diagnostics:

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/chat/sessions/{session_id}/graph/invoke` | Invoke LangGraph with a message |

Typically used by integration tests rather than production clients. Production clients should use the chat message endpoints.

## Admin KB API

Handbook management for L1 troubleshoot. Prefix: `/api/v1/admin/kb`. Interactive docs: `/docs` (tag `admin-kb`).

| Method | Path | Role | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/me` | `kb_editor` | Current principal, roles, edit/publish flags |
| `GET` | `/documents` | `kb_editor` | List handbooks |
| `POST` | `/documents` | `kb_editor` | Upload (multipart); triggers ingest |
| `GET` | `/documents/{id}` | `kb_editor` | Get document metadata |
| `PATCH` | `/documents/{id}` | `kb_editor` | Update title, tags, status |
| `POST` | `/documents/{id}/publish` | `kb_admin` | Publish for chat retrieval |
| `POST` | `/documents/{id}/reindex` | `kb_editor` | Re-run chunk/embed |
| `DELETE` | `/documents/{id}` | `kb_admin` | Delete handbook |
| `GET` | `/documents/{id}/markdown` | `kb_editor` | Markdown preview |
| `GET` | `/jobs/{job_id}` | `kb_editor` | Ingest job status |
| `POST` | `/search/preview` | `kb_editor` | Retrieval preview (does not affect chat) |

**Notes:**

- Only **published** documents are retrieved by the chat troubleshoot node.
- Prefer the Admin SPA (`make admin` → http://localhost:5174) for day-to-day handbook ops.
- Local seed: `make seed-kb` (ingests `config/knowledge/*.md` and publishes).

## Message roles

| Role | Description |
| ---- | ----------- |
| `user` | End-user message |
| `assistant` | AI reply (may include `card`) |
| `system` | System notices *(when used)* |

## UI card types

Defined in `packages/shared/schemas/cards.json`:

| `card_type` | Purpose |
| ----------- | ------- |
| `ticket_created` | New ticket confirmation with number, group, priority, state |
| `ticket_status` | Status lookup result |
| `ticket_summary` | Pre-submit summary *(planned for confirm flow)* |

## Error responses

Standard HTTP status codes:

| Code | Meaning |
| ---- | ------- |
| `400` | Invalid request body |
| `401` | Missing or invalid authentication |
| `403` | Session not owned by user |
| `404` | Session not found; streaming disabled |
| `422` | Validation error |
| `500` | Internal server error |

**Example:**

```json
{
  "detail": "Session not found"
}
```

## Rate and size limits

| Limit | Value |
| ----- | ----- |
| Message content | 1–16,000 characters |
| Session list | 1–50 per request |
| Message list | 1–500 per request |
| Attachment size | 10 MB per file (default) |
| Attachments per message | 5 (default) |

## CORS

The API allows configured origins (`CORS_ORIGINS` in environment). The web SPA uses the API base URL or Vite dev proxy.

## Postman collection

Import the [Postman Collection](../postman.md) for ready-made requests.

## Integration patterns

### Embed in intranet

1. Host the web SPA or build a thin client
2. Pass user identity via `X-User-Id` (dev) or JWT (production)
3. Create session on first visit; persist `session_id` in local storage
4. Poll or stream messages via chat endpoints

### Custom channel (future)

Additional channels (Teams, Slack) would call the same chat API with authenticated user context — no direct Zammad access from the channel bot.

## Related documents

- [Quick Start](00-quick-start.md)
- [Security & Data Handling](04-security-and-data-handling.md)
- [UI/UX Overview](08-ui-ux-overview.md)
