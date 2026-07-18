# Tech Support AI Documentation

Welcome to the **Tech Support AI** documentation site — an enterprise web chat assistant that helps employees report IT issues and manage support tickets through natural conversation, integrated with **Zammad** and other help desk platforms.

## Start here

| I want to… | Go to |
| ---------- | ----- |
| Run the product locally | [Quick Start](external/00-quick-start.md) |
| Understand business value | [Executive Solution Overview](external/01-executive-solution-overview.md) |
| Review architecture | [Solution Architecture](external/03-solution-architecture.md) |
| Connect Zammad | [Zammad Integration Guide](external/05-integration-guide-zammad.md) |
| Integrate via REST | [API Overview](external/07-api-overview.md) |
| Plan UAT | [Test & Acceptance](external/09-test-and-acceptance.md) |

## What is Tech Support AI?

Employees describe problems in plain language. When enabled, the agent retrieves Agent Handbook chunks and synthesizes adaptive grounded self-help guidance (classic RAG); if that does not resolve the issue, it creates a ticket. A **deterministic orchestration layer** validates every ticket operation before it reaches the help desk.

```text
User (web chat) → FastAPI (ChatService) → LangGraph
  conversation → troubleshoot (KB/RAG when enabled) → orchestrate → ticket_tool → respond
                     ↕ PostgreSQL · Redis · MinIO · Qdrant
```

The language model runs in the `conversation` node (intent/slots) and in `troubleshoot` (grounded RAG presentation). Handbook retrieval, citation validation, policy, mapping, and ticket execution remain deterministic Python — not prompt instructions.

## Document sets

This site hosts the **external** documentation pack (safe to share with customers and partners). For the full index, see [Documentation Index](external/README.md).

## Related resources

| Resource | Location |
| -------- | -------- |
| Interactive API docs (Swagger) | `http://localhost:8000/docs` when the API is running |
| Postman collection | [Postman Collection](postman.md) |
| Example configuration | `.env.example` in the repository root |
| Zammad field mapping | `config/providers/zammad/mapping.yaml` |

## Capability snapshot

| Capability | Status |
| ---------- | ------ |
| Web chat with session resume | Available |
| Create ticket end-to-end | Available |
| Check ticket status | Available |
| L1 handbook troubleshoot (KB/RAG) | Available (`KB_RAG_ENABLED`) |
| Admin KB (upload / publish handbooks) | Available — core module |
| Thought streaming (processing panel) | Available |
| Multi-provider LLM (OpenAI, Azure, Anthropic) | Available |
| File attachments (upload → Zammad) | Available |

See the [Capability Matrix](external/appendices/C-capability-matrix.md) for the full list.
