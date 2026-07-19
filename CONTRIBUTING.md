# Contributing to Tech Support AI

Thanks for your interest in contributing! This guide covers how to set up your
environment, the standards we follow, and how to get a change merged.

By participating in this project you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Getting started

1. **Fork** the repository and create a feature branch from `main`:

   ```bash
   git checkout -b feat/short-description
   ```

2. **Install dependencies** (Python via [uv](https://docs.astral.sh/uv/), plus the
   web and admin frontends):

   ```bash
   make install
   ```

3. **Bring up local infrastructure** and apply migrations:

   ```bash
   make up
   make migrate
   ```

You can develop entirely offline by setting `GRAPH_LLM_MODE=mock`,
`VECTOR_BACKEND=memory`, and `EMBEDDING_PROVIDER=hash` in your `.env` — no OpenAI
or Zammad credentials required. See [`.env.example`](.env.example) for all
settings and the [Quick start](docs/external/00-quick-start.md) for details.

## Development workflow

- Keep changes focused; one logical change per pull request.
- Add or update tests for any behavior you change.
- Update relevant documentation (README, `docs/`) when behavior or configuration
  changes.
- Run the checks below before pushing.

### Checks

```bash
make lint          # ruff (Python) + eslint (web)
make test          # pytest + vitest
make e2e           # Playwright browser tests (mock LLM + Wiremock; no keys needed)
```

All of these run without external API keys.

## Coding standards

- **Python** targets 3.12+ and is formatted/linted with
  [ruff](https://docs.astral.sh/ruff/) (line length 100). Prefer type hints and
  keep business logic deterministic — the LLM handles language, not consequences.
- **TypeScript/React** is linted with eslint. Keep components small and typed.
- Don't add comments that merely restate the code; explain intent or trade-offs
  only where it isn't obvious.
- Never commit secrets. `.env` is gitignored — use `.env.example` for new settings.

## Commit and pull request guidelines

- Write clear, imperative commit messages (e.g. `Add confirm-before-submit gate`).
- In the PR description, explain **what** changed and **why**, and link any related
  issue.
- Ensure CI/checks pass and that the branch is up to date with `main`.
- Be responsive to review feedback; maintainers may request changes before merge.

## Reporting bugs and requesting features

- Search existing issues first to avoid duplicates.
- For bugs, include reproduction steps, expected vs. actual behavior, and relevant
  logs or configuration (with secrets redacted).
- For features, describe the use case and the problem it solves.

For security vulnerabilities, **do not** open a public issue — follow
[SECURITY.md](SECURITY.md) instead.

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE).
