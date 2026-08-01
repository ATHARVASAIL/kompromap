# Deploying Kompromap

Two realistic paths, depending on what you have available. Both assume
you've already got the repo checked out and Docker installed on whatever
you're deploying to.

## Option A — Single VM / VPS (recommended, simplest)

Everything (frontend, backend, Postgres) runs on one machine via
`docker-compose.prod.yml`.

```bash
git clone https://github.com/<you>/kompromap.git
cd kompromap
cp .env.prod.example .env
```

Edit `.env` — at minimum, change `POSTGRES_PASSWORD` to something real, and
set `CORS_ORIGINS` to the domain you'll actually serve the frontend from
(e.g. `CORS_ORIGINS=https://kompromap.yourdomain.com`).

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds both production images locally, starts Postgres, runs
`alembic upgrade head` automatically before the backend starts serving
traffic, and exposes the frontend (with `/api` reverse-proxied to the
backend automatically — see `frontend/nginx.conf`) on port 80.

**Put a real reverse proxy with TLS in front of it.** The compose file's
nginx serves plain HTTP on port 80 — that's fine as the origin server, but
you need something terminating TLS in front of it for a real deployment.
[Caddy](https://caddyserver.com/) is the least fuss for this:

```
# Caddyfile
kompromap.yourdomain.com {
    reverse_proxy localhost:80
}
```

Caddy handles Let's Encrypt certificate issuance and renewal automatically.
(Traefik or nginx+certbot work too if you'd rather use those.)

**Updating:** `git pull && docker compose -f docker-compose.prod.yml up -d --build`
rebuilds and restarts with zero manual migration steps — the backend runs
`alembic upgrade head` on every startup, so it's a no-op if there's nothing
new to migrate.

## Option B — Use the pre-built images from GitHub Container Registry

Every push to `main` builds and pushes both images via
`.github/workflows/docker-publish.yml` to:

```
ghcr.io/<you>/kompromap-backend:latest
ghcr.io/<you>/kompromap-frontend:latest
```

Swap the `build:` blocks in `docker-compose.prod.yml` for `image:`
references to skip building on the server entirely:

```yaml
services:
  backend:
    image: ghcr.io/<you>/kompromap-backend:latest
    # (remove the `build:` block)
  frontend:
    image: ghcr.io/<you>/kompromap-frontend:latest
    # (remove the `build:` block)
```

Note the frontend image bakes `VITE_API_BASE_URL` in at *build* time (Vite
inlines env vars into the static bundle), so if you need a non-default
value, set the `VITE_API_BASE_URL` **repository variable** (not secret) in
GitHub before the workflow runs, or build your own image locally with the
right `--build-arg`.

## Option C — Split hosting (frontend and backend on different platforms)

If you'd rather use managed platforms instead of running your own VM:

**Backend + Postgres** — Railway, Render, or Fly.io all support "deploy
from a Dockerfile" directly:
1. Point the platform at `backend/Dockerfile.prod`.
2. Provision a Postgres instance (most of these platforms offer one
   natively) and set `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_USER`/
   `POSTGRES_PASSWORD`/`POSTGRES_DB` to match it.
3. Set `CORS_ORIGINS` to your frontend's URL.
4. The Dockerfile's entrypoint runs migrations automatically on every
   deploy — nothing extra to configure.

**Frontend** — Vercel, Netlify, Cloudflare Pages, or GitHub Pages all serve
a static Vite build fine:
1. Build command: `npm run build`, output directory: `dist`.
2. Set the build-time env var `VITE_API_BASE_URL` to your backend's public
   URL (e.g. `https://kompromap-api.up.railway.app`) — this is required
   here, since frontend and backend are on different origins and the
   nginx reverse-proxy trick from Option A only works when they're
   deployed together.
3. Since there's no `try_files` SPA fallback config to write yourself on
   most of these platforms (they handle it), no extra routing config is
   usually needed for a Vite app with no client-side router (this app
   doesn't use one — see `frontend/src/pages/AppShell.tsx`).

## Environment variables reference

| Variable | Where | Purpose | Default |
|---|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | backend, postgres | Database credentials | `kompromap` / `kompromap` / `kompromap` (dev-only — **change these in prod**) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | backend | Where Postgres lives | `postgres` / `5432` in compose |
| `CORS_ORIGINS` | backend | Comma-separated list of origins allowed to call the API | `http://localhost:5173,http://localhost:3000` |
| `ANTHROPIC_API_KEY` | backend | Enables LLM-generated attack-chain narratives | unset (falls back to a template narrative — see README) |
| `ANTHROPIC_MODEL` | backend | Which Claude model to use for narratives | `claude-sonnet-5` |
| `UVICORN_WORKERS` | backend (prod only) | Number of worker processes | `2` |
| `VITE_API_BASE_URL` | frontend (build time) | Backend URL, if not same-origin | empty (same-origin) |

## Post-deploy checklist

- [ ] Changed `POSTGRES_PASSWORD` from the placeholder
- [ ] `CORS_ORIGINS` set to your real frontend domain(s), not `*` or `localhost`
- [ ] TLS terminated in front of the app (Caddy/Traefik/nginx+certbot, or your platform's built-in TLS)
- [ ] Confirmed `GET /api/health` and `GET /api/health/db` both return 200 from the deployed backend
- [ ] Confirmed the frontend loads and `GET /api/graph` succeeds (open browser devtools → Network tab on first load)
- [ ] Decided whether `ANTHROPIC_API_KEY` is worth setting (optional — everything works without it, narratives just use the template fallback)

## Backups

`docker-compose.prod.yml`'s Postgres volume (`kompromap_pg_data_prod`) is a
regular Docker named volume — back it up like any other:

```bash
docker exec <postgres-container> pg_dump -U kompromap kompromap > backup.sql
```

Restoring is the reverse (`psql -U kompromap kompromap < backup.sql` against
a running container). If you're using a managed Postgres from Option C's
platforms, use their built-in backup tooling instead.
