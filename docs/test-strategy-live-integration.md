# Test Strategy — Live Integration with AI User Simulator

## Document control

| Item | Detail |
| ---- | ------ |
| **Audience** | Engineering, QA, DevOps |
| **Related documents** | [Functional Document](functional-document.md), [Implementation Strategy](implementation-strategy.md) |
| **Scope** | Live integration tests: real OpenAI (support agent) + real Zammad + AI User Simulator |
| **Status** | Active — Phase 1–2 implemented in `tests/integration/` |

---

## 1. Purpose

Validate the **full production path** for ticket creation:

```text
User (simulated) → Web Chat API → LangGraph → OpenAI → Orchestration → Zammad
```

Unlike unit tests (mocks) or Playwright E2E (Wiremock Zammad), these tests use:

- **Real OpenAI** for the support conversation agent (`GRAPH_LLM_MODE=openai`)
- **Real Zammad sandbox** for ticket persistence
- **AI User Simulator** — a second LLM that role-plays an employee and drives multi-turn dialogue

**Success criterion:** For each of 10 issue scenarios, the support agent collects enough information and creates a ticket whose number is verified in Zammad.

---

## 2. Problem with scripted user messages

The initial integration harness used fixed turn scripts (`opening → follow_up → confirm`). That approach:

| Limitation | Impact |
| ---------- | ------ |
| Ignores what the support agent actually asked | Misses broken clarification loops |
| Same replies every run | Overfits to current prompt/graph behavior |
| Cannot adapt to policy reject or missing email | False failures or false passes |
| Unrealistic user behavior | Does not test NLU + multi-turn collection |

**Decision:** Replace scripted turns with an **AI User Simulator Agent**.

---

## 3. Target architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Test Harness                      │
│  ┌──────────────┐    HTTP API     ┌──────────────────────────┐  │
│  │ User Sim     │◄───────────────►│ Tech Support AI (SUT)    │  │
│  │ Agent (LLM)  │  POST /messages │ LangGraph + OpenAI +     │  │
│  │              │                 │ Orchestration + Zammad   │  │
│  └──────┬───────┘                 └────────────┬─────────────┘  │
│         │                                      │                 │
│         │ reads scenario brief                 │ creates ticket  │
│         │ + conversation history               ▼                 │
│         │                              ┌──────────────┐          │
│         └──────────────────────────────│ Zammad (real)│          │
│                                        └──────────────┘          │
│  ┌──────────────┐                                                │
│  │ Evaluator    │  Hard gates: ticket in Zammad, keywords, ref   │
│  │ (rules)      │  Soft gates (future): LLM transcript judge     │
│  └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────┘
```

- **SUT** — system under test (existing stack)
- **User Sim Agent** — `tests/integration/user_sim/`
- **Evaluator** — `tests/integration/evaluator/rules.py`

---

## 4. User Simulator Agent

### 4.1 Responsibilities

1. Open with a natural first message derived from a scenario brief
2. Read each support agent reply (and cards when present)
3. Reply as a realistic employee: answer clarifying questions, provide email when asked, confirm ticket creation
4. Use a hidden **fact sheet** per scenario; reveal facts progressively when asked
5. Stop when ticket is created, max turns reached, or conversation is blocked

### 4.2 Constraints

- Must **not** call Zammad or orchestration directly — only the chat API
- Must **not** invent ticket numbers
- Must **not** break character (no mention of testing, automation, or Zammad)

### 4.3 Structured output

Each User Sim turn returns:

| Field | Description |
| ----- | ----------- |
| `reply_to_support` | Next user message (empty if done) |
| `conversation_done` | Whether to stop the loop |
| `done_reason` | `ticket_created`, `gave_up`, `blocked`, or null |
| `notes` | Internal test log only — never sent to API |

Implementation: OpenAI structured output via LangChain (`UserSimTurn` schema).

### 4.4 LLM configuration

| Role | Env var | Default |
| ---- | ------- | ------- |
| Support agent (SUT) | `OPENAI_MODEL` | `gpt-4o-mini` |
| User Simulator | `USER_SIM_MODEL` | Same as `OPENAI_MODEL` |
| User Sim temperature | `USER_SIM_TEMPERATURE` | `0.4` |

Use the same API key (`OPENAI_API_KEY`) for both agents in v1.

---

## 5. Scenario model

Each scenario defines a **brief + fact sheet**, not fixed dialogue:

| Field | Purpose |
| ----- | ------- |
| `id` | Stable test identifier |
| `category` | Expected orchestration routing (network, email, etc.) |
| `user_goal` | What the simulated user wants to achieve |
| `initial_complaint_hint` | Seed topic for turn 1 (not verbatim script) |
| `fact_sheet` | Hidden facts revealed when support asks |
| `title_keywords` | Hard gate: at least one must appear in Zammad title |
| `persona` | Name, role, department for natural tone |

Example fact sheet keys: `device`, `software`, `error`, `when_started`, `impact`, `urgency`.

---

## 6. Conversation loop

```text
create session
generate opening (User Sim)
loop (max INTEGRATION_MAX_TURNS, default 12):
  POST user message → support API
  if ticket_created or active_ticket_number → success
  User Sim reads assistant reply → next user message
  if conversation_done → exit
assert hard gates (Zammad verify, keywords, reference ID)
save transcript JSON to tests/integration/artifacts/
```

### Parameters

| Parameter | Default | Notes |
| --------- | ------- | ----- |
| `INTEGRATION_MAX_TURNS` | 12 | Per scenario |
| Per-turn timeout | 60s | API + dual LLM |
| Retry on transient errors | 1 | OpenAI / Zammad 503 |

---

## 7. Evaluation strategy

### 7.1 Hard gates (must pass — implemented)

1. Ticket exists in Zammad; number matches API response
2. Ticket number is numeric and API-grounded (not LLM-invented)
3. Session `active_ticket_number` matches Zammad
4. Title contains at least one scenario `title_keywords`
5. Run reference ID traceable in conversation (`LIVE-{scenario}-{id}`)
6. Completed within turn budget

### 7.2 Soft gates (Phase 3 — planned)

Optional LLM evaluator on transcript:

- Did support gather description + impact before creating ticket?
- Were clarifying questions reasonable?
- If policy rejected, was the reason explained?

Fail if score below threshold (configurable).

---

## 8. The ten scenarios

| ID | Category | User goal |
| -- | -------- | --------- |
| `vpn_network` | network | Restore VPN from home |
| `email_outlook` | email | Fix Outlook sync |
| `access_locked` | access_management | Unlock domain account |
| `hardware_boot` | hardware | Laptop won't boot |
| `software_excel` | software | Stop Excel crashes on macro files |
| `security_phishing` | security | Report phishing email |
| `infrastructure_wiki` | infrastructure | Internal wiki 502 errors |
| `hardware_printer` | hardware | Network printer offline |
| `network_wifi` | network | Wi-Fi drops on video calls |
| `access_mfa` | access_management | Fix MFA / SSO login |

Defined in `tests/integration/scenarios.py`.

---

## 9. Implementation phases

| Phase | Scope | Status |
| ----- | ----- | ------ |
| **1** | User Sim core, conversation loop, VPN scenario | Done |
| **2** | All 10 scenarios, transcript artifacts, env docs | Done |
| **3** | LLM transcript evaluator, rich failure reports | Planned |
| **4** | Nightly staging workflow, cost dashboards | Planned |

### Repository layout

```text
tests/integration/
  user_sim/
    schema.py
    prompts.py
    openai_user_sim.py
  evaluator/
    rules.py
  simulated_conversation.py
  scenarios.py
  artifacts/          # gitignored transcript JSON
  log.py                  # structured logging
  transport.py            # API + browser chat transports
  live_stack.py           # starts API + web for browser mode
  test_live_create_ticket.py      # API tests (@live)
  test_live_create_ticket_ui.py   # browser tests (@live_ui)
docs/
  test-strategy-live-integration.md   # this document
```

---

## 10. Running tests

### Prerequisites

```env
GRAPH_ENABLED=true
GRAPH_LLM_MODE=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
USER_SIM_MODEL=gpt-4o-mini          # optional
ZAMMAD_BASE_URL=https://...
ZAMMAD_API_TOKEN=...
ZAMMAD_TEST_EMAIL=you@company.com
INTEGRATION_MAX_TURNS=12            # optional
```

Infrastructure: Postgres + Redis (`docker compose up -d postgres redis`).

### Commands

**API mode (headless)** — fast, with structured console + file logging:

```bash
make migrate
make test-live

# Single scenario:
.venv/bin/pytest tests/integration -m live -k vpn_network -v -s --log-cli-level=INFO
```

**Browser mode (visible)** — watch the User Sim type into the chat UI:

```bash
make test-live-ui

# Single scenario in browser:
.venv/bin/pytest tests/integration -m live_ui -k vpn_network -v -s --log-cli-level=INFO
```

Logs: terminal + `tests/integration/artifacts/live_integration.log`  
Transcripts: `tests/integration/artifacts/{scenario}_{ref}.json`

Browser mode auto-starts API (`:8020`) and web UI (`:5175`). Set `INTEGRATION_HEADLESS=false` and `INTEGRATION_SLOW_MO=350` to slow down for easier watching.

### CI

Manual workflow: `.github/workflows/integration-live.yml` (`workflow_dispatch`).

Not run on every PR — cost, latency, and sandbox side effects.

---

## 11. Risks and mitigations

| Risk | Mitigation |
| ---- | ---------- |
| Non-deterministic flakiness | Transcript artifacts; 1 retry; tune User Sim prompt |
| OpenAI cost (2× LLM per turn × 10 scenarios) | On-demand runs; `USER_SIM_MODEL=gpt-4o-mini`; turn cap |
| User Sim too helpful (dumps all facts turn 1) | Prompt: reveal progressively; temperature 0.4 |
| User Sim too passive (never confirms) | Explicit confirm-when-asked rules |
| Infinite clarification loop | Max turns + stuck-loop detection (duplicate assistant reply) |
| 10 real tickets in sandbox | Close after run; unique reference ID per run |

---

## 12. Comparison: Playwright E2E vs live integration

| Aspect | Playwright E2E | Live integration |
| ------ | ---------------- | ---------------- |
| LLM | Mock | Real OpenAI |
| Zammad | Wiremock | Real sandbox |
| User | Script / fixed | AI User Simulator |
| UI coverage | Yes | No (API-level) |
| CI default | PR checks | Manual dispatch |
| Purpose | Regression, UI | End-to-end intelligence + Zammad |

Both are required; they test different layers.

---

## 13. Acceptance criteria

- [x] User Sim drives all 10 scenarios (no scripted follow-ups)
- [x] Hard gates enforced on every run
- [x] Transcript JSON saved per scenario run
- [x] Documented in README and `.env.example`
- [ ] LLM transcript evaluator (Phase 3)
- [ ] Script driver removed (`live_chat_driver.py` deprecated)

---

## 14. Document map

| Question | Read |
| -------- | ---- |
| What the product must do | [Functional Document](functional-document.md) |
| Sprint gates and test pyramid | [Implementation Strategy](implementation-strategy.md) §9 |
| Local E2E (mock LLM + Wiremock) | [README](../README.md) § E2E tests |
| Live integration runbook | [README](../README.md) § Live integration tests |
