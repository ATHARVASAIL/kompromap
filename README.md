<div align="center">

# 🗺️ Kompromap

### Stop reading flat CVSS tables. Start seeing the attack chain.

Kompromap ingests raw VAPT tool output (Nmap, Nuclei, Amass/Subfinder,
Burp/ZAP) and manual findings, then auto-assembles them into a queryable
attack-chain graph — answering the one question every pentest report tries
to answer in prose: **what's the actual path from an unauthenticated
attacker to the thing that matters?**

![Typing SVG](https://readme-typing-svg.demolab.com/?font=JetBrains+Mono&size=20&pause=1200&color=2DD4E8&center=true&vCenter=true&width=680&lines=Subdomain+takeover+%E2%86%92+Stored+XSS+%E2%86%92+Session+theft;IDOR+on+%2Fapi%2Fv2%2Fusers%2F%7Bid%7D+%E2%86%92+PII+dump;Not+a+flat+CVSS+table.+An+attack+chain.)

[![CI](https://github.com/OWNER/kompromap/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/kompromap/actions/workflows/ci.yml)
[![Docker Publish](https://github.com/OWNER/kompromap/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/OWNER/kompromap/actions/workflows/docker-publish.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2DD4E8.svg?style=flat-square)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](./backend)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](./backend)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat-square&logo=react&logoColor=white)](./frontend)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6.svg?style=flat-square&logo=typescript&logoColor=white)](./frontend)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg?style=flat-square&logo=postgresql&logoColor=white)](./backend)

<sub>⚠️ Replace <code>OWNER</code> in the badge URLs above with your GitHub username/org once this is pushed — they 404 until then.</sub>

</div>

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start (Docker)](#quick-start-docker)
- [Manual setup](#manual-setup)
- [Deployment](#deployment)
- [API reference](#api-reference)
- [How the scoring & path-finding works](#how-the-scoring--path-finding-works)
- [Multi-engagement design](#multi-engagement-design)
- [Reporting & narrative generation](#reporting--narrative-generation)
- [Testing](#testing)
- [Frontend architecture](#frontend-architecture)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Why

Every pentest produces a pile of individually-scored findings — a
subdomain takeover here, a stored XSS there, an IDOR somewhere else. None
of them look critical alone. **Chained together, they're a full
compromise.** Existing graph tools (BloodHound and friends) map identity/
permission graphs within one system — a totally different problem from
chaining independent technical vulnerabilities across an external web/API
surface. Kompromap fills that gap: raw tool output in, attack-chain graph
out, with a path-finding engine that answers "what's the easiest way in?"

## Features

- 🕸️ **Attack-chain graph** — Cytoscape.js visualization with per-type SVG
  icons (8 node types, 7 edge types), animated layout transitions, hover
  highlighting, and search-as-you-type
- 📥 **Auto-ingestion** — upload raw Nmap/Nuclei/Amass-Subfinder/Burp-ZAP
  output and it's parsed straight into linked graph nodes
- 🎯 **Path-finding** — Dijkstra over a weighted graph (CVSS + exploit
  availability + auth requirement), not just shortest-hop-count — finds
  the *most realistic* chain, which might be five easy hops instead of one
  hard one
- 📝 **Narrative generation** — LLM-written (or template-fallback) plain-
  English paragraph describing a selected chain, exportable as
  Markdown/JSON for a report
- 🗂️ **Multi-engagement workspaces** — fully isolated per-client graphs,
  with point-in-time snapshots and diffing
- 📊 **Dashboard** — node/edge counts, findings-by-severity chart, paths-
  to-crown-jewels, highest-ease chain found
- ⌨️ **Command palette** (Ctrl/Cmd+K) and keyboard shortcuts throughout

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        A[Nmap]
        B[Nuclei]
        C[Amass / Subfinder]
        D[Burp / ZAP]
        E[Manual entry]
    end

    subgraph Backend["Backend — FastAPI"]
        P[Parsers] --> I[Ingestion service]
        I --> DB[(PostgreSQL)]
        DB --> G[NetworkX in-memory graph]
        G --> PF[Path-finding — Dijkstra]
        G --> R[Reporting / narrative]
    end

    subgraph Frontend["Frontend — React + Cytoscape.js"]
        UI[Graph / Findings / Path Analysis / Dashboard / Import]
    end

    A --> P
    B --> P
    C --> P
    D --> P
    E --> I
    Backend <--> Frontend
```

Storage is deliberately boring: relational Postgres tables
(`nodes`/`edges` adjacency-list style), loaded into NetworkX in memory for
graph algorithms on request. No graph database — at engagement scale
(hundreds of nodes, not millions), it isn't needed.

## Quick start (Docker)

```bash
git clone https://github.com/<you>/kompromap.git
cd kompromap
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres | localhost:5432 |

The frontend dev server proxies `/api/*` to the backend, so there's no CORS
configuration needed for local dev.

## Manual setup

<details>
<summary><strong>Backend</strong></summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # edit if your local Postgres differs
uvicorn app.main:app --reload
```

You'll need a local Postgres instance matching `.env` (default:
`kompromap` / `kompromap` / `kompromap` on `localhost:5432`). Quickest way
without the full compose stack:

```bash
docker run -d --name kompromap-pg \
  -e POSTGRES_USER=kompromap -e POSTGRES_PASSWORD=kompromap -e POSTGRES_DB=kompromap \
  -p 5432:5432 postgres:16-alpine
```

</details>

<details>
<summary><strong>Frontend</strong></summary>

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173.

</details>

## Deployment

Full guide: **[DEPLOYMENT.md](./DEPLOYMENT.md)**. Short version:

```bash
cp .env.prod.example .env   # edit with real values — see checklist in DEPLOYMENT.md
docker compose -f docker-compose.prod.yml up -d --build
```

This builds production images (backend: no `--reload`, migrations run
automatically on startup; frontend: static build served via nginx, with
`/api` reverse-proxied to the backend so it works same-origin out of the
box), and is meant for a single VM/VPS. `DEPLOYMENT.md` also covers using
the images CI already publishes to GHCR, and split-hosting the frontend
and backend on separate platforms (Vercel/Netlify + Railway/Render/Fly.io).

CI (`.github/workflows/ci.yml`) runs backend tests and frontend
typecheck/build/lint on every push and PR. CD
(`.github/workflows/docker-publish.yml`) builds and pushes both images to
`ghcr.io` on every push to `main`.

## API reference

| Endpoint | Purpose |
|---|---|
| `POST /api/nodes` | Create any node type (body discriminated by `node_type`) |
| `GET /api/nodes` | List nodes — filter by `node_type`, `in_scope`, `is_entry_point`, `is_crown_jewel`, `min_cvss`, `status` |
| `GET/PATCH/DELETE /api/nodes/{id}` | Fetch, partially update, or delete a node |
| `POST /api/edges` | Create an edge between two existing nodes |
| `GET /api/edges` | List edges — filter by `source_node_id`, `target_node_id`, `edge_type` |
| `GET/PATCH/DELETE /api/edges/{id}` | Fetch, update, or delete an edge |
| `POST /api/findings` | Manual finding entry — creates a Finding and its `HAS_FINDING` edge to an Asset/Endpoint in one call |
| `POST /api/ingest/{nmap,nuclei,amass,burp}` | Upload a tool output file and ingest it into the graph |
| `GET /api/graph` | Full graph in Cytoscape.js-ready shape — filter by `node_type`, `in_scope_only`, `min_cvss` |
| `POST /api/pathfind/best` | Easiest path from every (or specified) entry point to any crown jewel |
| `POST /api/pathfind/from/{entry_point_id}` | Easiest path from one entry point to each reachable crown jewel |
| `POST /api/reports/narrative` | Plain-English paragraph describing a chain (ordered `node_ids`), for a pentest report |
| `POST /api/reports/export` | Export a chain as Markdown or structured JSON — narrative + evidence + full node/edge detail |
| `GET/POST /api/engagements` | List / create engagements (workspaces) |
| `GET /api/engagements/active` | The currently active engagement |
| `POST /api/engagements/{id}/activate` | Switch the active engagement |
| `GET /api/engagements/{id}/dashboard` | Node/edge counts, paths to crown jewels, highest-ease chain |
| `GET/POST /api/engagements/{id}/snapshots` | List / capture point-in-time graph snapshots |
| `GET /api/snapshots/{id}/diff` | Diff a snapshot against the current graph, or another snapshot via `?compare_to=` |

Full interactive docs at `/docs` once the backend is running.

## How the scoring & path-finding works

```
ease_score = normalize(cvss_score) * 0.4
           + exploit_public_availability * 0.3
           + (1 - auth_required) * 0.2
           + (1 - complexity) * 0.1
cost = 1 - ease_score
```

Dijkstra minimizes total cost, so the "shortest path" is the *most
realistic* chain, not just the fewest hops — an easy five-hop chain can
beat one hard direct exploit.

Two things worth knowing if you're extending this:

- **`complexity` isn't a stored Finding property anywhere in the data
  model** — only `cvss_score`, `exploit_public`, and `auth_required` are.
  Rather than invent the data, `app/services/scoring.py` uses a
  configurable `default_complexity` (0.5, neutral) applied uniformly. Pass
  `weights.complexity: 0` in a pathfind request if you'd rather it not
  influence anything.
- **Only `YIELDS` edges get a computed ease_score** — the one edge type
  framed as an actual exploitation step ("exploiting this finding gets you
  this"). Every other edge type (`HOSTS`, `EXPOSES`, `HAS_FINDING`,
  `TRUSTS`, `AUTHENTICATES_AS`, `GRANTS_ACCESS_TO`) defaults to zero cost —
  an established relationship, not something you "exploit." Any edge's
  cost can still be overridden manually (the `+ edge` form has a weight
  field), and a manual override always wins over the computed default.

## Multi-engagement design

Every node carries a nullable `engagement_id`. Rather than require every
caller to pass one, there's a single "active engagement" — auto-created
("Default Engagement") the first time anything touches the graph.
`POST /api/engagements/{id}/activate` switches it; node creation,
ingestion, and all list/graph/pathfind endpoints default to whichever
engagement is active unless you pass an explicit `engagement_id`.

This isn't just filtering at read time — ingestion's get-or-create lookups
(dedupe an Asset by name, a Service by asset+port, etc.) are scoped
per-engagement too, so importing the same subdomain into two different
clients' engagements creates two genuinely separate Asset nodes, never a
merge. `tests/test_ingestion.py::test_same_asset_name_in_different_engagements_stays_isolated`
is the test that pins this down.

## Reporting & narrative generation

`POST /api/reports/narrative` and `/api/reports/export` take an ordered
list of `node_ids` (typically a path-finding result, but any connected
chain works) and generate a paragraph describing it.

- **With `ANTHROPIC_API_KEY` set:** calls the real Anthropic API, passing
  the chain's nodes, properties, and Finding evidence as structured
  context.
- **Without a key, or if the call fails for any reason:** falls back to a
  deterministic templated paragraph built directly from the chain data.
  Export always works — a tester shouldn't be blocked by a missing
  credential or a transient API error. `narrative_source` in the response
  (`"llm"` or `"template"`) tells you which happened.
- Export accepts an already-generated (possibly hand-edited) `narrative`
  to skip a redundant LLM call when the tester already reviewed one in the
  UI.

## Testing

```bash
cd backend && pytest -v
cd frontend && npx tsc -b && npm run build && npx eslint src --ext ts,tsx
```

**Backend — 137+ tests:** model/mapper sanity checks, parser unit tests
against sanitized sample files in `tests/fixtures/`, ingestion-service
tests (including cross-engagement isolation), scoring/path-finding tests
validated against the spec's own example attack chain, and full API tests
covering every router.

Tests run against an in-memory SQLite DB rather than Postgres — the model
layer uses cross-dialect column types (`sqlalchemy.Uuid`,
`JSON().with_variant(...)`) specifically so it's exercisable without a
live Postgres instance. This produces byte-for-byte identical DDL on
Postgres (verified in `test_models.py`); it's a test-only convenience, not
a stack change.

## Frontend architecture

Persistent sidebar with five sections (Graph / Findings / Path Analysis /
Dashboard / Import) — see `pages/AppShell.tsx`.

- **Design tokens** (`styles/tokens.ts`, `tailwind.config.js`) — dark-first
  palette as CSS custom properties, one deliberate accent (signal cyan),
  a colorblind-considerate severity scale (red→orange→amber→**blue**→gray,
  not red→green), JetBrains Mono for data/IDs, Inter for UI chrome.
- **`GraphCanvas`** — Cytoscape.js, persistent instance (diffed and
  re-laid-out on data changes rather than destroyed/recreated, so layout
  transitions actually animate), per-type SVG icons + shapes, per-edge-type
  line styles, hover highlighting, sequential path-pulse animation for
  path-finding results, search-as-you-type.
- **`FindingsPage`** — sortable/filterable table, severity badges, dense
  mode toggle.
- **`DashboardPage`** — stat cards + a `recharts` findings-by-severity
  chart.
- **`PathAnalysisPage`** — path-finding controls alongside the graph
  showing the highlighted chain; narrative generation and Markdown/JSON
  export live here too.
- **`ImportPage`** — upload UI for all four ingest endpoints, with
  session import history.
- **`CommandPalette`** (Ctrl/Cmd+K), **`ShortcutsHelp`** (`?`) — `/`
  focuses search, `f` focuses the type filter, `Esc` cascades closed
  through whatever's open.
- **`ToastProvider`**, **`Skeleton`**, **`ErrorBanner`**, **`EmptyState`**
  — consistent async-state treatment app-wide, no ad hoc loading/error
  text.

## Project structure

```
backend/
  app/
    api/         # FastAPI routers
    core/        # config, db session
    models/      # SQLAlchemy models
    parsers/     # nmap.py, nuclei.py, amass.py, burp.py
    services/    # ingestion, scoring, pathfinding, reporting, snapshots, engagements
    schemas/     # Pydantic request/response schemas
    main.py      # app entrypoint
  alembic/       # migrations
  tests/
  Dockerfile, Dockerfile.prod
frontend/
  src/
    api/         # fetch wrappers (VITE_API_BASE_URL-aware)
    components/  # shared UI (badges, panels, modals, graph canvas)
    pages/        # AppShell + the 5 sections
    styles/       # design tokens, edge/node style maps
    graph/        # SVG icon generation for Cytoscape
  Dockerfile, Dockerfile.prod, nginx.conf
.github/
  workflows/     # ci.yml, docker-publish.yml
docker-compose.yml         # local dev
docker-compose.prod.yml    # production
DEPLOYMENT.md
kompromap-spec.md
```

## Roadmap

See [`kompromap-spec.md`](./kompromap-spec.md) §7 for the full phased
build plan (Phase 0 scaffold → Phase 1 data layer & parsers → Phase 2 graph
construction & API → Phase 3 visualization → Phase 4 path-finding →
Phase 5 reporting → Phase 6 multi-engagement & polish). All six phases are
complete, followed by a UI modernization pass (design tokens, graph
visual polish, layout/navigation, motion, and empty/loading/error states).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

[MIT](./LICENSE) — a default placeholder; change it if you'd rather use
something else.
