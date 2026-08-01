# Contributing to Kompromap

## Setup

See [README.md](./README.md#quick-start-docker) for getting a local
environment running, or the [manual setup](./README.md#manual-setup)
section if you'd rather not use Docker.

## Running tests

```bash
# Backend
cd backend && pytest -v

# Frontend
cd frontend && npx tsc -b && npm run build && npx eslint src --ext ts,tsx
```

Both must pass before a PR will merge — CI runs the same checks on every
push and pull request (see `.github/workflows/ci.yml`).

## Making changes

- **Backend**: keep the model layer's cross-dialect types
  (`sqlalchemy.Uuid`, `JSON().with_variant(...)`) if you touch
  `app/models/` — they're what let the test suite run against SQLite
  without a live Postgres instance. If you add a migration, write it by
  hand and cross-check it against the model DDL (see
  `backend/tests/test_models.py` for the pattern) rather than assuming
  autogenerate will get it right without a live DB to diff against.
- **Frontend**: colors, fonts, and radii are centralized in
  `frontend/src/styles/tokens.ts` and `tailwind.config.js` — avoid
  hardcoding hex values or `slate-*`/`emerald-*`-style Tailwind defaults in
  components.
- Keep PRs focused. If a change touches both frontend and backend, say so
  in the description so reviewers know to check both CI jobs.

## Reporting bugs / requesting features

Use the issue templates — they ask for the minimum context needed to act
on a report without back-and-forth.
