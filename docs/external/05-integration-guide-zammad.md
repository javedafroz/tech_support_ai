# Zammad Integration Guide

This guide explains how to connect **Tech Support AI** to a **Zammad** instance for ticket create and search operations.

## Prerequisites

| Requirement | Detail |
| ----------- | ------ |
| Zammad instance | v5+ with REST API enabled |
| API token | User token with permission to create and search tickets |
| Network | API server can reach Zammad base URL (HTTPS recommended) |
| Mapping file | `config/providers/zammad/mapping.yaml` configured for your groups |

## Architecture

```text
ticket_tool (LangGraph)
    → TicketGateway
        → ZammadAdapter
            → ZammadClient (httpx)
                → Zammad REST API
```

The web UI and LLM **never** contact Zammad directly.

## Environment variables

Set these in `.env` or your secrets manager:

```bash
TICKETING_PROVIDER=zammad
ZAMMAD_BASE_URL=https://your-zammad.example.com
ZAMMAD_API_TOKEN=your-api-token-here
```

Optional:

```bash
ZAMMAD_VERIFY_SSL=true          # set false only for local dev with self-signed certs
ZAMMAD_TIMEOUT_SECONDS=30
```

See [Environment Variables](appendices/B-environment-variables.md) for the full list.

## Zammad API token

1. Log in to Zammad as an integration user (dedicated service account recommended).
2. Go to **Profile → Token Access**.
3. Create a token with permissions for:
   - Ticket create
   - Ticket search / read
4. Copy the token into `ZAMMAD_API_TOKEN` — never commit it to source control.

### Recommended Zammad user permissions

| Permission | Why |
| ---------- | --- |
| `ticket.agent` or appropriate role | Create and search tickets |
| Limited to required groups | Reduces blast radius |

Use a **dedicated integration user**, not a personal admin account.

## Field mapping

Workflow mapping translates conversational categories into Zammad group and priority IDs.

**File:** `config/providers/zammad/mapping.yaml`

Example structure:

```yaml
default_group_id: 1
default_priority_id: 2

categories:
  vpn:
    group_id: 3
    priority_id: 2
    keywords: ["vpn", "remote access", "forticlient"]
  hardware:
    group_id: 4
    priority_id: 3
    keywords: ["laptop", "monitor", "keyboard"]
```

### Finding Zammad IDs

| Entity | How to find ID |
| ------ | -------------- |
| Group | Zammad Admin → Groups → note ID in URL or API `GET /api/v1/groups` |
| Priority | Admin → Priorities → `GET /api/v1/ticket_priorities` |
| State | Usually mapped automatically; custom states via API |

After changing mapping, restart the API process to reload configuration.

## Ticket create flow

When orchestration approves a `CreateTicket` intent:

1. `WorkflowEngine` resolves category → `group_id`, `priority_id`
2. `ZammadAdapter` maps to Zammad ticket payload:
   - `title`, `group`, `priority`, `customer_id` or customer email
   - Article body from user description
   - Optional `attachments[]` on the article (base64-encoded from object storage)
3. `POST /api/v1/tickets` creates the ticket
4. Response ticket number is returned to the chat UI

## Attachment flow

Attachments never go directly from the browser to Zammad. The pipeline is:

```text
Web upload → MinIO/S3 → PostgreSQL (session_attachments)
    → LangGraph (vision / metadata)
    → encode_attachments_for_zammad
    → ZammadAdapter → POST /api/v1/tickets or /api/v1/ticket_articles
```

### Zammad attachment payload

Each attachment on a ticket article must include:

| Field | Description |
| ----- | ----------- |
| `filename` | Original file name |
| `data` | Base64-encoded file bytes |
| `mime-type` | MIME type (hyphenated — Zammad API requirement) |

The `ZammadClient` serializes with `by_alias=True` so `mime-type` is sent correctly. A missing or incorrectly named field produces:

```text
Attachment needs 'mime-type' param for attachment with index '0'
```

### Add attachment to existing ticket

When the chat session has an active ticket and the user sends new files:

1. Orchestration builds an `AddAttachment` command
2. Adapter searches for the ticket by number
3. `POST /api/v1/ticket_articles` adds a note article with attachments

### Customer identity

Zammad requires a customer on each ticket. The workflow uses:

- Email from structured intent (`customer_email`), or
- Fallback behavior defined in orchestration mapping

Ensure test users exist in Zammad or that auto-create is enabled per your Zammad configuration.

## Ticket search flow (CheckStatus)

When orchestration approves a `CheckStatus` intent:

1. Search query built from ticket number or user-provided keywords
2. `GET /api/v1/tickets/search?query=...` (via adapter)
3. Results normalized to `ProviderTicket` objects
4. UI shows status card for single match; disambiguation for multiple matches

## Health check

Verify connectivity:

```bash
curl -s "${ZAMMAD_BASE_URL}/api/v1/groups" \
  -H "Authorization: Token token=${ZAMMAD_API_TOKEN}"
```

The API also exposes:

```bash
GET /health/ready
```

Readiness includes dependency checks when configured.

## Docker Compose notes

When running via `docker compose`:

- Set `ZAMMAD_BASE_URL` to a URL reachable **from inside the API container**
  - Use `host.docker.internal` for Zammad on the host machine (macOS/Windows)
  - Use service name if Zammad is in the same compose network
- Mount or bake `config/providers/zammad/mapping.yaml` into the image

## Troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| `401 Unauthorized` | Invalid or expired token | Regenerate token; check `ZAMMAD_API_TOKEN` |
| `Connection refused` | Wrong base URL from container | Fix network / use correct hostname |
| Ticket created in wrong group | Mapping mismatch | Update `mapping.yaml` category → group_id |
| `customer email invalid` | User not in Zammad | Create customer or adjust email field |
| `Attachment needs 'mime-type' param` | Wrong JSON field name on create | Ensure API uses current `ZammadClient` (`by_alias=True` on create) |
| Attachment upload fails | MinIO/S3 not running or misconfigured | Start MinIO; verify `S3_*` env vars |
| Assistant ignores screenshot | Mock LLM or non-vision model | Use `GRAPH_LLM_MODE=openai` and `gpt-4o-mini` or `gpt-4o` |
| SSL errors | Self-signed cert | `ZAMMAD_VERIFY_SSL=false` (dev only) |

## Switching providers

To register a different help desk later:

```bash
TICKETING_PROVIDER=servicenow   # stub today — returns NOT_IMPLEMENTED
```

Zammad remains the production-supported provider. See internal `docs/provider-abstraction-strategy.md` for adapter development.

## Testing without Zammad

Use mock mode for UI and orchestration testing without live Zammad:

```bash
GRAPH_LLM_MODE=mock
# Omit or leave blank ZAMMAD_API_TOKEN for paths that don't hit ticket_tool
```

For full E2E with Zammad, use a sandbox instance and dedicated test groups.

## Related documents

- [Quick Start](00-quick-start.md)
- [Deployment & Operations](06-deployment-and-operations.md)
- [Solution Architecture](03-solution-architecture.md)
