# Tech Support AI — External Documentation

This folder contains customer- and partner-facing documentation for **Tech Support AI**: an enterprise web chat assistant integrated with help desk platforms (Zammad today; additional providers via adapter).

## Document index

| # | Document | Audience | Purpose |
| - | -------- | -------- | ------- |
| 00 | [Quick Start](00-quick-start.md) | Evaluators, developers, DevOps | Full stack via Docker Compose |
| 01 | [Executive Solution Overview](01-executive-solution-overview.md) | Sponsors, product, procurement | Business value, scope, capability summary |
| 02 | [Functional Specification Summary](02-functional-specification-summary.md) | Product, support ops, architects | Use cases, intents, workflows |
| 03 | [Solution Architecture](03-solution-architecture.md) | Enterprise architects, engineering leads | Components, data flow, design principles |
| 04 | [Security & Data Handling](04-security-and-data-handling.md) | Security, compliance, InfoSec | Auth, secrets, PII, audit |
| 05 | [Zammad Integration Guide](05-integration-guide-zammad.md) | Zammad admins, integrators | Sandbox setup, mapping, API credentials |
| 06 | [Deployment & Operations](06-deployment-and-operations.md) | Platform engineers, SRE | Docker, health checks, runbook basics |
| 07 | [API Overview](07-api-overview.md) | Developers, integrators | REST endpoints, auth, contracts |
| 08 | [UI/UX Overview](08-ui-ux-overview.md) | Product, design, support ops | Chat experience, cards, principles |
| 09 | [Test & Acceptance](09-test-and-acceptance.md) | QA, customer UAT | Test approach and acceptance scenarios |

### Appendices

| Appendix | Document |
| -------- | -------- |
| A | [Glossary](appendices/A-glossary.md) |
| B | [Environment Variables](appendices/B-environment-variables.md) |
| C | [Capability Matrix](appendices/C-capability-matrix.md) |

## Related artifacts (repository)

- **Documentation site:** `make docs` or `docker compose up -d docs` → http://localhost:8088
- Interactive API docs: `http://localhost:8000/docs` (when API is running)
- Postman collection: [Postman guide](../postman.md)
- Provider mapping (Zammad): `config/providers/zammad/mapping.yaml` (repository root)
- Example configuration: `.env.example` (repository root)
- Admin SPA (handbook KB): `apps/admin` — `make admin` → http://localhost:5174
- Sample handbooks: `config/knowledge/`
- Seed handbooks into Qdrant: `make seed-kb`

## Internal engineering docs

Detailed sprint plans and internal strategy documents may live alongside this pack in the repository. Partners with repository access can read the deep-dive strategy at [KB/RAG L1 Agent Strategy](../kb-rag-l1-agent-strategy.md). External readers should start with this [Documentation Index](README.md).

## Document control

| Item | Detail |
| ---- | ------ |
| **Version** | 1.3.1 |
| **Last updated** | 2026-07-17 |
| **Classification** | External — safe to share with customers and partners (no secrets) |
