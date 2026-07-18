# Appendix A — Glossary

| Term | Definition |
| ---- | ---------- |
| **AddAttachment** | Intent to attach a file to a new or existing support ticket |
| **Agent** | AI component (LangGraph) that handles natural language conversation and proposes structured intents |
| **BFF** | Backend-for-frontend — the FastAPI API tailored for the web chat client |
| **Card** | Structured JSON attached to an assistant message for rich UI display (e.g. ticket created) |
| **CheckStatus** | Intent to search for and report on existing ticket status |
| **CreateTicket** | Intent to open a new support ticket in the help desk |
| **Deflection** | L1 resolve path where guided self-help fixes the issue and no ticket is created |
| **Docling** | Document conversion library used to turn handbook PDFs into Markdown for ingest |
| **Gateway** | `TicketGateway` — abstraction layer for help desk providers |
| **Handbook** | Agent Handbook — curated troubleshooting guide (Markdown or PDF) indexed for L1 retrieval |
| **Handbook storage** | S3-compatible object store for handbook source files (`CEPH_RGW_*`; Compose may use MinIO with a dedicated bucket) |
| **kb_admin** | Keycloak role allowed to publish and delete handbooks |
| **kb_editor** | Keycloak role allowed to upload, edit, reindex, and preview handbooks |
| **Intent** | Classified user goal (`CreateTicket`, `CheckStatus`, etc.) extracted from conversation |
| **LangGraph** | Framework for composing the AI workflow as a directed graph of nodes |
| **LLMGateway** | Provider abstraction for conversation LLMs (OpenAI, Azure OpenAI, Anthropic) |
| **Mapping** | YAML configuration translating categories to Zammad group and priority IDs |
| **MinIO** | S3-compatible object storage used for staged attachment bytes |
| **Mock LLM** | Deterministic test mode (`GRAPH_LLM_MODE=mock`) without OpenAI calls |
| **Orchestration** | Policy and workflow layer that validates intents and builds provider commands |
| **Object storage** | MinIO/S3 layer (`packages/storage`) between browser upload and Zammad |
| **PolicyValidator** | Component that checks schema, required fields, and confidence before approval |
| **Provider** | External help desk system (Zammad primary; ServiceNow stub) |
| **ProviderTicket** | Neutral ticket representation returned by the ticketing gateway |
| **Qdrant** | Vector database storing handbook chunk embeddings for retrieval |
| **Reason code** | Stable identifier for orchestration rejection with user-facing message |
| **Session** | A conversation thread between one user and the assistant |
| **SSE** | Server-Sent Events — streaming HTTP protocol used for thought streaming |
| **StructuredIntent** | JSON payload proposed by the agent describing the user's goal and fields |
| **Thought streaming** | Live display of processing step labels during graph execution |
| **Troubleshoot node** | Deterministic LangGraph node that retrieves a handbook match and guides one self-help step before CreateTicket |
| **Vision intake** | OpenAI multimodal reading of screenshot attachments during conversation |
| **TicketCommand** | Neutral command object sent to the ticketing gateway |
| **TicketGateway** | Interface implemented by provider adapters (Zammad, ServiceNow) |
| **WorkflowEngine** | Maps validated intents to `TicketCommand` using field mapping rules |
| **Zammad** | Open-source help desk platform integrated via REST API |
| **ZammadAdapter** | Ticketing gateway implementation wrapping `ZammadClient` |

## Acronyms

| Acronym | Meaning |
| ------- | ------- |
| API | Application Programming Interface |
| JWT | JSON Web Token |
| KB | Knowledge base (Agent Handbooks + retrieval) |
| LLM | Large Language Model |
| OIDC | OpenID Connect |
| RAG | Retrieval-Augmented Generation — retrieve handbook chunks, then synthesize grounded LLM guidance with citation validation |
| PII | Personally Identifiable Information |
| REST | Representational State Transfer |
| SSE | Server-Sent Events |
| SSO | Single Sign-On |
| TTL | Time To Live |
| UAT | User Acceptance Testing |
| UI | User Interface |
| UX | User Experience |
