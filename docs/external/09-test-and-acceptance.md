# Test & Acceptance

This document defines the test approach and **user acceptance scenarios** for **Tech Support AI**. Use it for QA planning, customer UAT, and release sign-off.

## Test layers

| Layer | Scope | How to run |
| ----- | ----- | ---------- |
| Unit tests | Orchestration, ticketing adapters, agents, knowledge | `pytest` per package |
| API integration | Chat pipeline, session lifecycle, admin KB auth | `pytest apps/api/tests` |
| Live integration | OpenAI + Zammad sandbox | `make test-live` *(requires credentials)* |
| Browser E2E (mock) | Full UI flow without OpenAI/Zammad | `make e2e` *(Vite `:5175`)* |
| Live UI | Visible Chromium + real services | `make test-live-ui` *(optional)* |
| Mock E2E | UI + mock LLM, no external services | `make e2e` |

## Prerequisites for UAT

| Item | Detail |
| ---- | ------ |
| Environment | Docker Compose full stack per [Quick Start](00-quick-start.md) |
| Zammad sandbox | Dedicated test groups; integration API token |
| Test users | At least two `X-User-Id` values for isolation tests |
| OpenAI | API key with `GRAPH_LLM_MODE=openai`, or `mock` for UI-only UAT |
| KB / L1 + Admin KB | `KB_RAG_ENABLED=true`, Qdrant + Keycloak up, published handbook (`make seed-kb` or Admin SPA) |

## Acceptance criteria (release)

### Must pass

- [ ] Health endpoints return success when dependencies are up
- [ ] User can create a chat session and send messages
- [ ] CreateTicket: ticket appears in Zammad with correct group from mapping
- [ ] CreateTicket: UI shows ticket card with Zammad ticket number
- [ ] CheckStatus: single ticket lookup returns correct state
- [ ] Session isolation: user A cannot access user B's session
- [ ] Orchestration rejection: incomplete create does not call Zammad
- [ ] Message history persists across page refresh

### Should pass

- [ ] Thought streaming panel shows processing steps when enabled
- [ ] Multi-match status search prompts disambiguation
- [ ] Context strip updates with active ticket after create
- [ ] API returns appropriate errors for missing auth
- [ ] Attachment upload and ticket create with file (Zammad article has attachment)
- [ ] Screenshot attachment: assistant references on-screen error without user re-typing
- [ ] L1 guide: first support message offers one guided step (no handbook name in copy)
- [ ] L1 fail→ticket: “not working” / escalate creates ticket without dual clarify+card
- [ ] L1 resolve: user confirms fix → deflection, no ticket
- [ ] `KB_RAG_ENABLED=false` → legacy CreateTicket (no troubleshoot)
- [ ] Unpublished handbook is not retrieved; publish required

### Planned (not required for current release)

- [ ] UpdateTicket, Escalate, Cancel intents
- [ ] Confirm-before-submit flow
- [ ] End-user OIDC authentication (admin Keycloak is available)
- [ ] Audit log entries for each chat message flow

## UAT scenarios

### UAT-01 — Session creation

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Open web chat | Chat shell loads |
| 2 | Note session ID / URL | New session created |
| 3 | Refresh page | Same session resumes with history |

### UAT-02 — Create ticket (happy path)

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Send: “My laptop won't connect to VPN” | Assistant asks clarifying questions or proceeds |
| 2 | Provide category/details as prompted | Structured intake completes |
| 3 | Wait for response | Assistant confirms creation |
| 4 | Verify UI card | Card shows ticket number, group, priority, state |
| 5 | Open Zammad | Ticket exists with matching title/description |

**Pass criteria:** Ticket number in UI matches Zammad; group matches `mapping.yaml` for detected category.

### UAT-03 — Create ticket (rejection)

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Send vague message: “help” | Assistant asks for more detail |
| 2 | Verify Zammad | No new ticket created prematurely |

### UAT-04 — Check ticket status

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Create or note existing ticket number | Baseline ticket in Zammad |
| 2 | Ask: “What's the status of ticket #XXXXX?” | Assistant returns status |
| 3 | Verify card | Status card matches Zammad state |

### UAT-05 — Ambiguous status search

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Ask about a topic matching multiple tickets | Assistant lists or asks which ticket |
| 2 | Provide specific number | Correct single-ticket status |

### UAT-06 — Session isolation

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Create session as `user-a` | Session created |
| 2 | Request same session as `user-b` | 403 or 404 |

### UAT-07 — Thought streaming

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Set `THOUGHT_STREAMING_ENABLED=true` | Public config reflects true |
| 2 | Send message | Processing panel shows step labels |
| 3 | Completion | Final message and card appear |

### UAT-08 — Mock mode (no external deps)

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Set `GRAPH_LLM_MODE=mock` | API starts without OpenAI key |
| 2 | Send messages | Deterministic mock responses |
| 3 | UI functions | Chat shell works for demos |

### UAT-09 — Create ticket with screenshot attachment

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Attach `blue.png` (or similar BSOD screenshot) via 📎 | Upload succeeds; chip shown |
| 2 | Send: “Blue screen since this morning — see attached” | Processing may show “Reading attachment…” |
| 3 | Wait for response | Assistant references visible error text from image |
| 4 | Verify ticket card | Ticket created with Zammad number |
| 5 | Open Zammad | Ticket article includes attachment; description mentions error details |

**Pass criteria:** No `mime-type` API error; attachment visible in Zammad; assistant does not ask user to re-type on-screen error.

### UAT-10 — Add attachment to active ticket

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Complete UAT-02 or UAT-09 (active ticket in session) | Context strip shows ticket number |
| 2 | Attach a log file and send message | Upload succeeds |
| 3 | Verify Zammad | New article on ticket with attachment |

### UAT-11 — L1 guided step (first turn)

*Requires `KB_RAG_ENABLED=true` and a published handbook matching the issue (e.g. VPN).*

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Send a clear support problem (e.g. VPN disconnect) | Assistant offers empathetic opener + **one** guided step |
| 2 | Inspect reply | No handbook title or “knowledge base” phrasing |
| 3 | Verify Zammad | No ticket yet |

### UAT-12 — L1 fail → CreateTicket

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Complete UAT-11 | Guiding in progress |
| 2 | Reply that it did not work / ask to escalate | Ticket created; UI shows ticket card |
| 3 | Verify reply | Single outcome (ticket card), not clarify questions plus card |
| 4 | Open Zammad | Description may include handbook title + steps + transcript for **agents** (chat UI still hides handbook names). Controlled by `KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET`. |

### UAT-13 — L1 resolve (deflection)

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Complete UAT-11 | Guiding in progress |
| 2 | Confirm the step fixed the issue | Assistant acknowledges resolution |
| 3 | Verify Zammad | No new ticket |

### UAT-14 — KB flag off

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Set `KB_RAG_ENABLED=false` and restart API | Flag off |
| 2 | Send the same VPN problem | CreateTicket intake (no guided handbook step) |

### UAT-15 — Publish required for retrieval

| Step | Action | Expected result |
| ---- | ------ | --------------- |
| 1 | Upload a handbook but leave unpublished | Draft / ingested only |
| 2 | Chat with a matching problem (`KB_RAG_ENABLED=true`) | No guided step from that draft |
| 3 | Publish as `kb_admin`, retry | Guided step available |

## API smoke tests

```bash
# Health
curl -s http://localhost:8000/health/ready | jq .

# Create session
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/chat/sessions \
  -H "X-User-Id: uat-tester@company.com" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r .id)

# Send message
curl -s -X POST "http://localhost:8000/api/v1/chat/sessions/${SESSION}/messages" \
  -H "X-User-Id: uat-tester@company.com" \
  -H "Content-Type: application/json" \
  -d '{"content": "My VPN is not working"}' | jq .
```

## Defect severity guide

| Severity | Definition | Example |
| -------- | ---------- | ------- |
| Critical | Data loss, security breach, wrong user's session | Session isolation failure |
| High | Ticket created incorrectly or not created when should | Wrong Zammad group |
| Medium | UX confusion, missing card, slow response | Status card missing |
| Low | Cosmetic, non-blocking | Typo in processing label |

## Sign-off template

| Role | Name | Date | Result |
| ---- | ---- | ---- | ------ |
| Business owner | | | Pass / Fail |
| Support ops | | | Pass / Fail |
| QA lead | | | Pass / Fail |
| Security | | | Pass / Fail |

**Notes:**

---

## Automated test reference

| Package | Focus |
| ------- | ----- |
| `packages/ticketing/tests` | Gateway, Zammad adapter, factory |
| `packages/agents/tests` | Graph routing, troubleshoot, ticket_tool |
| `packages/knowledge/tests` | Chunking, ingest, store |
| `packages/orchestration/tests` | Policy, workflow |
| `apps/api/tests` | Ticket pipeline, chat service, admin KB auth |

Run full suite from repository root:

```bash
pytest packages/ticketing packages/agents packages/knowledge packages/orchestration apps/api/tests -q
```

## Related documents

- [Quick Start](00-quick-start.md)
- [Capability Matrix](appendices/C-capability-matrix.md)
- [Zammad Integration Guide](05-integration-guide-zammad.md)
