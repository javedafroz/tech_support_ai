# Deployment & Operations

This guide covers how to deploy, configure, monitor, and operate **Tech Support AI** in development and production-like environments.

## Deployment options

| Option | Best for | Components |
| ------ | -------- | ---------- |
| **Docker Compose** | Local dev, demos, CI | API, web, Postgres, Redis, MinIO, Qdrant, Keycloak |
| **Host-run (uvicorn + vite)** | Active development | Processes on developer machine |
| **Kubernetes** *(target)* | Production | Containerized API/web, managed data stores |

## Docker Compose (evaluation path)

Follow the single path in [Quick Start](00-quick-start.md): `docker compose up -d --build`, then `make seed-kb`.

From the repository root:

```bash
cp .env.example .env
# Required: Zammad must already be running — set ZAMMAD_BASE_URL + ZAMMAD_API_TOKEN
# Also set KB_RAG_ENABLED=true and OPENAI_API_KEY (or GRAPH_LLM_MODE=mock)

docker compose up -d --build
```

| Service | Default port | Purpose |
| ------- | ------------ | ------- |
| Web | 5173 | React chat UI |
| Admin | 5174 | Handbook admin SPA (`make admin`) |
| API | 8000 | FastAPI backend |
| PostgreSQL | 5433 → 5432 | Durable storage |
| Redis | 6380 → 6379 | Session cache |
| MinIO API | 9002 → 9000 | Object storage (attachments; Compose also hosts handbook bucket) |
| MinIO Console | 9003 | MinIO admin UI |
| Qdrant | 6333 | Vector store for Agent Handbooks |
| Keycloak | 8081 → 8080 | Admin OIDC (realm import for local) |

Useful Make targets:

```bash
make up         # postgres, redis, minio, qdrant, keycloak
make up-kb      # postgres, redis, qdrant, keycloak (no MinIO)
make up-all     # full Compose stack including api, web, admin, docs
make migrate    # includes KB tables (004)
make seed-kb    # ingest + publish config/knowledge/*.md
make admin      # Admin SPA on :5174
```

### Health endpoints

```bash
curl http://localhost:8000/health/live    # process up
curl http://localhost:8000/health/ready   # dependencies ready
```

## Host-run development

### API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

# Start Postgres + Redis (Docker or local)
alembic upgrade head   # if migrations configured
uvicorn tech_support_api.main:app --reload --port 8000
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

Set `VITE_API_BASE_URL=http://localhost:8000` if needed.

## Environment configuration

Copy `.env.example` to `.env`. Critical variables:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `GRAPH_LLM_MODE` | Yes | `openai` or `mock` |
| `OPENAI_API_KEY` | If openai | OpenAI API key |
| `TICKETING_PROVIDER` | Yes | `zammad` (default) |
| `ZAMMAD_BASE_URL` | If zammad | Zammad instance URL |
| `ZAMMAD_API_TOKEN` | If zammad | API token |
| `S3_ENDPOINT` | If attachments | MinIO/S3 endpoint |
| `S3_ACCESS_KEY` | If attachments | Object storage access key |
| `S3_SECRET_KEY` | If attachments | Object storage secret |
| `S3_BUCKET` | No | Bucket name (default `attachments`) |
| `AUTH_MODE` | Yes | `dev` or `jwt` |
| `THOUGHT_STREAMING_ENABLED` | No | `true` / `false` |
| `KB_RAG_ENABLED` | No | `true` to enable L1 handbook troubleshoot |
| `VECTOR_BACKEND` | If KB | `qdrant` (shared) or `memory` (process-local / tests) |
| `QDRANT_URL` | If KB | Vector store URL (default `http://localhost:6333`) |
| `EMBEDDING_PROVIDER` | If KB | `openai` or `hash` (offline/tests) |
| `KB_MIN_SCORE` | No | Retrieval threshold (default `0.35`) |
| `KEYCLOAK_URL` | Yes (Admin KB) | Admin OIDC issuer host |
| `KB_HANDBOOK_STORAGE_BACKEND` | Yes (Admin upload) | `memory` or `s3` (S3-compatible / Ceph RGW) |

Full reference: [Environment Variables](appendices/B-environment-variables.md).

## Database operations

### Schema

PostgreSQL holds:

- Chat sessions and messages
- Session attachments metadata (`session_attachments`)
- KB handbook metadata (`kb_documents`, `kb_ingest_jobs`, `kb_deflection_events`)
- Audit tables (`policy_audit_log`, `zammad_operations`)
- Reason code catalog

Apply migrations on deploy:

```bash
make migrate
# or: cd apps/api && alembic upgrade head
```

### Backup

| Store | Recommendation |
| ----- | -------------- |
| PostgreSQL | Daily automated backups; point-in-time recovery for production |
| Redis | Ephemeral — backup optional; rebuild from Postgres on cold start |

## Redis operations

Session context keys expire after configurable TTL (default ~24 hours). Redis loss causes:

- Loss of hot session context (recent turns cache)
- **No** loss of message history (PostgreSQL)

Users may experience slightly slower context rebuild after Redis flush.

## Scaling considerations

| Component | Scale approach |
| --------- | -------------- |
| API | Horizontal replicas behind load balancer; stateless |
| Web / Admin | Static CDN or multiple Vite/nginx replicas |
| PostgreSQL | Vertical scale or managed RDS; connection pooling |
| Redis | Single instance or Redis Cluster for HA |
| Qdrant | Dedicated cluster or managed vector service for production |
| Keycloak | Shared IdP or dedicated realm; HA per IdP guidance |
| OpenAI | Rate limits per API key — consider queueing for high volume |

LangGraph runs in-process per API worker today. For high concurrency, size workers appropriately and monitor OpenAI latency.

## Monitoring

### Recommended signals

| Signal | Source |
| ------ | ------ |
| API latency p95 | APM / ingress metrics |
| Error rate 5xx | API logs |
| OpenAI call failures | Agent logs |
| Zammad HTTP errors | Ticketing client logs |
| Postgres connection pool | DB metrics |
| Redis memory | Redis INFO |

### Logging

API uses structured logging (`structlog`). Configure JSON output in production for log aggregation (ELK, CloudWatch, Datadog, etc.).

## Release process

1. Run test suite: `pytest` across packages
2. Build containers: `docker compose build`
3. Apply DB migrations
4. Rolling deploy API replicas
5. Deploy web static assets
6. Smoke test: health endpoints + create session + send message

## Configuration changes

| Change type | Action |
| ----------- | ------ |
| `.env` secrets | Rolling restart API |
| `mapping.yaml` | Restart API to reload |
| Reason codes | DB seed or migration |
| Feature flags | Restart API (`THOUGHT_STREAMING_ENABLED`, etc.) |

## Operational runbook

### API won't start

1. Check `DATABASE_URL` and `REDIS_URL` connectivity
2. Verify migrations applied
3. Check logs for missing `OPENAI_API_KEY` when `GRAPH_LLM_MODE=openai`

### Tickets not creating

1. Verify `TICKETING_PROVIDER=zammad`
2. Test Zammad token manually (see [Zammad Integration Guide](05-integration-guide-zammad.md))
3. Check orchestration rejection in API response / logs
4. Validate `mapping.yaml` group IDs exist in Zammad

### Attachments failing

1. Verify MinIO is running (`docker compose ps minio`)
2. Check `S3_*` variables — Docker uses `http://minio:9000` inside the API container
3. For Zammad `mime-type` errors, ensure API image includes current `ZammadClient` serialization
4. For vision not reading screenshots, confirm `GRAPH_LLM_MODE=openai` and a vision-capable model

### High latency

1. Check OpenAI API status and latency
2. Check Zammad response times
3. Review Postgres slow queries
4. Consider `GRAPH_LLM_MODE=mock` for isolated perf testing

### Redis down

- API may degrade session context performance
- Restore Redis; sessions recover from Postgres on next message

## Security operations

- Rotate `ZAMMAD_API_TOKEN` and `OPENAI_API_KEY` on schedule
- Restrict network egress from API to required hosts only
- Use secrets manager in production (not plain `.env` on disk)

See [Security & Data Handling](04-security-and-data-handling.md).

## Production checklist

- [ ] HTTPS everywhere
- [ ] Secrets in vault
- [ ] OIDC auth *(when available)*
- [ ] DB backups automated
- [ ] Log aggregation and alerting
- [ ] CORS restricted to production web origin
- [ ] Resource limits on containers
- [ ] Zammad integration user with least privilege

## Related documents

- [Quick Start](00-quick-start.md)
- [Zammad Integration Guide](05-integration-guide-zammad.md)
- [Test & Acceptance](09-test-and-acceptance.md)
