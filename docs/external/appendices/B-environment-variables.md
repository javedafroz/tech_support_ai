# Appendix B — Environment Variables

Reference for operators and integrators. Copy `.env.example` to `.env` for local development. **Never commit secrets.**

## API server

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | HTTP port |
| `API_ENV` | `development` | `development` enables reload |
| `CORS_ORIGINS` | JSON list (Settings default includes `:5173` / `:5174`) | Allowed browser origins for chat + admin |

## Database

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `DATABASE_URL` | Yes | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_SYNC` | Yes | Sync URL for Alembic migrations |

## Redis

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `REDIS_URL` | — | Redis connection URL |
| `REDIS_SESSION_TTL_SECONDS` | `86400` | Session cache TTL (24 hours) |

## Authentication

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `AUTH_MODE` | `dev` | `dev` or `jwt` |
| `AUTH_DEV_HEADER_USER_ID` | `X-User-Id` | Header name for dev user ID |
| `AUTH_JWT_SECRET` | — | HMAC secret for JWT validation |
| `AUTH_JWT_AUDIENCE` | — | Optional JWT audience claim |

## LangGraph / LLM

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `GRAPH_ENABLED` | `false` *(API Settings)* / `true` in `.env.example` | Enable LangGraph pipeline; set `true` for real agent flow |
| `GRAPH_LLM_MODE` | `openai` | `mock` disables LLM; any other value enables LLM via `LLM_PROVIDER` |
| `LLM_PROVIDER` | `openai` | `openai`, `azure_openai`, or `anthropic` |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature for conversation LLM |

### OpenAI (default)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `OPENAI_BASE_URL` | — | Optional custom API base URL |

### Azure OpenAI

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `AZURE_OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=azure_openai` |
| `AZURE_OPENAI_ENDPOINT` | — | Azure resource endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | — | Deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-02-15-preview` | API version |

### Anthropic Claude

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-latest` | Claude model name |

## Thought streaming

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `THOUGHT_STREAMING_ENABLED` | `false` | Enable SSE streaming endpoint |
| `VITE_THOUGHT_STREAMING_ENABLED` | — | Optional UI-only override |

## Ticketing

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `TICKETING_PROVIDER` | `zammad` | `zammad` or `servicenow` (stub) |
| `ZAMMAD_BASE_URL` | — | Zammad instance URL |
| `ZAMMAD_API_TOKEN` | — | Zammad API token |
| `ZAMMAD_TEST_EMAIL` | — | Test customer email for integration tests |
| `ZAMMAD_VERIFY_SSL` | `true` | TLS certificate verification |
| `ZAMMAD_TIMEOUT_SECONDS` | `30` | HTTP timeout |

## Object storage (attachments)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `S3_ENDPOINT` | — | MinIO/S3 endpoint (e.g. `http://localhost:9002`) |
| `S3_ACCESS_KEY` | — | Access key |
| `S3_SECRET_KEY` | — | Secret key |
| `S3_BUCKET` | `attachments` | Bucket name |
| `S3_REGION` | `us-east-1` | Region |
| `STORAGE_BACKEND` | `s3` | `s3` for MinIO/S3; `memory` for unit tests |

## KB / RAG (L1 handbook troubleshoot)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `KB_RAG_ENABLED` | `false` | Enable troubleshoot node before CreateTicket |
| `VECTOR_BACKEND` | `qdrant` | `qdrant` or `memory` (tests) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP URL |
| `QDRANT_API_KEY` | — | Optional Qdrant API key |
| `QDRANT_COLLECTION` | `agent_handbook` | Collection name |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `hash` (offline/tests) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model when using OpenAI |
| `EMBEDDING_DIMENSIONS` | `1536` | Vector size |
| `KB_RETRIEVAL_TOP_K` | `5` | Max chunks retrieved |
| `KB_MIN_SCORE` | `0.35` | Minimum similarity score (tune empirically; higher = stricter) |
| `KB_MAX_TROUBLESHOOT_STEPS` | `5` | Max grounded steps the RAG generator may return (adaptive 1..N) |
| `KB_RAG_MAX_CONTEXT_CHARS` | `12000` | Cap on retrieved handbook text passed into the RAG prompt |
| `KB_INCLUDE_CHAT_TRANSCRIPT_IN_TICKET` | `true` | Append full transcript on escalate→CreateTicket |
| `PDF_TO_MARKDOWN_CONVERTER` | `docling` | Handbook PDF → Markdown converter |
| `KB_PDF_OCR_ENABLED` | `false` | Enable Docling OCR for scanned PDFs only; roughly doubles peak memory |
| `KB_CHUNK_STRATEGY` | `page` | Chunking strategy (`page` or `heading`) |
| `KB_CHUNK_MAX_CHARS` | `4000` | Max characters per chunk |
| `KB_CHUNK_OVERLAP_CHARS` | `200` | Overlap between chunks |

### Handbook object storage

Separate from the **attachment** MinIO bucket (`S3_*`). Env vars use `CEPH_RGW_*` names for any S3-compatible endpoint:

| Environment | Typical setup |
| ----------- | ------------- |
| Host-run eval | `KB_HANDBOOK_STORAGE_BACKEND=memory` (seed script works; Admin upload needs `s3`) |
| Docker Compose API | `s3` + `CEPH_RGW_ENDPOINT=http://minio:9000` (dedicated `agent-handbooks` bucket) |
| Production | Ceph RGW (or managed S3) — not the attachment bucket |

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `KB_HANDBOOK_STORAGE_BACKEND` | `memory` | `memory` or `s3` (S3-compatible including MinIO/Ceph) |
| `KB_HANDBOOK_S3_BUCKET` | `agent-handbooks` | Handbook bucket name |
| `CEPH_RGW_ENDPOINT` | — | S3-compatible endpoint |
| `CEPH_RGW_ACCESS_KEY` | — | Access key |
| `CEPH_RGW_SECRET_KEY` | — | Secret key |
| `CEPH_RGW_REGION` | `us-east-1` | Region |
| `CEPH_RGW_ADDRESSING_STYLE` | `auto` | Addressing style (`auto`, `path`, `virtual`) |

## Keycloak (Admin KB API)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `KEYCLOAK_URL` | `http://localhost:8081` | Keycloak base URL |
| `KEYCLOAK_REALM` | `tech-support` | Realm name |
| `KEYCLOAK_ADMIN_CLIENT_ID` | `tech-support-admin` | OIDC client for Admin SPA |
| `KEYCLOAK_API_AUDIENCE` | `tech-support-admin` | Expected JWT audience |
| `KEYCLOAK_JWKS_URL` | — | Optional explicit JWKS URL override |

## Web client

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VITE_API_BASE_URL` | — | API URL for production builds |
| `API_PROXY_TARGET` | `http://localhost:8000` | Vite dev proxy target |
| `VITE_KEYCLOAK_URL` | — | Admin SPA Keycloak URL |
| `VITE_KEYCLOAK_REALM` | — | Admin SPA realm |
| `VITE_KEYCLOAK_CLIENT_ID` | — | Admin SPA OIDC client ID |

## Integration testing

| Variable | Description |
| -------- | ----------- |
| `USER_SIM_MODEL` | Model for AI user simulator |
| `USER_SIM_TEMPERATURE` | Simulator temperature |
| `INTEGRATION_MAX_TURNS` | Max dialogue turns in live tests |
| `INTEGRATION_HEADLESS` | Playwright headless mode |
| `INTEGRATION_SLOW_MO` | UI action delay (ms) |
| `LIVE_API_PORT` | Port for isolated live test API |
| `LIVE_WEB_PORT` | Port for isolated live test web |

## Docker Compose notes

- Compose sets `VITE_API_BASE_URL` for the web service
- API container uses `S3_ENDPOINT=http://minio:9000` for **attachments** and `CEPH_RGW_ENDPOINT=http://minio:9000` for **handbooks** (separate buckets)
- API container may rewrite `localhost` Zammad URLs to `host.docker.internal`
- `make up` starts Postgres, Redis, MinIO, Qdrant, and Keycloak
- `make up-kb` starts Postgres, Redis, Qdrant, and Keycloak (no MinIO)
- Seed sample handbooks with `make seed-kb` after migrate (`VECTOR_BACKEND=memory` is process-local — use Qdrant for shared retrieval)

## Security reminder

| Do | Don't |
| -- | ----- |
| Store tokens in secrets manager in production | Commit `.env` to git |
| Rotate tokens on schedule | Put tokens in `mapping.yaml` |
| Use dedicated Zammad integration user | Share personal admin tokens |

## Related documents

- [Deployment & Operations](../06-deployment-and-operations.md)
- [Zammad Integration Guide](../05-integration-guide-zammad.md)
