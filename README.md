# Kompromap

Ingests recon and vulnerability data from a VAPT engagement (Nmap, Nuclei,
Amass/Subfinder, Burp/ZAP exports, manual findings) and builds an
attack-chain graph — a visual, queryable map of how individual weaknesses
chain together into a full compromise path, instead of a flat CVSS-sorted
findings table.

Full spec: [`kompromap-spec.md`](./kompromap-spec.md).

## Status

**Phase 6 — multi-engagement + polish. All six phases complete.**
Workspace/engagement switcher, graph snapshots with diff-against-current-
or-another-snapshot, a dashboard (counts, paths to crown jewels,
highest-ease chain), and a Ctrl/Cmd+K command palette. Every engagement's
graph is isolated end-to-end — verified with a test proving the same
subdomain name ingested into two engagements creates genuinely separate
nodes, not a merge.

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL (loaded into NetworkX in-memory for graph algorithms)
- **Frontend:** React + TypeScript + Tailwind, Cytoscape.js for graph rendering

## Project layout

```
backend/
  app/
    api/         # FastAPI routers
    core/        # config, db session
    models/      # SQLAlchemy models (Phase 1)
    parsers/     # nmap.py, nuclei.py, amass.py, burp.py (Phase 1)
    schemas/     # Pydantic request/response schemas
    main.py      # app entrypoint
  tests/
  requirements.txt
  Dockerfile
frontend/
  src/
    api/         # fetch wrappers for the backend
    components/  # graph view, filters, detail panel (Phase 3)
    pages/
    App.tsx
  Dockerfile
docker-compose.yml
kompromap-spec.md
```

## Running locally (Docker — recommended)

Requires Docker and Docker Compose.

```bash
docker compose up --build
```

This starts three services:

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres | localhost:5432 |

The frontend dev server proxies `/api/*` requests to the backend, so no CORS
config is needed in the browser.

Visiting the frontend should show a status page confirming the API server
and Postgres are both reachable.

## Running locally (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # edit if your local Postgres differs
uvicorn app.main:app --reload
```

You'll need a local Postgres instance matching the values in `.env`
(default: `kompromap` / `kompromap` / `kompromap` on `localhost:5432`).
Easiest way to get one without running the full compose stack:

```bash
docker run -d --name kompromap-pg \
  -e POSTGRES_USER=kompromap -e POSTGRES_PASSWORD=kompromap -e POSTGRES_DB=kompromap \
  -p 5432:5432 postgres:16-alpine
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173.

## API endpoints

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

## Multi-engagement design

Every node carries a nullable `engagement_id`. Rather than require every
caller to pass one, there's a single "active engagement" — auto-created
("Default Engagement") the first time anything touches the graph, so every
earlier phase's API calls kept working completely unmodified once this
landed. `POST /api/engagements/{id}/activate` switches it; node creation,
ingestion, and all list/graph/pathfind endpoints default to whichever
engagement is active unless you pass an explicit `engagement_id`.

This isn't just filtering at read time — ingestion's get-or-create lookups
(the ones that dedupe an Asset by name, a Service by asset+port, etc.) are
scoped per-engagement too, so importing the same subdomain into two
different clients' engagements creates two genuinely separate Asset nodes,
never a merge. `tests/test_ingestion.py::test_same_asset_name_in_different_engagements_stays_isolated`
is the test that pins this down.

## Reporting & narrative generation

`POST /api/reports/narrative` and `/api/reports/export` take an ordered
list of `node_ids` (typically a path-finding result, but any connected
chain works — validated via the edges between consecutive nodes) and
generate a paragraph describing it.

- **With `ANTHROPIC_API_KEY` set:** calls the real Anthropic API
  (`app/services/reporting.py`), passing the chain's nodes, properties, and
  Finding evidence as structured context, per spec §6.
- **Without a key, or if the API call fails for any reason:** falls back to
  a deterministic templated paragraph built directly from the chain data.
  Export always works — a tester shouldn't be blocked from getting their
  report out by a missing credential or a transient API error. The
  response's `narrative_source` field (`"llm"` or `"template"`) tells you
  which happened.
- `/api/reports/export` accepts an already-generated (and possibly
  hand-edited) `narrative` string to avoid a redundant LLM call when the
  tester already reviewed one in the UI.

## Scoring & path-finding

Implements spec §4's ease_score formula:

```
ease_score = normalize(cvss_score) * 0.4
           + exploit_public_availability * 0.3
           + (1 - auth_required) * 0.2
           + (1 - complexity) * 0.1
cost = 1 - ease_score
```

Two things worth knowing if you're extending this:

- **`complexity` isn't a stored Finding property anywhere in the spec's
  data model** — only `cvss_score`, `exploit_public`, and `auth_required`
  are. Rather than invent the data, `app/services/scoring.py` uses a
  configurable `default_complexity` (0.5, neutral) applied uniformly. Pass
  `weights.complexity: 0` in a pathfind request if you'd rather it not
  influence anything.
- **Only `YIELDS` edges get a computed ease_score.** That's the one edge
  type the spec frames as an actual exploitation step ("exploiting this
  finding gets you this"). Every other edge type (`HOSTS`, `EXPOSES`,
  `HAS_FINDING`, `TRUSTS`, `AUTHENTICATES_AS`, `GRANTS_ACCESS_TO`) defaults
  to zero cost — it's an established relationship, not something you
  "exploit." Any edge's cost can still be overridden manually (the `+ edge`
  form in the UI has a weight field) and a manual override always wins over
  the computed default.

## Health checks

- `GET /api/health` — liveness, no DB dependency
- `GET /api/health/db` — confirms the API can reach Postgres

## Database migrations

```bash
cd backend
alembic upgrade head        # apply all migrations
alembic revision --autogenerate -m "describe your change"   # after editing models
```

`alembic/env.py` reads the DB URL from `app.core.config`, so it always uses
the same `.env` as the running app — nothing to configure separately.

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

137 tests: model/mapper sanity checks, parser unit tests against sanitized
sample files in `tests/fixtures/`, ingestion-service tests (including
cross-engagement isolation), scoring/path-finding tests validated against
the spec's own example attack chain, and full API tests (via FastAPI's
`TestClient`) covering every router — node/edge CRUD, manual finding entry,
file ingestion, path-finding, narrative/export, engagements, and snapshots.

Tests run against an in-memory SQLite DB rather than Postgres — the model
layer uses cross-dialect column types (`sqlalchemy.Uuid`, `JSON().with_variant(...)`)
specifically so it's exercisable without a live Postgres instance. This
produces byte-for-byte identical DDL on Postgres (verified in
`test_models.py`); it's a test-only convenience, not a stack change.

## Frontend

- `GraphCanvas` — Cytoscape.js, `cose` force-directed layout. Nodes colored
  by type (see legend in the filter bar); crown-jewel nodes render as
  diamonds, entry-point nodes get a double border.
- `DetailPanel` — opens on node click, fetches full node detail (including
  `notes`, which the graph endpoint doesn't include to keep that payload
  light), lets you toggle entry-point/crown-jewel, edit notes, delete.
- `FilterBar` — node type, in-scope-only, min CVSS. Re-fetches
  `GET /api/graph` with the corresponding query params on change.
- `CreateNodeModal` / `CreateEdgeModal` — manual graph editing from the UI,
  the frontend counterpart to file ingestion.
- `PathfindPanel` — runs `/api/pathfind/best` or `/api/pathfind/from/{id}`,
  lists results cheapest-first, and highlights the selected chain on the
  canvas (matched nodes/edges get a bright border and thicker line;
  everything else dims). Selecting a path also surfaces a "generate
  narrative" step (editable once generated) and "export .md" / "export
  .json" buttons that trigger a browser download.
- `EngagementSwitcher` — header dropdown to see, switch, and create
  engagements/workspaces. Switching reloads the graph and closes any
  open node/path panels, since they're scoped to the previous workspace.
- `DashboardPanel` — node/edge counts by type, entry-point/crown-jewel
  counts, and the highest-ease chain found, via `/api/engagements/{id}/dashboard`.
- `SnapshotPanel` — capture a labeled snapshot of the current graph, then
  diff any snapshot against the live graph or another snapshot (added/
  removed nodes and edges).
- `CommandPalette` — Ctrl/Cmd+K from anywhere opens a searchable list of
  actions (create node/edge, open path-finder/dashboard/snapshots, clear
  highlight).

## Roadmap

See [`kompromap-spec.md`](./kompromap-spec.md) §7 for the full phased
build plan (Phase 0 scaffold → Phase 1 data layer & parsers → Phase 2 graph
construction & API → Phase 3 visualization → Phase 4 path-finding →
Phase 5 reporting → Phase 6 multi-engagement & polish).
