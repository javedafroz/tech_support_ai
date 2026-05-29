# UI/UX Strategy – Tech Support AI Web Chat

## Document Control

| Item | Detail |
| ---- | ------ |
| **Related document** | [Functional Document – Tech Support AI](functional-document.md) (FSD) |
| **Channel in scope** | Web Chat only |
| **Audience** | Product, design, engineering, support operations |
| **Purpose** | Define user experience principles, patterns, and deliverables that implement the FSD with enterprise-grade usability and trust |

---

## 1. Executive Summary

Tech Support AI is a **web chat** experience where employees and customers resolve support needs through conversation while operations run on **Zammad** behind an **orchestration layer**. UX success depends on three balances:

1. **Speed vs. clarity** — Feel fast (&lt; 3s perceived response per FSD §10) without skipping confirmation on irreversible or ambiguous actions.
2. **Automation vs. trust** — Users must believe ticket numbers, status, and outcomes are real (API-grounded per FSD §9).
3. **Conversation vs. control** — Natural language in the UI; deterministic policy in the backend (FSD §3.3).

This strategy maps every in-scope FSD use case to interface patterns, states, and copy rules, and applies industry best practices for conversational support, accessibility, and enterprise compliance.

---

## 2. Strategic Alignment with the FSD

### 2.1 Experience Goals (from FSD §2)

| Business objective | UX implication |
| ------------------ | -------------- |
| Reduce manual intake | Default to conversational paths; minimize form fields unless policy requires explicit confirmation |
| Improve ticket quality | Progressive disclosure of required fields; inline validation feedback before submit |
| 24/7 availability | Clear offline/degraded modes when Zammad or AI is unavailable |
| Faster response | Streaming assistant text; optimistic UI only where safe (never for ticket IDs) |
| Better UX | Consistent tone, predictable outcomes, visible system status |

### 2.2 Architecture → Experience Layers

| FSD component | User-visible experience |
| ------------- | ------------------------ |
| Web Chat (§3.1) | Single product surface: chat shell, composer, history |
| Conversation Agent (§3.2) | Message stream, clarifying questions, summaries |
| Orchestration (§3.3) | Processing indicators, policy rejection messages, confirmation cards |
| Ticket Management + Zammad (§3.4–§9) | Ticket cards, status chips, deep links to Zammad portal (if enabled) |

Users must **never** see raw structured intents, policy rule IDs, or internal JSON unless in an admin/debug mode.

### 2.3 Out of Scope (FSD §1)

Do not design for Teams, Slack, mobile native, WhatsApp, voice, RAG/KB, or in-chat human handoff in v1. Copy may reference external escalation channels (phone, email, portal) per FSD §12.

---

## 3. Design Principles

### 3.1 Core Principles

1. **Ground truth in the UI** — Ticket numbers (`#22019`), states, groups, and priorities are shown only after Zammad/orchestration success. No placeholder ticket IDs.
2. **Progressive commitment** — Collect information conversationally; summarize and confirm before create/escalate/close.
3. **Transparent processing** — When orchestration or Zammad runs, show explicit states (“Validating…”, “Creating ticket…”), not a silent pause.
4. **Recoverable errors** — Policy rejections and API failures offer a clear next step (edit, retry, contact alternatives).
5. **Accessible by default** — WCAG 2.2 AA target; keyboard-first chat; screen-reader-friendly status announcements.
6. **Calm enterprise tone** — Professional, concise, non-anthropomorphic excess; avoid faux empathy and over-promising resolution times.

### 3.2 AI-Specific Principles (Best Practice)

| Principle | Application |
| --------- | ----------- |
| Set expectations upfront | Short disclaimer: AI assists with tickets; human support via configured channels |
| Disclose limitations | “I can create and update tickets; I can’t access systems directly.” |
| Avoid false certainty | Use “Based on your ticket #22019…” not “I’ve fixed your VPN.” |
| Human-readable failures | Map policy reason codes to plain language (FSD §13) |
| No dark patterns | Don’t hide escalation paths or make cancel/close hard to find |

---

## 4. Primary Personas & Jobs-to-be-Done

### 4.1 End User (Employee / Customer)

**Jobs:**

* Report an issue quickly without learning Zammad
* Check status without logging into another system
* Add context or files to an open ticket
* Know what happened after each action

**Pain points to design against:**

* Fear the AI “made up” a ticket
* Uncertainty during long LLM + API latency
* Ambiguity when multiple tickets match (“VPN ticket”)

### 4.2 Support Engineer (Indirect)

Not a daily chat user in v1, but benefits from:

* Higher-quality ticket titles/descriptions
* Correct group/priority from workflow rules
* Fewer duplicate tickets (orchestration duplicate checks)

**UX note:** Optional link-out to Zammad agent view for ticket `#22019` on success cards.

### 4.3 Admin

Configures policies outside the chat UI. Admin UX for policy editing is out of scope for this document except: **chat must consume reason-code → message mappings** supplied by configuration.

---

## 5. Information Architecture

### 5.1 Web Chat Shell

```text
┌─────────────────────────────────────────────┐
│ Header: Product name · Status · Help · ⋮   │
├─────────────────────────────────────────────┤
│                                             │
│  Message stream (scrollable)                │
│  - User / Assistant / System / Cards        │
│                                             │
├─────────────────────────────────────────────┤
│ Context strip (optional): Active ticket #   │
├─────────────────────────────────────────────┤
│ Composer: text · attach · send              │
│ Quick actions: New issue · My tickets       │
└─────────────────────────────────────────────┘
```

### 5.2 Entry Points

| Entry | Behavior |
| ----- | -------- |
| Embedded widget (intranet/portal) | Opens panel; preserves parent page context |
| Dedicated `/support/chat` route | Full-height chat; SSO redirect if unauthenticated |
| Deep link `?intent=status&ticket=22019` | Pre-fills context strip; assistant acknowledges ticket |

### 5.3 Session Model

* One **conversation session** maps to FSD `session_id`
* **Active ticket context** pinned in context strip when user is working on `#22019`
* **New conversation** clears active ticket unless user chooses to continue thread
* Session persistence: restore on refresh within TTL (e.g. 24h); show “Continuing your conversation from earlier today”

---

## 6. FSD Use Case → UX Patterns

### 6.1 Create Ticket (FSD §5.1)

**Flow stages in UI:**

| Stage | FSD step | UI pattern |
| ----- | -------- | ---------- |
| Intake | User describes issue | User bubble; assistant asks one clarifying question at a time (avoid question dumps) |
| Collection | Required fields | Optional **progress hint**: “2 of 3 details collected” (non-blocking) |
| Review | Structured intent → policy | **Summary card** before submit: title, description, suggested category/impact |
| Processing | Policy + workflow + API | System message + spinner: “Creating your ticket…” |
| Success | Zammad returns `number` | **Ticket created card** with `#22019`, group, priority, copy link, “Add more info” CTA |
| Failure | Policy reject | Inline explanation + “Edit details” / “Try again” |

**Summary card (best practice):**

* Editable only via conversation (“change title to …”) or explicit **Edit** that reopens field prompts—not a full form unless accessibility needs require it
* Primary CTA: **Create ticket**; secondary: **Keep chatting**

**Copy example (success):**

> Ticket **#22019** is created and assigned to **Network Support**. You’ll get updates through your usual support channels.

### 6.2 Check Status (FSD §5.2)

| Scenario | UX pattern |
| -------- | ---------- |
| Single match | **Status card**: number, state, group, owner (if available), last update time |
| Multiple matches | **Disambiguation list** (max 5): `#22019 VPN connection` · `#22004 Email sync` — tap or reply with number |
| No match | Explain scope (“I only see tickets linked to your account”) + suggest ticket number |
| Unauthorized | Neutral message; no leak of other users’ ticket existence |

**Best practice:** Make ticket numbers **copyable** and **linkable** to Zammad customer portal when configured.

### 6.3 Update Ticket (FSD §5.3)

* Confirm target ticket in context strip or disambiguation
* User provides comment; assistant echoes **preview**: “I’ll add this note to #22019: ‘…’”
* On success: **Confirmation chip** attached to thread + optional “View full history in portal”

### 6.4 Add Attachment (FSD §5.4)

| Element | Specification |
| ------- | ------------- |
| Upload control | Paperclip in composer; drag-and-drop on desktop |
| Constraints | Show max size and allowed types **before** upload (from policy config) |
| Preview | Thumbnail for images; filename + size for logs |
| Progress | Per-file progress bar; cancel supported |
| Failure | Policy rejection: “File type not allowed” with allowed list |

**Best practice:** Never auto-attach without user seeing filename in composer preview.

### 6.5 Escalate (FSD §5.5)

* Triggered by user (“escalate this”) or assistant suggestion when impact is high
* **Escalation confirmation card**: current priority → new priority, group change, what happens next
* Post-success: set expectations (“Network Support has been notified per your organization’s rules.”)

### 6.6 Cancel / Close Ticket (FSD §6 `CancelTicket`)

* Use **close** language in UI, not “delete” (FSD: no hard delete for users)
* Confirm irreversibility where org policy restricts reopening
* Success state distinct from create (muted card, checkmark)

### 6.7 Low Confidence & Unsupported (FSD §12)

| Condition | UX |
| --------- | -- |
| Low confidence | Assistant asks targeted clarification (max 2 rounds before fallback) |
| Still unresolved | **Fallback panel**: phone, email, portal links from org config |
| Critical incident | Prominent **urgent escalation** block with human channels—not buried in footer |

---

## 7. Message Types & Component Library

### 7.1 Message Taxonomy

| Type | Role | Visual |
| ---- | ---- | ------ |
| `user` | User input | End-aligned bubble |
| `assistant` | LLM natural language | Start-aligned bubble |
| `system` | Orchestration/API progress | Centered, low emphasis |
| `card` | Structured outcomes | Full-width inset panel |
| `error` | Recoverable failure | Card with warning icon + actions |

### 7.2 Cards (High-Value Components)

1. **Ticket summary (pre-create)**
2. **Ticket created / updated / escalated**
3. **Status**
4. **Disambiguation picker**
5. **Attachment preview**
6. **Fallback / contact support**

### 7.3 Orchestration-Aware States

Expose backend stages without technical jargon:

| Internal state | User-facing label |
| -------------- | ----------------- |
| Intent received | *(no message — too fast)* |
| Policy validating | “Checking your request…” |
| Workflow applying | “Applying support rules…” |
| Zammad executing | “Updating ticket…” / “Creating ticket…” |
| Policy rejected | “We couldn’t complete that request” + reason |
| Queued (Zammad down) | “Your request is queued; we’ll process it shortly.” |

**Best practice:** Combine stages if total time &lt; 500ms; show stepped progress if &gt; 2s.

### 7.4 Streaming (FSD §10)

* Stream assistant **tokens** for conversational replies
* **Do not stream** ticket numbers or status until API returns—render those as atomic card inserts
* Show **typing indicator** within 300ms of send
* If stream stalls &gt; 3s, switch to “Still working…” system line

---

## 8. Interaction & Conversation Design

### 8.1 Turn-Taking Rules

* **One primary question per assistant turn** during intake
* Batch optional questions only when user provided a rich initial message
* Use **chips** for bounded choices: “Single user / Multiple users / Not sure” (maps to FSD priority signals, not final priority text)

### 8.2 Quick Actions (Composer Accessory)

| Action | Maps to intent |
| ------ | -------------- |
| New issue | `CreateTicket` (reset context strip) |
| My tickets | `CheckStatus` (list recent) |
| Add screenshot | `AddAttachment` |
| Escalate | `EscalateIssue` (requires active ticket) |

### 8.3 Confirmation Matrix

| Action | Confirm before orchestration? |
| ------ | ------------------------------ |
| Create ticket | Yes — summary card |
| Add comment | Soft confirm (preview text) |
| Escalate | Yes |
| Close ticket | Yes |
| Check status | No |
| Upload attachment | No (if ticket context clear) |

Aligns with FSD orchestration gates and wrong-ticket mitigation (FSD §16).

### 8.4 Tone & Voice

| Do | Don’t |
| -- | ----- |
| Short sentences, active voice | Overly casual slang |
| “Your ticket #22019” | “INC-10452” (non-Zammad format) |
| Explain what the system did | Blame the user for policy blocks |
| Offer next step | Dead-end “Error occurred” |

---

## 9. Trust, Transparency & Compliance

### 9.1 Trust Signals

* **AI disclosure** in header or first visit: “Powered by AI; ticket actions are recorded in [Org] Support (Zammad).”
* **Verified badge** on cards when data source = Zammad API response timestamp
* **No hallucinated UI chrome** — hide features that aren’t built (RAG, live agent)

### 9.2 Privacy & PII

* Mask sensitive values in thread when pasted (credit cards, secrets)—warn and refuse upload per policy
* Attachment preview in client only; redact in logs (FSD §10–§11)
* Session timeout with clear “Signed out for security”

### 9.3 Policy Rejection UX

Map orchestration `reason_code` to user messages via configurable catalog:

| Example reason code | User message |
| ------------------- | ------------ |
| `MISSING_DESCRIPTION` | “Please describe what happened so we can create a ticket.” |
| `TICKET_ACCESS_DENIED` | “You don’t have access to that ticket. Try one of your open tickets below.” |
| `ATTACHMENT_TYPE_BLOCKED` | “That file type isn’t allowed. You can upload PNG, JPG, or PDF.” |
| `ESCALATION_NOT_ALLOWED` | “This ticket can’t be escalated further in chat. Contact [phone] for urgent issues.” |

Never expose internal rule names to end users (FSD §13).

---

## 10. Visual Design Direction

### 10.1 Layout & Density

* **Desktop:** 400–480px widget width or 640px centered panel; min height 560px
* **Mobile web:** Full viewport; composer fixed bottom; safe-area insets
* **Density:** Comfortable (14–16px body); adequate touch targets 44×44px

### 10.2 Color & Status Semantics

Align with Zammad state colors where possible for cognitive consistency:

| Semantic | Usage |
| -------- | ----- |
| Neutral | Open / in progress |
| Warning | Pending user action |
| Success | Created / updated |
| Critical | Escalation / outage messaging only |

### 10.3 Typography & Branding

* Inherit org design tokens (CSS variables) when embedded
* Fallback: system font stack for performance
* Monospace for ticket numbers only in cards for scannability

### 10.4 Motion

* Subtle fade-in for new messages (150–200ms)
* Respect `prefers-reduced-motion`
* No celebratory animations on ticket create (enterprise context)

---

## 11. Accessibility (WCAG 2.2 AA Target)

| Requirement | Implementation |
| ----------- | -------------- |
| Keyboard | `Enter` send, `Shift+Enter` newline, `Esc` close widget, focus trap in modal panel |
| Screen readers | `aria-live="polite"` for assistant messages; `assertive` for errors |
| Focus order | Header → stream → composer → quick actions |
| Contrast | 4.5:1 text; 3:1 UI components |
| Labels | Icon buttons have `aria-label`; attachments announce filename |
| Time limits | Session expiry warnings at 2 min and 30s |
| Cognitive load | Plain language; chunk cards; no timed dismiss on errors |

---

## 12. Responsive & Performance UX

### 12.1 Performance Budget (aligned with FSD §10)

| Metric | UX target |
| ------ | --------- |
| First contentful paint (widget) | &lt; 1.5s on corporate network |
| Time to interactive | &lt; 2.5s |
| Perceived AI reply start | &lt; 300ms typing indicator |
| End-to-end ticket create feedback | Processing state within 500ms of user confirm |

### 12.2 Degraded Modes

| Condition | UI |
| --------- | -- |
| LLM unavailable | Banner + “Submit via portal” link; optional email capture |
| Zammad unavailable | Queue message; don’t fake success |
| Partial outage | Read-only status if cache exists; block mutations |

---

## 13. Content Design & Localization Readiness

* All user-facing strings externalized (i18n keys) even if v1 is English-only (FSD: multilingual future)
* Ticket numbers formatted per locale but ID unchanged (`#22019`)
* Dates relative (“Updated 2 hours ago”) with absolute on hover
* Org-configurable: product name, support hours, fallback contacts, portal URL

---

## 14. Measurement & Success Metrics

Map UX instrumentation to FSD §17 KPIs:

| KPI | UX metric | Instrumentation |
| --- | --------- | --------------- |
| Ticket automation rate | % sessions ending in confirmed create/update without fallback | Funnel events |
| Handling time reduction | Median time from first message to ticket created | `ticket_created` − `session_start` |
| User satisfaction | Post-session CSAT (1–5) + optional comment | Throttle 30% sessions |
| First response time | Time to first assistant token | `first_token` latency |

### 14.1 Core Analytics Events

* `chat_opened`, `message_sent`, `summary_confirmed`, `ticket_created`, `status_viewed`, `attachment_uploaded`, `escalation_confirmed`, `policy_rejected`, `fallback_shown`, `session_abandoned`

### 14.2 Qualitative Research Cadence

* Baseline usability test (5 users) before beta
* Monthly review of policy rejection transcripts
* Quarterly accessibility audit

---

## 15. Security & Enterprise UX

* SSO/SAML login where required; show signed-in identity in header (supports FSD user identity)
* Copy-to-clipboard for ticket numbers logs no extra PII
* Watermark or banner on **internal** beta: “Test environment — tickets may not reach production Zammad”
* CSP-safe embedding; no third-party trackers in composer

---

## 16. Delivery Phases

### Phase 1 — MVP (align with FSD v1)

* Chat shell + message stream + composer
* Create, status, update, attachment flows with cards
* Orchestration processing states + policy error mapping
* SSO + fallback panel
* WCAG AA critical paths

### Phase 2 — Hardening

* Deep links, disambiguation polish, CSAT
* Admin-editable reason-code copy
* Advanced quick actions

### Phase 3 — Future (FSD §15)

* RAG “suggested articles” inline
* Proactive status notifications in chat
* Multilingual UI

---

## 17. Design Deliverables Checklist

| Deliverable | Owner | Notes |
| ----------- | ----- | ----- |
| User journey maps (per FSD §5) | UX | Create, status, update, escalate |
| Wireframes (desktop + mobile) | UX | Shell + cards + degraded states |
| High-fidelity UI (design system) | UX | Tokens from org brand |
| Interactive prototype | UX | Happy path + policy reject |
| Component spec in Storybook | Eng | Message types §7 |
| Copy deck + reason-code catalog | UX + Ops | §9.3 |
| Accessibility test report | UX + QA | §11 |
| Analytics spec | Product | §14 |

---

## 18. UX Risks & Mitigations (FSD Cross-Reference)

| Risk (FSD §16) | UX mitigation |
| -------------- | ------------- |
| Hallucinated ticket IDs | Cards only after API success; no streaming IDs |
| Wrong ticket selected | Disambiguation + context strip + preview |
| Incorrect classification | Show category/priority on summary card for user sanity check |
| Long latency | Stepped processing labels + streaming text |
| Low trust in AI | Disclosure + portal links + verified timestamps |

---

## 19. Reference Patterns (Best Practices Summary)

1. **Chat + cards hybrid** — Conversation for intake; cards for outcomes (Intercom, Ada, enterprise IT bots).
2. **Confirm before commit** — Especially create, escalate, close (banking and ITSM norms).
3. **Explicit system status** — Replace silent loading with labeled orchestration steps.
4. **Copyable ticket artifacts** — Reduce support repeat contacts.
5. **Graceful fallback** — Always visible path to human channels (FSD §12).
6. **Policy-as-UX-config** — Reason codes drive copy, not engineering hotfixes.
7. **Accessibility-first** — Live regions, keyboard, reduced motion.
8. **Measure perception** — CSAT + time-to-first-token, not only backend latency.

---

## 20. Conclusion

The web chat experience is the sole user-facing product of Tech Support AI in this release. UX design must reflect the FSD’s split between **conversational gathering** (Conversation Agent) and **deterministic execution** (Orchestration + Zammad), making processing visible, outcomes verifiable, and failures recoverable. Following this strategy ensures the interface meets enterprise expectations for trust, accessibility, and measurable support efficiency while remaining ready for future channels and knowledge features.

---

## Appendix A — Sample Thread Layout (Create Ticket)

```text
[Assistant] Hi — I can help you create or check support tickets.
[User]      VPN won't connect since this morning.
[Assistant] Are you seeing an error message?
[User]      Authentication failed.
[Assistant] Here's what I'll submit:
              ┌─ Summary ─────────────────────┐
              │ Title: VPN connection issue   │
              │ Impact: Single user           │
              │ [Create ticket]  [Change]     │
              └───────────────────────────────┘
[System]    Checking your request…
[System]    Creating ticket…
[Card]      ✓ Ticket #22019 created
              Network Support · Priority: High
              [Copy #] [Add details] [Portal ↗]
```

## Appendix B — Document References

| Section | FSD reference |
| ------- | ------------- |
| Use case patterns | §5.1–5.5 |
| Intents | §6 |
| Field collection | §7 |
| Classification display | §8 |
| Ticket ID format | §9 |
| Performance | §10 |
| Low confidence | §12 |
| Processing workflow | §13 |
| KPIs | §17 |
