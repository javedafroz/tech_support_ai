# Security Policy

## Supported versions

Security fixes are applied to the latest release on the `main` branch. Older
tags or forks are not actively maintained.

## Scope notes

This project integrates with third-party services (LLM providers, Zammad,
Keycloak, object storage). Vulnerabilities in those upstream products should be
reported to their respective maintainers. Reports about misconfiguration of a
local deployment (e.g. exposed credentials in a personal `.env`) are generally
out of scope unless they indicate a defect in the project itself.

## Hardening tips for deployers

- Never commit `.env` files or API tokens; use secrets management in production.
- Keep Keycloak, Postgres, Redis, Qdrant, and the object store behind a private
  network; expose only the intended public endpoints.
- Prefer Azure OpenAI (or another private-tenant LLM) when handling sensitive
  ticket content.
- Review handbook content before publishing — the agent surfaces grounded
  excerpts from whatever you publish.

Thank you for helping keep Tech Support AI and its users safe.
