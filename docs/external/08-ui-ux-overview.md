# UI/UX Overview

This document describes the **Tech Support AI** web chat experience for product owners, designers, and support operations stakeholders.

## Experience goals

| Goal | Design approach |
| ---- | --------------- |
| Feel like messaging, not a form | Conversational composer; multi-turn clarification |
| Trust in outcomes | Ticket numbers and status from Zammad — shown in structured cards |
| Transparency during wait | Processing labels and optional thought streaming panel |
| Resume conversations | Session list and context strip for active ticket |
| Accessibility | WCAG 2.2 AA target; semantic structure and keyboard support |

## Primary layout

```text
┌────────────────────────────────────────────────────────────┐
│  Context strip — active ticket, session info                │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Message stream — user bubbles, assistant replies, cards    │
│                                                             │
│  [ Optional: Thought stream panel — processing steps ]      │
│                                                             │
├────────────────────────────────────────────────────────────┤
│  Composer — text input + send + 📎 file attach                      │
└────────────────────────────────────────────────────────────┘
```

**Main components** (`apps/web`):

| Component | Role |
| --------- | ---- |
| `ChatShell` | Overall layout and session management |
| `MessageStream` | Renders message history |
| `MessageCard` | Rich cards for ticket events |
| `Composer` | User input and file attachment (📎) |
| `ContextStrip` | Active ticket context |
| `SystemStatusLine` | Inline processing status |
| `ThoughtStreamPanel` | Live processing steps (when enabled) |

## Conversation patterns

### Guided self-help (KB/RAG)

*When `KB_RAG_ENABLED=true` and a published handbook matches the issue.*

1. User describes a new support problem in natural language.
2. Assistant replies with an **empathetic opener** and **one** concrete step (Markdown: bold titles, numbered lists).
3. Handbook names and “knowledge base” internals are **never** shown in chat.
4. **If it worked:** assistant confirms and does **not** create a ticket.
5. **If it did not work:** assistant creates a ticket (confirmation + card only — no extra diagnostic question in the same turn).

Processing labels may include “Looking into that…” / “I have a suggestion…” (neutral wording).

### Create ticket

1. User describes issue in natural language (or arrives here after a failed self-help step).
2. Assistant may ask clarifying questions (category, urgency, details) when KB is off or no handbook matched.
3. When ready, orchestration creates the ticket.
4. User sees assistant confirmation **and** a **ticket created card**:

```text
┌─────────────────────────────┐
│ Ticket #22042               │
│ IT Support · 2 normal · new │
└─────────────────────────────┘
```

The ticket number always comes from Zammad — never invented by the model.

### Attach files and screenshots

1. User clicks **📎** in the composer and selects file(s).
2. Upload progress completes; filename chips appear above the input.
3. User sends a message (e.g. “Blue screen since this morning — see attached”).
4. **Images:** the assistant reads visible error codes and on-screen text via OpenAI vision — users should not need to re-type what is shown in the screenshot.
5. **New ticket:** files are included on the initial Zammad article when the ticket is created.
6. **Active ticket:** files are added via a new Zammad article on the open ticket.

Processing labels may include **“Reading attachment…”** while image content is analyzed.

### Check status

1. User references a ticket number or describes what they're looking for.
2. Assistant returns a conversational summary.
3. **Single match:** status card with state and group.
4. **Multiple matches:** assistant asks which ticket.
5. **No match:** assistant asks for a ticket number.

### Policy rejection

When orchestration rejects an action (missing fields, low confidence):

- User sees a plain-language explanation
- No ticket card appears
- User can continue the conversation to provide more detail

## Message types

| Type | Appearance |
| ---- | ---------- |
| User message | Right-aligned or distinct user bubble; may show attachment filename |
| Assistant message | Left-aligned reply; **Markdown rendered** (bold, lists, code) for assistant text |
| Card message | Structured block below assistant text |
| System status | Subtle processing line during graph execution |

## Thought streaming

When `THOUGHT_STREAMING_ENABLED=true` (exposed via public config):

- UI calls `POST .../messages/stream` instead of synchronous endpoint
- **ThoughtStreamPanel** shows live labels such as “Understanding your request”, “Creating ticket”
- Final assistant message and card appear when processing completes

When disabled, the UI uses the standard message endpoint and may show `system_statuses` from the response.

## Session continuity

| Feature | Behavior |
| ------- | -------- |
| Session resume | Users return to prior sessions from session list |
| Active ticket | Context strip shows `active_ticket_number` from session |
| Message history | Loaded from API on session open |

Redis-backed context supplements Postgres for fast access to recent state.

## Card catalog

| Card type | When shown | Key fields |
| --------- | ---------- | ---------- |
| `ticket_created` | After successful create | `ticket_number`, `group`, `priority`, `state` |
| `ticket_status` | After status lookup | `ticket_number`, `state`, `group` |
| `ticket_summary` | Confirm-before-submit *(planned)* | `title`, `description` |

## Admin SPA (handbook maintenance)

Handbook upload, Markdown preview, publish, reindex, and search preview live in a **dedicated** React app (`apps/admin`, typically http://localhost:5174). It is a **core product module** (not an optional add-on), separate from the end-user chat shell. Admins sign in with **Keycloak** (`kb_editor` / `kb_admin` roles). Local setup: [Quick Start](00-quick-start.md).

## Planned UX enhancements

| Feature | Description |
| ------- | ----------- |
| Confirm-before-submit | Summary card + explicit user approval before Zammad create |
| Typing indicator | Visual feedback while assistant is generating |
| Token streaming | Word-by-word assistant reply display |
| Error recovery | Clear messaging when Zammad or OpenAI unavailable |

## Accessibility

Target: **WCAG 2.2 Level AA**

| Area | Approach |
| ---- | -------- |
| Keyboard | Composer and navigation operable without mouse |
| Screen readers | Semantic roles for messages and cards |
| Color contrast | Sufficient contrast for text and status indicators |
| Motion | Respect `prefers-reduced-motion` for streaming animations *(planned)* |

## Branding and theming

The default UI is a functional enterprise chat shell. Organizations can:

- Customize CSS modules in `apps/web`
- Embed the SPA in an iframe within an intranet portal
- Replace the web app with a custom client using the [API Overview](07-api-overview.md)

## What users do not see

- Raw JSON intents or orchestration payloads
- Handbook / runbook titles or “from the knowledge base” phrasing
- Zammad API tokens or internal error stack traces
- Internal reason code IDs (user sees friendly messages only)

## Related documents

- [Functional Specification Summary](02-functional-specification-summary.md)
- [API Overview](07-api-overview.md)
- [Test & Acceptance](09-test-and-acceptance.md)
