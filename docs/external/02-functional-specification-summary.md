# Functional Specification Summary

This document summarizes the functional requirements for **Tech Support AI**. It is derived from the full functional specification and intended for external stakeholders.

## Purpose

Enable users to interact with an AI-powered web chat assistant to:

- Receive optional guided self-help from Agent Handbooks (KB/RAG) before a ticket is created
- Create support tickets
- Check ticket status
- Update existing tickets *(planned)*
- Add comments or attachments
- Escalate issues *(planned)*
- Cancel or close tickets *(planned)*

All ticket operations integrate with the organization's help desk platform (**Zammad** in the primary deployment). Handbook content is maintained in a separate **Admin** application.

## Actors

| Actor | Role |
| ----- | ---- |
| **End user** | Employee or customer reporting or following up on issues |
| **Conversation agent** | AI layer — understands language, asks questions, proposes structured intents |
| **Troubleshoot layer** | Classic RAG: deterministic retrieval + grounded LLM guidance (citation-validated) |
| **Orchestration layer** | Policy and workflow engine — approves or rejects every ticket action |
| **Ticket management** | Executes approved commands against the help desk API |
| **Support engineer** | Works tickets in Zammad (indirect beneficiary of better intake) |
| **KB administrator** | Uploads, publishes, and previews Agent Handbooks (Keycloak-authenticated admin SPA) |
| **Administrator** | Configures mapping, credentials, and policies |

## Supported intents

| Intent | Description | Status |
| ------ | ------------- | ------ |
| `CreateTicket` | Report a new issue; gather title, description, category, priority | **Available** |
| `CheckStatus` | Look up an existing ticket by number or search | **Available** |
| `UpdateTicket` | Add information or comment to an existing ticket | Planned |
| `AddAttachment` | Attach a file to a ticket (new or active) | **Available** |
| `EscalateIssue` | Escalate priority or routing | Planned |
| `CancelTicket` | Request ticket closure | Planned |

## Control flow

Every ticket operation follows the same path:

```text
1. User sends natural language message (web chat), optionally with file attachment(s)
2. Conversation agent analyzes the turn (support-issue signal + optional StructuredIntent)
3. If KB/RAG is enabled and a support issue is detected → troubleshoot (adaptive grounded steps)
4. If troubleshooting resolves the issue → no ticket; on failure/ticket request → escalate immediately to ticket creation
5. Orchestration: PolicyValidator checks schema, required fields, confidence
6. Orchestration: WorkflowEngine maps category → group/priority and builds command
7. If approved → ticket_tool executes against help desk API
8. If rejected → user receives plain-language reason (no API call)
9. Assistant reply and optional UI card (ticket created, status, etc.)
```

**Critical rule:** the LLM never calls the help desk directly. Orchestration must approve every operation. Handbook retrieval and citation validation are deterministic; the LLM only synthesizes user-facing guidance from retrieved sources (not free-form tool calls).

## Use case: L1 handbook troubleshoot

*Requires `KB_RAG_ENABLED=true` and at least one **published** handbook in the vector store.*

### Preconditions

- User can access the web chat
- Knowledge store (Qdrant) is available and handbooks are published
- Issue is a new support problem (not CheckStatus / attachment-only)

### Main flow

1. User describes the issue (e.g. “My computer is running very slow”).
2. Conversation marks `is_support_issue` and a short `problem_summary` (even before full ticket fields are ready).
3. Troubleshoot retrieves matching handbook chunks and asks the configured LLM to synthesize **adaptive** grounded steps (1..`KB_MAX_TROUBLESHOOT_STEPS`) with an empathetic opener (handbook names are **not** shown to the user). Citations are validated against retrieved `source_id`s.
4. **Resolved:** user confirms the guidance worked → assistant deflects; no ticket is created; a deflection event is recorded.
5. **Not resolved / escalate:** user says it did not work (or asks for a ticket) → system **immediately** creates a `CreateTicket` (no second troubleshoot round) with problem details, steps attempted, internal source refs, and optionally the full chat transcript (ticket text may name the handbook for **agents**; chat UI still does not).
6. If retrieval/generation cannot produce grounded guidance → normal clarify-then-CreateTicket flow (unchanged).

### Postconditions

- Either the issue is deflected (no ticket) or a ticket exists with troubleshooting context for the support engineer
- End-user chat copy does not mention “handbook”, “guide title”, or knowledge-base internals (ticket body enrichment is server-side only)

## Use case: Create support ticket

### Preconditions

- User can access the web chat
- Help desk API is available and configured
- Required intake fields can be collected conversationally

### Main flow

1. User describes the issue (e.g. “My VPN won't connect”).
2. When KB/RAG is enabled, the system may offer adaptive grounded self-help steps first (see above).
3. If troubleshooting is skipped or fails, AI identifies intent `CreateTicket` and asks clarifying questions if needed.
4. When sufficient detail exists, AI proposes a structured intent with title, description, category, priority, and customer email.
5. Orchestration validates the payload.
6. On approval, a ticket is created in Zammad.
7. User sees assistant confirmation and a **ticket card** with the Zammad ticket number.

### Postconditions

- Ticket exists in Zammad with correct group and priority
- User has a verifiable ticket number from the provider (not invented by AI)
- Attached files appear on the initial Zammad article when included with the create request
- When troubleshoot ran first, ticket description may include attempted steps and chat transcript (configurable)

## Use case: Attach files

### Main flow

1. User clicks **📎** in the composer and selects one or more files (images, logs, PDFs).
2. Files upload to object storage via `POST .../attachments`; chips appear in the composer.
3. User sends a message describing the issue, referencing the attachment if needed.
4. **Screenshot / image:** the conversation agent uses OpenAI vision to read visible error codes and on-screen text — the user does not need to re-type what is shown in the image.
5. **New ticket:** when `CreateTicket` is approved, attachments are included on the initial Zammad article.
6. **Active ticket:** when a session already has `active_ticket_number`, `AddAttachment` adds files via a new Zammad article.

### Limits

| Rule | Value |
| ---- | ----- |
| Max file size | 10 MB |
| Max files per message | 5 |
| Blocked | Executable file types |

## Use case: Check ticket status

### Main flow

1. User asks about an existing ticket (e.g. “What's the status of ticket #22042?”).
2. AI identifies intent `CheckStatus`.
3. Orchestration builds a search command.
4. Help desk search returns matching tickets.
5. **One match:** user sees status summary and status card.
6. **Multiple matches:** user is asked to confirm which ticket.
7. **No match:** user is prompted to provide a ticket number.

## Policy and rejection

Orchestration may **reject** an operation with a stable reason code and user-facing message, for example:

| Reason | User-facing behavior |
| ------ | -------------------- |
| Missing title or description | Ask user to provide more detail |
| Low confidence | Ask user to clarify |
| Invalid schema | Ask user to rephrase |
| Access denied *(planned)* | Explain user cannot access that ticket |

Rejected operations **never** call the help desk API.

## Data shown to users

| Data | Source |
| ---- | ------ |
| Ticket number | Help desk API response only |
| Group, priority, state | Help desk API or workflow mapping |
| Policy rejection message | Reason code catalog |
| Detected intent label | Orchestration (informational) |

Users do **not** see raw JSON intents, internal rule IDs, or API tokens.

## Non-functional requirements (summary)

| Area | Target |
| ---- | ------ |
| Availability | API health endpoints; degraded messaging when provider unavailable *(planned)* |
| Response time | Conversational feel; processing indicators during orchestration |
| Auditability | Policy and provider operation logs in database |
| Security | Server-side credentials; user-scoped sessions |
| Accessibility | WCAG 2.2 AA target for web chat |

## Out of scope (this release)

- Teams, Slack, mobile, WhatsApp channels
- Voice interface
- In-chat live agent handoff
- Policy admin UI (ticket mapping remains YAML + environment; handbook admin is in scope)

## Related documents

- [Solution Architecture](03-solution-architecture.md) — technical realization
- [UI/UX Overview](08-ui-ux-overview.md) — experience patterns
- [Test & Acceptance](09-test-and-acceptance.md) — validation scenarios
