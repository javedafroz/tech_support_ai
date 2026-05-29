# Functional Document – Tech Support AI for Ticket Management with Zammad

## 1. Document Overview

### Purpose

This document defines the functional requirements, workflow, architecture, and integration behavior for the **Tech Support AI** solution. The system enables users to interact with an AI-powered chat assistant to:

* Create support tickets
* Check ticket status
* Update existing tickets
* Add comments or attachments
* Receive troubleshooting guidance
* Escalate issues when necessary

The AI solution integrates with the help desk platform Zammad.

### Scope

**In scope**

* Web Chat as the user interaction channel
* Conversational AI for intake and ticket operations
* **Orchestration layer** with deterministic policy validation and workflow rules (between AI and Zammad)
* Zammad REST API integration for ticket lifecycle actions

**Out of scope (this release)**

* Microsoft Teams, Slack, mobile app, and WhatsApp as inbound chat channels
* Voice assistant
* Knowledge base / RAG layer (planned as a future enhancement)

---

## 2. Business Objective

The objective of the solution is to:

* Reduce manual effort in support intake
* Improve ticket quality and categorization
* Provide 24/7 support interaction via web chat
* Reduce response times
* Automate repetitive support operations
* Improve user experience through conversational AI

---

## 3. High-Level Solution Architecture

### Components

#### 3.1 User Interface

Channel through which users communicate with the AI:

* **Web Chat** (primary and only channel for this release)

#### 3.2 AI Conversation Agent (Frontline AI)

Responsibilities:

* Understand user intent
* Ask clarifying questions
* Extract ticket details
* Collect mandatory information (conversational validation only—not business policy)
* Produce **structured intent** and payload proposals (JSON schema)
* Detect urgency and sentiment (signals passed downstream; not authoritative for policy)
* Route requests to the orchestration layer

This agent acts as the primary conversational layer. It must **not** embed enterprise business rules, escalation policy, or Zammad field mappings in prompts.

#### 3.3 Orchestration Layer (Policy / Workflow Engine)

Sits between the AI agents and Zammad. All ticket operations pass through this layer before any API call is made.

**Recommended control flow:**

```text
LLM (Conversation Agent)
  ↓
Structured Intent
  ↓
Policy Validator
  ↓
Workflow Rules
  ↓
Ticket Management Agent (approved commands only)
  ↓
Integration Layer
  ↓
Zammad API
```

**Responsibilities:**

* Accept structured intents from the Conversation Agent (`CreateTicket`, `CheckStatus`, etc.)
* **Policy Validator** — schema validation, required fields, allowed values, user authorization scope, attachment limits, rate limits per user/session
* **Workflow Rules** — deterministic business logic: priority/category/group mapping, escalation triggers, allowed state transitions, duplicate-ticket checks, security-incident routing
* Approve, modify, or **reject** operations with explicit reason codes (for audit and user-facing messages)
* Emit approved **commands** to the Ticket Management Agent (never raw LLM output)
* Record policy decisions for audit (input intent, rule matched, outcome)

**Why this matters at enterprise scale:**

| Capability | Benefit |
| ---------- | ------- |
| Validates fields | Blocks incomplete or malformed payloads before Zammad |
| Enforces escalation policy | VIP, security, and outage rules applied consistently |
| Prevents invalid transitions | e.g. cannot close another user’s ticket; cannot skip states |
| Blocks dangerous operations | Deletes, cross-customer access, privilege escalation |
| Enables auditability | Every Zammad call traceable to a policy decision |
| Removes business logic from prompts | LLM focuses on language; policies are versioned and testable |

Policy and workflow definitions are maintained as **configuration** (YAML/JSON rules engine or workflow DSL), not as ad hoc prompt instructions. Changes require admin review and do not require model retraining.

#### 3.4 Ticket Management Agent

Responsibilities:

* Execute **only orchestration-approved commands** against Zammad
* Map approved payloads to Zammad API contracts (field names, `customer_id`, groups, priorities)
* Create tickets, retrieve status, update tickets, add articles, attach files
* Return API results to the orchestration layer (and then to the Conversation Agent for natural-language response)

This agent is a **thin executor**: no business policy, no escalation logic, no field-mapping heuristics. All ticket identifiers returned to users must come from Zammad API responses (for example, ticket `number` such as `22019`).

#### 3.5 Integration Layer

Responsibilities:

* Zammad API client (HTTP, auth headers)
* Authentication handling for the service account
* Retry handling and circuit breaking
* Error normalization (Zammad errors → orchestration error codes)
* Rate limiting against Zammad

Logging of user-facing audit events is owned by the orchestration layer; this layer provides technical request/response logging.

#### 3.6 Knowledge Base / RAG Layer (Optional Future Enhancement)

Responsibilities:

* Provide troubleshooting guidance
* Search FAQs
* Suggest known fixes
* Reduce unnecessary ticket creation

---

## 4. Actors

| Actor                   | Description                                                     |
| ----------------------- | --------------------------------------------------------------- |
| End User                | Employee or customer seeking support                            |
| AI Conversation Agent   | Conversational AI; produces structured intents only             |
| Orchestration Layer     | Policy validator and workflow engine; gates all ticket ops      |
| Ticket Management Agent | Executes approved Zammad API commands                           |
| Support Engineer        | Human support staff working in Zammad                           |
| Admin                   | System administrator; configures policies and workflow rules  |

---

## 5. Functional Use Cases

### 5.1 Create Support Ticket

#### Description

User reports a technical issue through web chat. The AI gathers required information and creates a ticket in Zammad.

#### Preconditions

* User is authenticated (optional depending on deployment)
* Zammad API is available

#### Main Flow

**Step 1 – User Initiates Conversation**

Example:

> “My VPN is not connecting.”

**Step 2 – AI Understands Intent**

Intent identified: **Create Ticket**

**Step 3 – AI Collects Required Information**

AI asks for:

* Issue description
* Device/system affected
* Error message
* Impact/severity
* Screenshots/logs (optional)

**Step 4 – AI Produces Structured Intent**

Example structured intent (proposed by LLM; not yet authoritative):

```json
{
  "intent": "CreateTicket",
  "confidence": 0.92,
  "payload": {
    "title": "VPN connection issue",
    "description": "User unable to connect to VPN since morning",
    "suggested_priority": "high",
    "suggested_category": "Network",
    "customer_email": "john.doe@company.com",
    "attachments": [
      { "filename": "vpn_error.png", "mime_type": "image/png" }
    ]
  }
}
```

**Step 5 – Orchestration: Policy Validator**

* Validate schema and required fields (`title`, `description`, `customer_email`)
* Verify user is allowed to create tickets for the given customer identity
* Validate attachment count, size, and MIME allow-list
* Reject or request clarification if validation fails (reason code returned to Conversation Agent)

**Step 6 – Orchestration: Workflow Rules**

* Map `suggested_category` → Zammad custom object key (e.g. `category_network`)
* Map impact/sentiment → allowed Zammad priority (e.g. `3 high`)
* Assign `group` per routing rules (e.g. Network → `Network Support`)
* Apply escalation pre-checks (e.g. security keywords → security group + high priority)
* Emit approved command, e.g. `CreateTicketCommand`

**Step 7 – Ticket Management Agent Executes in Zammad**

Approved command only:

* `POST /api/v1/tickets` with Zammad-native field values
* Initial article and optional attachments

**Step 8 – Confirmation to User**

Example (using Zammad ticket number from API response):

> “Your support ticket **#22019** has been created successfully.”

#### Alternative Flow – AI Cannot Understand Issue

* AI requests clarification
* If confidence remains low after repeated attempts, AI informs the user that the request could not be processed automatically and advises contacting support through standard channels (email/phone as configured by the organization)

#### Postconditions

* Ticket exists in Zammad
* User receives the Zammad ticket number

---

### 5.2 Get Ticket Status

#### Description

User requests the status of an existing ticket.

#### Main Flow

**User Query**

> “What is the status of my VPN ticket?”

**AI Actions**

1. Produce structured intent `CheckStatus` with user identity and search hints
2. Orchestration validates user scope (customer may only query own tickets)
3. Orchestration approves search/read workflow; Ticket Management Agent calls Zammad search/show APIs
4. If multiple matches, Conversation Agent disambiguates (confirm ticket number or title)
5. Return summarized status from API-grounded data only

**Example Response**

> “Your ticket **#22019** is currently assigned to the Network Support group and is **open**.”

---

### 5.3 Update Existing Ticket

#### Description

User provides additional information for an existing ticket.

#### Main Flow

**User Query**

> “Please add that the issue happens only on Wi-Fi.”

**AI Actions**

1. Produce structured intent `UpdateTicket` with ticket reference and comment body
2. Orchestration verifies ticket ownership/access and ticket state (e.g. not closed if updates disallowed)
3. Workflow rules select allowed operation (`AddComment` vs `UpdateTicket`)
4. Ticket Management Agent executes approved Zammad API call
5. Confirm update completion

**Example Update Payload**

```json
{
  "ticket_id": 19,
  "comment": "Issue occurs only when connected via Wi-Fi."
}
```

---

### 5.4 Add Attachment to Ticket

#### Description

User uploads screenshot or log files in web chat.

#### Flow

1. User uploads file in chat
2. Conversation Agent attaches file reference to structured intent `AddAttachment`
3. Orchestration enforces file type, size, and per-ticket attachment limits
4. On approval, Ticket Management Agent uploads via ticket article API (base64 in `attachments` array)
5. AI confirms attachment success

---

### 5.5 Escalate Ticket

#### Description

AI identifies critical incidents or user escalation requests and raises severity in Zammad.

#### Escalation Triggers

* VIP user (from external identity/HR attribute if integrated)
* Production outage (keywords / impact classification)
* Security incident
* High sentiment negativity
* Multiple failed resolution attempts in the same session

#### Actions

* Conversation Agent emits `EscalateIssue` structured intent with signals (VIP, keywords, sentiment score)
* **Workflow rules** determine allowed priority bump, group reassignment, and mandatory fields (e.g. security incidents require category = Security)
* Policy validator blocks invalid escalations (e.g. user cannot set critical priority without matching rule)
* Ticket Management Agent applies approved `PUT /api/v1/tickets/{id}` changes only
* Zammad triggers handle notifications to support staff (email and in-app per Zammad configuration)

---

## 6. Intent Recognition

### Supported Intents

The Conversation Agent outputs a **structured intent** document for each actionable turn. The orchestration layer maps intents to workflow definitions.

| Intent        | Description                    | Orchestration gate                          |
| ------------- | ------------------------------ | ------------------------------------------- |
| CreateTicket  | Create new support issue       | Field validation + routing rules            |
| CheckStatus   | Retrieve ticket status         | User scope + ticket access                  |
| UpdateTicket  | Add/update ticket details      | State transition rules + ownership          |
| AddAttachment | Upload supporting files        | File policy + ticket access                 |
| EscalateIssue | Raise severity                 | Escalation policy matrix                    |
| CancelTicket  | Close ticket (state change)    | Allowed close states; no hard delete        |

Intents with `confidence` below threshold are not forwarded to Zammad; the Conversation Agent clarifies or falls back per §12.

Low-confidence or unsupported requests are handled by clarification prompts and, when unresolved, by directing the user to organization-defined support channels—not by a dedicated in-chat handoff workflow in this release.

### Structured Intent Schema (minimum)

| Field        | Description                                      |
| ------------ | ------------------------------------------------ |
| `intent`     | One of the supported intent names                |
| `confidence` | Model confidence score (0–1)                     |
| `session_id` | Web chat session identifier                      |
| `user_id`    | Authenticated user identity                      |
| `payload`    | Intent-specific fields (proposed, not authoritative) |
| `timestamp`  | ISO 8601 time of emission                        |

Authoritative field values for Zammad are produced only **after** policy validation and workflow rules run.

---

## 7. AI Conversation Requirements

### Natural Language Understanding

The AI must:

* Understand conversational language
* Handle incomplete requests
* Detect sentiment
* Maintain conversational context across the web chat session

Multilingual support is a future enhancement.

### Context Collection Rules

The Conversation Agent collects the following before emitting `CreateTicket`. **Enforcement** of required fields is performed by the orchestration Policy Validator (not by the LLM alone).

| Field         | Required (policy) | Collected by |
| ------------- | ----------------- | ------------ |
| Issue summary | Yes               | Conversation Agent → Policy Validator |
| Description   | Yes               | Conversation Agent → Policy Validator |
| User identity | Yes               | Auth session → Policy Validator |
| Priority      | Optional          | Workflow rules may override LLM suggestion |
| Category      | Optional          | Workflow rules map to Zammad custom fields |
| Attachment    | Optional          | Policy Validator (type/size/count) |

---

## 8. Ticket Classification Logic

### Categories

Categories are stored as **Zammad custom ticket objects** (configured in Admin → Objects). Example taxonomy:

* Hardware
* Software
* Network
* Access Management
* Email
* Security
* Infrastructure

The **orchestration workflow rules** map validated inputs to Zammad internal field names and allowed enum values. The Ticket Management Agent applies the approved mapping only.

### Priority Mapping

| User Sentiment / Impact | Zammad Priority (example) |
| ----------------------- | ------------------------- |
| Minor inconvenience     | 1 low                     |
| Single user blocked     | 2 normal                  |
| Multiple users impacted | 3 high                    |
| Production outage       | 3 high (or org-specific critical priority) |

Exact priority labels must match the Zammad instance configuration.

---

## 9. Integration with Zammad

### APIs Used

| Operation           | API                                              |
| ------------------- | ------------------------------------------------ |
| Create Ticket       | `POST /api/v1/tickets`                           |
| Get Ticket          | `GET /api/v1/tickets/{id}`                       |
| Search Tickets      | `GET /api/v1/tickets/search?query={query}`         |
| Update Ticket       | `PUT /api/v1/tickets/{id}`                       |
| Add Article/Comment | `POST /api/v1/ticket_articles`                   |
| Upload Attachment   | Via `attachments` on ticket article create/update |

### Authentication

Recommended options (per Zammad documentation):

* API token (HTTP `Authorization: Token token=...` or Bearer for OAuth2)
* OAuth 2.0 access token
* Dedicated service account with `ticket.agent` for create-on-behalf flows

### Ticket Identifiers

* **Internal ID**: numeric `id` used in API paths (e.g. `19`)
* **User-facing number**: Zammad `number` field (e.g. `22019`)—displayed to users as `#22019`
* The system must never fabricate ticket numbers; only values returned by Zammad may be shown

### Error Handling

| Scenario               | Action                  |
| ---------------------- | ----------------------- |
| API timeout            | Retry with backoff      |
| Authentication failure | Alert admin             |
| Policy rejection       | Return reason code to Conversation Agent; no Zammad call |
| Invalid payload        | Caught by Policy Validator before API |
| Zammad unavailable     | Queue approved commands and retry |

---

## 10. Non-Functional Requirements

### Performance

* AI response time: target &lt; 3 seconds for simple turns (streaming UI recommended for longer operations)
* Ticket creation (Zammad API only): target &lt; 5 seconds

### Availability

* 99.9% uptime target for the Tech Support AI platform (excluding third-party LLM and Zammad SLAs)

### Security

* TLS encryption for all traffic
* Role-based access to admin and integration configuration
* Audit logging of ticket actions and API calls
* PII masking in logs where feasible
* Secure credential storage (secrets manager or equivalent)

### Scalability

* Support concurrent web chat sessions
* Horizontal scaling for Conversation Agent, **orchestration layer**, and Ticket Management Agent
* Stateless policy evaluation where possible; versioned policy configuration in central store
* Persistent session store for conversation context

---

## 11. Audit & Logging

The system must log:

* User interactions (session-scoped)
* Structured intents emitted by the Conversation Agent
* **Policy decisions** (rule id, input, approve/reject/modify, reason code)
* **Workflow rule applications** (e.g. priority mapped from impact table)
* Approved commands sent to the Ticket Management Agent
* Zammad API requests and responses (sanitized)
* Escalation events
* Failed operations and retries

Policy and workflow configuration changes must be auditable (who changed what, when).

---

## 12. Low-Confidence and Unsupported Requests

### Conditions

* AI confidence below threshold after clarification attempts
* Unsupported request type
* Critical incident requiring immediate human attention (user directed to org escalation path)

### Flow

1. AI summarizes what was understood
2. AI explains that the action could not be completed automatically
3. User is directed to configured alternatives (e.g. phone, email, or existing Zammad portal)—no embedded live-agent chat handoff in this release

---

## 13. End-to-End Processing Workflow

```text
User (Web Chat)
  ↓
Conversation AI Agent (LLM)
  ↓
Structured Intent
  ↓
Orchestration Layer
  ├── Policy Validator
  └── Workflow Rules
  ↓
Approved Command (or Rejection + reason code)
  ↓
Ticket Management Agent
  ↓
Integration Layer
  ↓
Zammad API
  ↓
API Result
  ↓
Conversation AI Agent (natural-language response)
  ↓
User
```

Rejected operations never reach Zammad. The Conversation Agent translates policy reason codes into user-appropriate messages without exposing internal rule identifiers unless configured for support staff.

---

## 14. Sample Conversation Flow

### Ticket Creation Example

**User**

> My laptop cannot connect to the company VPN.

**AI**

> I can help with that. When did the issue start?

**User**

> Since this morning.

**AI**

> Are you receiving any error message?

**User**

> Authentication failed.

**AI**

> Thank you. I’m creating a support ticket now.

**AI**

> Your ticket **#22019** has been created successfully.

---

## 15. Future Enhancements

* Voice support
* Auto-remediation workflows
* Integration with ServiceNow/Jira
* Knowledge base / RAG for AI-generated troubleshooting steps
* Predictive incident detection
* SLA prediction
* Sentiment analytics dashboard
* Additional inbound channels (Teams, Slack, mobile, WhatsApp) if required later
* Multilingual conversations

---

## 16. Risks & Considerations

| Risk                        | Mitigation                                      |
| --------------------------- | ----------------------------------------------- |
| Incorrect AI classification | Workflow rules + policy overrides; human review in Zammad |
| Business logic drift in LLM | Policies externalized; prompts must not encode rules      |
| Hallucinated responses      | Orchestration blocks unapproved ops; API-grounded IDs only  |
| Wrong ticket selected       | Access checks in Policy Validator; user confirmation in chat |
| Policy bypass attempt       | Ticket Management Agent accepts signed/approved commands only |
| Security concerns           | RBAC, encryption, least-privilege API tokens              |
| API dependency failures     | Retry queue for approved commands; dead-letter handling   |

---

## 17. Success Metrics

| KPI                             | Target    |
| ------------------------------- | --------- |
| Ticket automation rate          | > 70%     |
| Average handling time reduction | 40%       |
| User satisfaction               | > 85%     |
| First response time (chat)      | < 1 minute |

---

## 18. Conclusion

The Tech Support AI solution provides a **web chat** interface for automated support operations integrated with Zammad. The architecture separates **conversational intelligence** (LLM), **deterministic enterprise control** (orchestration layer with policy validation and workflow rules), and **transactional execution** (Ticket Management Agent + Integration Layer). This separation enables auditability, safe scaling at enterprise level, and maintainable business rules without embedding them in prompts. Channel scope is limited to web chat; ticket references align with Zammad; multi-channel intake and in-chat human handoff remain future phases.
