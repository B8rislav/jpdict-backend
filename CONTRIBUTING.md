# Contributing

Short guide for working on the JpDict backend. For project orientation (setup, layout, conventions) read [`AGENTS.md`](AGENTS.md) first.

## Branching

- Branch off `main`; never commit directly to `main`.
- Name branches `<type>/<short-description>`, e.g. `feat/reibun-pagination`, `fix/kanji-cache-ttl`, `docs/api-reference`, `chore/bump-deps`.

## Before you push

```bash
make lint        # ruff check + format check — must be clean
uv run pytest    # full suite must pass
```

`make typecheck` (mypy) is advisory — it has a small known baseline of errors. Don't add new ones.
Run `make format` to auto-fix lint findings and formatting.

## Database migrations

Migrations are async (Alembic + asyncpg). When you change a model:

```bash
uv run --env-file .env alembic revision --autogenerate -m "describe change"
```

1. **Review the generated revision** — autogenerate is a starting point, not gospel. Check the `upgrade`/`downgrade` ops, index/constraint names, and that no unintended drops slipped in.
2. Apply it locally with `make migrate` and verify the app still boots and tests pass.
3. Commit the revision file alongside the model change in the same PR.

## Conventions recap

- Async everywhere; inject the DB session via `Depends(get_session)`.
- No business logic in routers — it belongs in `app/services`.
- Pydantic schemas at the API edges.
- Give every new public service function and router handler a one-line docstring (intent + return shape).
- Never commit `.env` or secrets.
