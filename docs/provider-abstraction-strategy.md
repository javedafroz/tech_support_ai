# Provider Abstraction Strategy – Ticketing Platform Agnostic Architecture

## 1. Purpose

This strategy defines how to decouple Tech Support AI from direct Zammad dependencies so that additional ticket providers (for example ServiceNow, Jira Service Management, Freshservice) can be plugged in with minimal changes.

The plan is incremental: preserve current behavior first, then introduce interfaces and adapters, then migrate orchestration and graph execution to provider-neutral contracts.

---

## 2. Current Coupling Analysis

Today, provider coupling is concentrated in three places:

1. `packages/agents/src/tech_support_agents/nodes/zammad_tool.py`
   - Node is explicitly named around Zammad.
   - Builds `ZammadClient` directly from env vars.
   - Accepts only `ZammadCommandType.CREATE_TICKET`.

2. `packages/orchestration/src/tech_support_orchestration/models.py`
   - Uses `ZammadCommand` and `ZammadCommandType` in domain models.
   - Makes orchestration provider-specific by type name.

3. `packages/orchestration/src/tech_support_orchestration/workflow.py`
   - Imports Zammad DTOs (`CreateTicketRequest`, `TicketArticleInput`).
   - Produces payloads shaped to Zammad API fields (`group`, `priority`, `customer_id`, `article`).

Additional coupling exists in naming and config (`zammad-field-mapping.yaml`, env vars `ZAMMAD_*`, docs/tests importing `tech_support_zammad`).

---

## 3. Target Architecture

Introduce a **provider abstraction layer** between orchestration and concrete helpdesk APIs.

```text
Conversation LLM (LangGraph conversation node)
  -> StructuredIntent
  -> Orchestration (provider-neutral policy + workflow)
  -> TicketCommand (provider-neutral)
  -> TicketGateway (interface)
      -> ZammadAdapter (current)
      -> ServiceNowAdapter (future)
      -> JiraSMAdapter (future)
  -> ProviderTicketResult (normalized)
  -> respond node + UI cards
```

### Design principles

- Keep policy rules provider-neutral.
- Keep graph state and UI cards provider-neutral.
- Push provider field mapping into adapters.
- Preserve current Zammad behavior while introducing abstraction.
- Allow runtime provider selection (default Zammad).

---

## 4. Proposed Core Contracts

Create a new package (recommended): `packages/ticketing/`.

### 4.1 Provider-neutral command model

- `TicketCommandType`: `CREATE_TICKET`, `SEARCH_TICKETS`, `GET_TICKET`, `ADD_COMMENT`, `ADD_ATTACHMENT`, `ESCALATE`, `CLOSE`.
- `TicketCommand`: `type`, `session_id`, `user_id`, `idempotency_key`, `payload`, `provider_hint` (optional).

### 4.2 Provider capability model

- `ProviderCapabilities`:
  - `supports_attachments`
  - `supports_escalation`
  - `supports_close`
  - `supports_status_search`
  - optional limits (`max_attachment_size_mb`, etc.)

### 4.3 Normalized response model

- `ProviderTicket`
  - `provider`
  - `external_id`
  - `display_number` (what UI shows as ticket number/key)
  - `state`
  - `group_or_queue`
  - `priority`
  - `url` (optional)
  - `raw` (provider-specific payload snapshot)

- `TicketOperationResult`
  - `success`
  - `ticket` (optional)
  - `items` (for search)
  - `error_code`
  - `error_message`
  - `retryable`

### 4.4 Gateway interface

- `TicketGateway` (protocol/abstract class):
  - `create_ticket(command) -> TicketOperationResult`
  - `search_tickets(command) -> TicketOperationResult`
  - `get_ticket(command) -> TicketOperationResult`
  - `add_comment(command) -> TicketOperationResult`
  - `add_attachment(command) -> TicketOperationResult`
  - `escalate(command) -> TicketOperationResult`
  - `close_ticket(command) -> TicketOperationResult`
  - `healthcheck() -> bool`
  - `capabilities() -> ProviderCapabilities`

---

## 5. Adapter and Factory Pattern

### 5.1 Adapter implementations

- `ZammadAdapter` wraps existing `tech_support_zammad.ZammadClient`.
- Future adapters map neutral command payloads to provider-specific API DTOs.

### 5.2 Provider factory

- `TicketGatewayFactory.from_settings(...) -> TicketGateway`
- Provider selected via env:
  - `TICKETING_PROVIDER=zammad|servicenow|jira_sm`
- Provider-specific env namespaces:
  - `ZAMMAD_*`
  - `SERVICENOW_*`
  - `JIRASM_*`

### 5.3 Mapping profiles

Replace `zammad-field-mapping.yaml` with provider-scoped mappings:

- `config/providers/zammad/mapping.yaml`
- `config/providers/servicenow/mapping.yaml`
- `config/providers/jira_sm/mapping.yaml`

Keep canonical category/priority in neutral form and map in adapter layer.

---

## 6. Migration Plan (Phased, Low Risk)

## Phase 0 – Stabilize naming and test baseline (1-2 days)

- Add regression tests for current CreateTicket flow.
- Freeze current response contract in tests (`ticket_created` card behavior).
- Document exact behavior parity requirements.

**Exit criteria**
- Existing tests green and tagged as baseline.

## Phase 1 – Introduce neutral models alongside existing ones (2-3 days)

- Add `TicketCommand` and `TicketCommandType` in new package.
- Keep `ZammadCommand` for backward compatibility (temporary).
- Add converter helpers between old and new command models.

**Exit criteria**
- No runtime behavior changes.
- New neutral model tested.

## Phase 2 – Introduce gateway interface + Zammad adapter (3-4 days)

- Implement `TicketGateway` and `ZammadAdapter`.
- Implement `TicketGatewayFactory`.
- Move env parsing for provider credentials from node into adapter/factory.

**Exit criteria**
- CreateTicket works through `ZammadAdapter` path.
- `zammad_tool` no longer instantiates `ZammadClient` directly.

## Phase 3 – Replace graph node with provider-neutral executor (2-3 days)

- Replace `zammad_tool_node` with `ticket_tool_node`.
- Route approved commands to `TicketGateway`.
- Keep emitted `ui_card` unchanged for compatibility.

**Exit criteria**
- Graph tests pass with same user-visible behavior.
- Node naming and internal state no longer Zammad-specific.

## Phase 4 – Refactor orchestration to emit neutral commands (3-5 days)

- Rename `ZammadCommand` -> `TicketCommand` in orchestration models.
- Remove direct imports of `tech_support_zammad` from workflow.
- Workflow produces canonical payload (provider-neutral fields only).

**Exit criteria**
- `packages/orchestration` has zero imports from `tech_support_zammad`.
- Provider mapping done in adapter layer.

## Phase 5 – Config and ops abstraction (2-3 days)

- Add `TICKETING_PROVIDER` and provider-specific settings classes.
- Move mapping file path resolution to provider config structure.
- Update health/readiness to call active provider `healthcheck()`.

**Exit criteria**
- Runtime can switch providers by config (even if only Zammad adapter exists).

## Phase 6 – Expand command coverage and capabilities (incremental)

- Implement neutral handlers for:
  - `SEARCH_TICKETS` / `GET_TICKET`
  - `ADD_COMMENT`
  - `ADD_ATTACHMENT`
  - `ESCALATE`
  - `CLOSE`
- Use `ProviderCapabilities` to gate unsupported operations gracefully.

**Exit criteria**
- Unsupported actions return deterministic policy/user messages, not runtime errors.

---

## 7. File-Level Change Strategy

### Immediate files to touch first

- `packages/agents/src/tech_support_agents/nodes/zammad_tool.py`
  - Rename and replace with provider-neutral executor.
- `packages/agents/src/tech_support_agents/graph.py`
  - Rename node references from `zammad_tool` to `ticket_tool`.
- `packages/orchestration/src/tech_support_orchestration/models.py`
  - Introduce neutral command type aliases (temporary bridge).
- `packages/orchestration/src/tech_support_orchestration/workflow.py`
  - Remove direct Zammad DTO dependence; produce canonical payload.
- `apps/api/src/tech_support_api/config.py`
  - Add provider selection settings.
- `docs/solution-architecture.md`
  - Update with neutral layer once phase 3 is complete.

### New files to introduce

- `packages/ticketing/src/tech_support_ticketing/models.py`
- `packages/ticketing/src/tech_support_ticketing/gateway.py`
- `packages/ticketing/src/tech_support_ticketing/factory.py`
- `packages/ticketing/src/tech_support_ticketing/providers/zammad_adapter.py`
- `config/providers/zammad/mapping.yaml`

---

## 8. Backward Compatibility and Rollout

Use a feature flag:

- `TICKETING_ABSTRACTION_ENABLED=false` (default initially)
- When true, graph uses `ticket_tool_node` + gateway.

Rollout sequence:

1. Deploy with flag off.
2. Enable in dev.
3. Run existing integration suite (`make test`, `make e2e`, `make test-live`).
4. Enable in staging.
5. Enable in production.

Keep old path for one release window, then remove.

---

## 9. Test Strategy for Abstraction

### 9.1 Unit tests

- Contract tests for `TicketGateway` behavior.
- Adapter tests:
  - neutral command -> provider request mapping
  - provider response -> normalized `ProviderTicket`
- Factory tests for provider selection and missing credentials.

### 9.2 Integration tests

- Graph test with fake gateway (no provider dependency).
- Orchestration tests verify neutral commands only.
- API tests verify unchanged response shape.

### 9.3 Live tests

- Reuse existing Zammad live suite via `ZammadAdapter`.
- Add one provider-agnostic acceptance test suite to validate behavior contract independent of provider-specific payload keys.

---

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Scope creep during abstraction | Delays feature delivery | Phased migration with strict parity goals |
| Breaking existing ticket flow | Production regression | Feature flag + golden-path regression tests |
| Neutral model too generic | Leaky abstractions | Define canonical fields around actual use cases; allow `raw` extensions |
| Provider-specific policy divergence | Inconsistent behavior | Keep policy engine neutral; adapter handles provider mapping only |
| Naming churn across codebase | Developer confusion | Temporary aliases, migration guide, single rename phase |

---

## 11. Recommended Execution Order (Practical)

1. Build `packages/ticketing` contracts + `ZammadAdapter`.
2. Replace graph node with `ticket_tool_node` through factory.
3. Convert orchestration output from `ZammadCommand` to neutral `TicketCommand`.
4. Move mapping config to provider-specific directory.
5. Add second provider adapter stub (even partial) to validate abstraction quality.

This order gives fast architectural payoff with low delivery risk and preserves your existing Zammad functionality.

---

## 12. Definition of Done

The abstraction strategy is complete when:

- No direct `tech_support_zammad` imports remain in `packages/agents` and `packages/orchestration` (adapter package only).
- Graph node names and state are provider-neutral (`ticket_tool`, `provider_response`).
- Runtime provider can be selected by config without code changes.
- Existing Zammad behavior and UI output remain unchanged.
- Test suite passes with abstraction enabled.
- At least one non-Zammad adapter skeleton can run through factory wiring.

