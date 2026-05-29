# Implementation Strategy – Tech Support AI

## Document Control

| Item | Detail |
| ---- | ------ |
| **Related documents** | [Functional Document](functional-document.md), [UI/UX Strategy](ui-ux-strategy.md), [Technical Strategy](technical-strategy.md) |
| **Estimated duration** | ~14 weeks to production MVP (adjust for team size) |
| **Audience** | Engineering leads, PM, QA, DevOps, support operations |
| **Purpose** | Executable plan to build, integrate, test, and release v1 |

---

## 1. Implementation Goals

### 1.1 What “Done” Means for v1

| Criterion | Verification |
| --------- | -------------- |
| All FSD §6 intents work end-to-end via web chat | E2E suite green |
| Orchestration gates every Zammad call | Integration tests + audit log rows |
| Ticket numbers are Zammad-grounded only | No card without `zammad_operations.status = success` |
| UI/UX Phase 1 deliverables shipped | Storybook cards + WCAG critical paths |
| FSD §11 audit trail complete | `policy_audit_log` + `zammad_operations` per action |
| Staging sign-off with real Zammad sandbox | Ops checklist signed |
| Production runbook and rollback tested | DevOps sign-off |

### 1.2 Out of Scope for v1 Build

Per FSD §1 and technical strategy: Teams/Slack/mobile/WhatsApp, RAG/KB, voice, in-chat human handoff, policy admin UI (API-only config acceptable for v1).

---

## 2. Team & Ownership Model

### 2.1 Recommended Workstreams

| Workstream | Owns | Typical roles |
| ---------- | ---- | ------------- |
| **WS1 – Platform** | Monorepo, Docker Compose, CI/CD, Postgres/Redis, Alembic, secrets | Backend lead, DevOps |
| **WS2 – API & Graph** | FastAPI, LangGraph, SSE, session lifecycle | Backend engineers |
| **WS3 – Orchestration** | Policy validator, workflow rules, reason codes, audit | Backend engineer |
| **WS4 – Zammad** | HTTP client, DTOs, sandbox mapping, outbox worker | Integration engineer |
| **WS5 – Web UI** | React chat, cards, streaming hooks, embed | Frontend engineers |
| **WS6 – Quality** | Test pyramid, Wiremock, Playwright, load smoke | QA + engineers |
| **WS7 – Ops & Security** | SSO, observability, runbooks, pen test coordination | DevOps, security |

One engineer may span streams in a small team; **orchestration (WS3) must not be owned solely by the LLM/prompt owner** to avoid policy drift into prompts.

### 2.2 RACI (Key Decisions)

| Decision | Responsible | Accountable | Consulted | Informed |
| -------- | ----------- | ----------- | --------- | -------- |
| Zammad field mapping | WS4 | Product/Ops | WS3 | All |
| Policy rule changes | WS3 | Support Ops | Security | PM |
| Graph topology changes | WS2 | Tech lead | WS3, WS5 | PM |
| UI card contract | WS5 | UX | WS2 | PM |
| Go-live | DevOps | Engineering lead | Ops, Security | Stakeholders |

---

## 3. Prerequisites (Week 0)

Complete before Sprint 1 coding starts.

### 3.1 Infrastructure & Access

| Item | Owner | Notes |
| ---- | ----- | ----- |
| Git repo + branch strategy (`main`, `develop`, feature branches) | Platform | Protect `main` |
| Cloud/subscription for dev/staging | DevOps | K8s or VM + managed Postgres/Redis |
| LLM API keys (dev/staging/prod separated) | Platform | Azure OpenAI or equivalent |
| Zammad **sandbox** instance URL + service token | WS4 | `ticket.agent` service user |
| SSO/OIDC test tenant (or auth stub documented) | WS7 | Match prod IdP when known |
| Object store for attachments (MinIO dev, S3 prod) | Platform | |
| Secrets manager pattern agreed | DevOps | No tokens in repo |

### 3.2 Zammad Sandbox Configuration

| Config | Action |
| ------ | ------ |
| Groups | Create queues matching workflow rules (e.g. Network Support, Security) |
| Priorities | Align names with mapping table (`1 low`, `2 normal`, `3 high`) |
| Custom objects | Add Ticket category field; record **internal names** for API |
| Service account | API token; verify create-on-behalf with `customer_id: guess:email` |
| Test customers | 2–3 users for access-scope testing |

Deliverable: **`zammad-field-mapping.yaml`** in repo (committed, no secrets).

### 3.3 Shared Contracts (Day 1 Alignment)

Freeze v1 schemas early to unblock parallel work:

| Artifact | Path (proposed) | Consumers |
| -------- | --------------- | --------- |
| `StructuredIntent` | `packages/shared/schemas/intent.json` | Graph, orchestration, tests |
| `ZammadCommand` | `packages/shared/schemas/command.json` | Orchestration, zammad client |
| `StreamEvent` | `packages/shared/schemas/stream-event.json` | API, React |
| `UIEvent` / card types | `packages/shared/schemas/cards.json` | Graph respond node, React |
| Reason codes enum | `packages/shared/reason_codes.py` | Orchestration, Postgres seed |

**Gate:** WS2, WS3, WS5 do not merge conflicting shapes without schema version bump.

---

## 4. Delivery Phases & Milestones

Maps to [Technical Strategy §14](technical-strategy.md#14-implementation-phases) with sprint-level detail.

```text
Week 0        Prerequisites & contracts
Weeks 1–4     M1: Foundation (walk skeleton)
Weeks 5–8     M2: Intelligent core (CreateTicket E2E)
Weeks 9–11    M3: Full intents + resilience
Weeks 12–14   M4: Hardening + production pilot
```

| Milestone | Date (example) | Demo |
| --------- | -------------- | ---- |
| **M0** | End Week 0 | Contracts reviewed; Zammad sandbox smoke POST ticket |
| **M1** | End Week 4 | Chat UI sends messages; API persists; mock graph echo |
| **M2** | End Week 8 | Create ticket E2E with real Zammad + policy + SSE |
| **M3** | End Week 11 | All intents + outbox + degraded UI |
| **M4** | End Week 14 | Staging UAT pass; pilot go-live |

---

## 5. Sprint Plan

### Sprint 1 (Week 1) — Monorepo & Runtime

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S1.1 | Init monorepo (`apps/web`, `apps/api`, `packages/*`) | Platform | CI lint runs |
| S1.2 | Docker Compose: postgres, redis, minio | Platform | `docker compose up` healthy |
| S1.3 | Alembic init + `chat_sessions`, `chat_messages` | Platform | Migration applies |
| S1.4 | FastAPI health + OpenAPI stub | WS2 | `/health/ready` 200 |
| S1.5 | React Vite app + ChatShell placeholder | WS5 | App loads in browser |

**Exit:** Developer can run full stack locally in &lt; 15 minutes (documented in `README.md`).

---

### Sprint 2 (Week 2) — Session API & UI Stream

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S2.1 | `POST/GET /chat/sessions`, `POST/GET messages` | WS2 | Postman collection passes |
| S2.2 | Auth middleware stub (`X-User-Id` dev / JWT prod path) | WS2 | 401 without identity |
| S2.3 | MessageStream + Composer (no AI) | WS5 | Messages render both roles |
| S2.4 | Shared TypeScript types from OpenAPI or JSON schema | WS5 | Types compile |
| S2.5 | Redis: session context key + basic get/set | WS2 | Integration test |

**Exit:** User can open chat, send text, see history after refresh (Postgres).

---

### Sprint 3 (Week 3) — Zammad Client & Orchestration Skeleton

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S3.1 | `zammad-client`: create ticket, get ticket, search | WS4 | Wiremock tests green |
| S3.2 | Pydantic DTOs + error mapping | WS4 | |
| S3.3 | `PolicyValidator` v0: JSON Schema on `StructuredIntent` | WS3 | Unit tests for required fields |
| S3.4 | `WorkflowEngine` v0: static group/priority map | WS3 | Fixture tests |
| S3.5 | Tables: `policy_audit_log`, `zammad_operations` | Platform | Migrations applied |
| S3.6 | Seed `reason_code_messages` (EN v1) | WS3 | SQL seed script |

**Exit:** CLI/script can create a ticket in sandbox bypassing LangGraph (proves integration).

---

### Sprint 4 (Week 4) — M1 Demo: Vertical Skeleton

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S4.1 | Mock “graph” endpoint returns canned assistant reply | WS2 | UI shows bot message |
| S4.2 | System status line component | WS5 | UI/UX §7.3 labels |
| S4.3 | Context strip (active ticket placeholder) | WS5 | |
| S4.4 | CI: pytest + vitest on PR | Platform | Required check |
| S4.5 | Zammad sandbox E2E script (create + get) | WS4 | Runs in CI with secrets |

**M1 demo:** Web chat → API → Zammad ticket created via script; UI skeleton complete.

---

### Sprint 5 (Week 5) — LangGraph Bootstrap

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S5.1 | `SupportGraphState` + graph builder | WS2 | Compiles |
| S5.2 | `conversation` node + structured output schema | WS2 | Mock LLM test |
| S5.3 | `orchestrate` node calls WS3 package | WS2 | Reject path tested |
| S5.4 | `zammad_tool` node (create only) | WS2 | Approved command only |
| S5.5 | Postgres LangGraph checkpointer | WS2 | Resume by `thread_id` |

**Exit:** Graph invoke creates ticket in sandbox from fixed intent fixture.

---

### Sprint 6 (Week 6) — SSE & Redis Memory

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S6.1 | Redis pub/sub + `GET .../stream` SSE | WS2 | Events received in browser |
| S6.2 | Stream `token`, `system_status`, `done` | WS2/5 | Contract test |
| S6.3 | Redis session memory summary (rolling) | WS2 | Rehydrate after 10 turns |
| S6.4 | `useSSEStream` hook + typing indicator | WS5 | &lt; 300ms indicator |
| S6.5 | Wire LLM provider (env-configured) | WS2 | Dev only key |

**Exit:** Real LLM conversation in dev; tokens stream to UI.

---

### Sprint 7 (Week 7) — Create Ticket Flow & Confirm Interrupt

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S7.1 | `interrupt_before` confirm node | WS2 | Graph pauses |
| S7.2 | `POST .../confirm` resumes graph | WS2 | |
| S7.3 | Summary card component + confirm/edit | WS5 | UI/UX §6.1 |
| S7.4 | Ticket created card (only on `card` event) | WS5 | No ID before event |
| S7.5 | Policy reject → `policy_rejected` SSE + message | WS3/5 | Reason code shown |
| S7.6 | `respond` node templates (no ID invention) | WS2 | Test asserts |

**Exit:** Full CreateTicket happy path in dev environment.

---

### Sprint 8 (Week 8) — M2 Demo: Production-Path Create

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S8.1 | Attachment upload API + MinIO | WS2 | File reaches storage |
| S8.2 | Policy: attachment size/type rules | WS3 | Reject oversized |
| S8.3 | Audit: every orchestration outcome logged | WS3 | Row per invoke |
| S8.4 | Storybook: all Phase 1 cards | WS5 | |
| S8.5 | Playwright: create ticket happy path | WS6 | CI nightly |

**M2 demo:** Stakeholder creates VPN ticket in staging; `#number` matches Zammad UI.

---

### Sprint 9 (Week 9) — CheckStatus & UpdateTicket

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S9.1 | Graph routing for `CheckStatus`, `UpdateTicket` | WS2 | |
| S9.2 | Zammad search + access policy | WS3/4 | Cross-user denied |
| S9.3 | Disambiguation card (≤5 tickets) | WS5 | UI/UX §6.2 |
| S9.4 | Status card + copy ticket # | WS5 | |
| S9.5 | Update preview + comment article tool | WS2/4 | |

---

### Sprint 10 (Week 10) — Attach, Escalate, Close

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S10.1 | `AddAttachment` graph + base64 article | WS4 | |
| S10.2 | `EscalateIssue` workflow rules | WS3 | VIP/keyword fixtures |
| S10.3 | Escalation confirm card | WS5 | |
| S10.4 | `CancelTicket` → close state (not DELETE) | WS3/4 | |
| S10.5 | Fallback panel (static config) | WS5 | FSD §12 |

---

### Sprint 11 (Week 11) — M3: Resilience & Observability

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S11.1 | Outbox worker + `outbox_jobs` | WS4 | Retry on 503 |
| S11.2 | Degraded mode banners (LLM/Zammad down) | WS5 | UI/UX §12.2 |
| S11.3 | OpenTelemetry traces | Platform | Trace across nodes |
| S11.4 | Metrics: `first_token`, `zammad_ms`, reject rate | Platform | Dashboard |
| S11.5 | Playwright: policy reject + disambiguation | WS6 | |

**M3 demo:** All intents in staging; Zammad outage queues job and recovers.

---

### Sprint 12 (Week 12) — SSO & Security Hardening

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S12.1 | OIDC integration (staging IdP) | WS7 | Real login |
| S12.2 | Rate limiting (Redis) | WS2 | 429 over threshold |
| S12.3 | PII redaction in logs | Platform | Spot check |
| S12.4 | Command signing / type safety on zammad_tool | WS2 | Negative test |
| S12.5 | Session timeout + warning UI | WS5 | |

---

### Sprint 13 (Week 13) — Performance & UAT

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S13.1 | Load smoke: 50 concurrent sessions | WS6 | No error burst |
| S13.2 | WCAG audit fixes (critical) | WS5 | Report attached |
| S13.3 | CSAT endpoint + optional UI prompt | WS2/5 | Event logged |
| S13.4 | UAT script with support ops (10 scenarios) | PM/QA | Signed |
| S13.5 | Analytics events (UI/UX §14) | WS5 | |

---

### Sprint 14 (Week 14) — M4: Pilot Go-Live

| ID | Task | WS | Done when |
| -- | ---- | -- | --------- |
| S14.1 | Production deploy + secrets | DevOps | |
| S14.2 | Runbook: deploy, rollback, Zammad token rotate | DevOps | |
| S14.3 | Pilot cohort (limited users) | PM | |
| S14.4 | Hypercare week on-call rota | All | |
| S14.5 | Retro + backlog for Phase 2 | PM | |

---

## 6. Critical Path

```text
Zammad sandbox ready (W0)
    → zammad-client (S3)
    → orchestration package (S3)
    → LangGraph + orchestrate + zammad_tool (S5–S7)
    → SSE + confirm interrupt (S6–S7)
    → M2 E2E (S8)
    → remaining intents (S9–S10)
    → outbox + SSO (S11–S12)
    → UAT + go-live (S13–S14)
```

**Parallelizable early:** React shell (S1–S2) alongside Zammad client (S3); Storybook cards (S8) while graph stabilizes.

**Blockers:**

* LLM unavailable → use mock LLM implementer until S6; do not block S3–S5.
* Zammad mapping unknown → blocks workflow engine finalization, not UI skeleton.

---

## 7. Build Order by Component

### 7.1 Bottom-Up (Recommended)

```text
1. packages/shared          (schemas, reason codes)
2. packages/zammad-client   (HTTP + DTOs)
3. packages/orchestration   (validator + workflow + audit)
4. packages/agents          (LangGraph)
5. apps/api                 (FastAPI wires all)
6. apps/web                 (React consumes API)
```

### 7.2 Horizontal Slices (Per Intent)

For each intent after M2, use the same slice template:

| Step | Backend | Frontend |
| ---- | ------- | -------- |
| 1 | Extend `StructuredIntent` payload | — |
| 2 | Orchestration rules + tests | — |
| 3 | Zammad command + tool | — |
| 4 | Graph branch + routing | — |
| 5 | SSE events + card type | Card component |
| 6 | Playwright scenario | — |

---

## 8. Environment Strategy

| Environment | Data | LLM | Zammad | Users |
| ----------- | ---- | --- | ------ | ----- |
| **Local** | Docker Postgres/Redis | Dev key / mock | Wiremock default; sandbox optional | Dev headers |
| **CI** | Ephemeral containers | Mock LLM | Wiremock | Fixture users |
| **Staging** | Managed DB | Staging deployment | Zammad sandbox | SSO test users |
| **Prod pilot** | Managed DB HA | Prod deployment | Zammad prod | Pilot group |
| **Prod** | Managed DB HA | Prod | Zammad prod | Gradual rollout |

**Promotion rule:** Same Docker image from `main` build; config via env only.

---

## 9. Testing Gates (Definition of Done per Sprint)

| Gate | Applies from | Requirement |
| ---- | ------------ | ----------- |
| **G0 – Unit** | S3+ | Orchestration & zammad-client &gt; 80% branch on critical paths |
| **G1 – Contract** | S6+ | SSE JSON schema validation in CI |
| **G2 – Integration** | S5+ | Graph tests with mock LLM for each intent |
| **G3 – E2E** | S8+ | Playwright happy path on staging weekly |
| **G4 – Security** | S12+ | No critical findings; secrets scan clean |
| **G5 – Perf smoke** | S13 | p95 first token &lt; 4s staging under load |

**Merge policy:** PR requires G0 for touched packages; release to staging requires G2; production requires G3–G5.

---

## 10. Configuration & Policy Rollout

### 10.1 v1 Policy Delivery (No Admin UI)

| Approach | Implementation |
| -------- | -------------- |
| Rules stored in Postgres | Seed migrations + `config/policy/v1/*.yaml` in git |
| Deploy | Migration or `admin-cli load-policy` on release |
| Reason copy | `reason_code_messages` seeded; hotfix via SQL in pilot |

### 10.2 Change Process

1. PR updates YAML + unit fixtures.
2. WS3 reviews rule impact.
3. Deploy to staging → run regression orchestration tests.
4. Ops approves prod policy bump (change ticket).

---

## 11. DevOps & CI/CD Pipeline

```text
PR → lint + unit + contract tests
  → build api + web images
  → integration (Wiremock + mock LLM)
Merge to develop → deploy staging
Tag release → deploy prod (manual approval)
```

| Stage | Actions |
| ----- | ------- |
| PR | Ruff/mypy, pytest, vitest, eslint |
| Main | Push images, deploy staging, Playwright nightly |
| Release | Prod deploy, run DB migrations, smoke test |

**Database:** Alembic migrations run as Job before new API pods serve traffic.

---

## 12. Documentation Deliverables (Engineering)

| Doc | When | Owner |
| --- | ---- | ----- |
| `README.md` local setup | S1 | Platform |
| `docs/runbooks/deploy.md` | S14 | DevOps |
| `docs/runbooks/zammad-token-rotate.md` | S14 | WS4 |
| OpenAPI (exported from FastAPI) | S2 | WS2 |
| `zammad-field-mapping.yaml` | W0 | WS4 |
| Policy rule authoring guide | S8 | WS3 |

---

## 13. Risk Register (Implementation)

| Risk | Likelihood | Impact | Mitigation |
| ---- | ---------- | ------ | ---------- |
| Zammad mapping mismatch | High | High | W0 sandbox + mapping file; early S3 script |
| LLM latency blows SLO | Medium | Medium | Streaming; step labels; cache system prompts |
| Graph interrupt stuck | Medium | Medium | Session timeout; cancel endpoint S7 |
| Scope creep (RAG, channels) | High | Medium | PM guards FSD §1; backlog Phase 2 |
| Orchestration logic in prompts | Medium | High | WS3 owns rules; code review checklist |
| SSO delays | Medium | Medium | Dev stub until S12; don’t block M2 |

---

## 14. Go-Live Checklist

### 14.1 Pre-Production

- [ ] Staging UAT signed (10 scenarios)
- [ ] Zammad prod token in secrets manager
- [ ] Policy v1 loaded and version tagged in audit config
- [ ] Reason-code messages reviewed by support ops
- [ ] Load smoke passed (S13.1)
- [ ] WCAG critical issues resolved
- [ ] Rollback procedure tested (previous image + DB backward compatible)
- [ ] On-call runbook and escalation contacts

### 14.2 Launch Day

- [ ] Deploy API + web during low-traffic window
- [ ] Migrations applied successfully
- [ ] Smoke: create ticket + check status in prod
- [ ] Dashboards: error rate, `first_token`, policy reject rate
- [ ] Pilot users notified; fallback contacts visible in UI

### 14.3 Hypercare (Week 1 post-launch)

- [ ] Daily review of `policy_audit_log` rejects
- [ ] Sample transcript review for hallucination/UX issues
- [ ] Zammad ticket quality spot-check
- [ ] KPI baseline captured for FSD §17 comparison at 30 days

---

## 15. Post-v1 Backlog (Prioritized)

| Priority | Item | Source |
| -------- | ---- | ------ |
| P1 | Policy admin API + UI | Technical strategy Phase 4 |
| P1 | RAG / KB layer | FSD §3.6 |
| P2 | Embeddable widget NPM package | UI/UX §7.5 |
| P2 | Additional channels | FSD §15 |
| P3 | Multilingual | FSD §7 |
| P3 | LangSmith production analytics | Technical strategy §11 |

---

## 16. Success Metrics (Implementation Phase)

Track from pilot week:

| Metric | Target | Tool |
| ------ | ------ | ---- |
| Create ticket E2E success rate | &gt; 95% staging | Playwright + prod logs |
| Policy reject rate | Baseline; tune rules | `policy_audit_log` |
| p95 first token | &lt; 3s staging | OTel |
| Defect escape rate | &lt; 2 critical in pilot | Incident tracker |
| Sprint velocity stability | ±20% | PM |

Align production KPIs with FSD §17 after 30 days of pilot data.

---

## 17. Appendix — Sprint Dependency Graph

```text
S1 ──► S2 ──► S4 (M1)
 │
 └──► S3 ──► S5 ──► S6 ──► S7 ──► S8 (M2)
              │              │
              └──────────────┴──► S9 ──► S10 ──► S11 (M3)
                                      │
                                      └──► S12 ──► S13 ──► S14 (M4)
S5 (parallel UI) ─────────────────────────────────────────► S7, S8, S9...
```

## 18. Appendix — Document Map

| Implementation question | Read |
| ----------------------- | ---- |
| What to build | [Functional Document](functional-document.md) |
| How it should feel | [UI/UX Strategy](ui-ux-strategy.md) |
| How to architect it | [Technical Strategy](technical-strategy.md) |
| When and who builds it | **This document** |

---

## 19. Conclusion

Implementation proceeds **foundation → LangGraph core → full intents → hardening**, with **orchestration and Zammad integration on the critical path** and **React UI parallel from Sprint 1**. Shared schemas in Week 0 prevent integration thrash. Each milestone ends in a demonstrable, test-gated increment culminating in a **limited pilot go-live** at Week 14, with hypercare and KPI baselines before broader rollout.
