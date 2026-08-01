# Kompromap — Project Specification

## 1. Overview
Kompromap ingests recon and vulnerability data from a VAPT engagement (Nmap, Nuclei, Amass/Subfinder, Burp/ZAP exports, manual findings) and builds an attack-chain graph: a visual, queryable map of how individual weaknesses connect into a full compromise path.

Instead of a flat CVSS-sorted findings table, the tester sees something like:

```
[Subdomain takeover: dev.client.com]
 → [Stored XSS on admin login page]
 → [Session cookie theft]
 → [IDOR on /api/v2/users/{id}]
 → [PII dump — 40,000 records]
```

The graph answers the question every pentest report tries to answer in prose: "what's the actual path from an unauthenticated attacker to the thing that matters?"

## 2. Problem & Why This Is Different
Graph-based attack-path tooling exists today, but only for identity/permission graphs — BloodHound (and its OpenGraph extension) maps who-can-access-what across Active Directory, Azure, GitHub, Snowflake, MSSQL. That's a different problem: it graphs privilege relationships within one identity system, not a chain of independent technical vulnerabilities across an external web/API attack surface that a VAPT engagement actually produces (a subdomain takeover, a filter-bypass XSS, an IDOR, a misconfigured S3 bucket — none of which share an identity provider).

No existing tool takes raw pentest tool output + manual findings and auto-assembles them into a chain graph with a "most likely/most damaging path" query. That's the gap Kompromap fills.

## 3. Core Concept
- **Nodes** = things in the environment (assets, services, endpoints, credentials, accounts, data stores) and the findings attached to them.
- **Edges** = relationships, including "exploit" edges that represent "this finding gets you from node A to node B."
- **Path-finding** = given one or more entry points (internet-facing assets with findings) and one or more crown jewels (tagged critical data stores/accounts), compute the easiest/most damaging path through the graph.
- **Scoring** = each exploit edge gets an "ease" score from CVSS + exploit public availability + auth required + complexity, so path-finding isn't just shortest-hop-count, it's most-realistic-chain.

## 4. Data Model

### Node types
| Node type | Purpose | Key properties |
|---|---|---|
| Asset | domain, subdomain, IP, host, cloud resource | name, type (domain/subdomain/ip/cloud_resource), in_scope (bool), tags |
| Service | a port/protocol on an asset | port, protocol, banner, tech_stack |
| WebApplication | an app running on a service | name, base_url, tech_stack, auth_type |
| Endpoint | a specific route/page/API path | path, method, params, requires_auth (bool), documented (bool) |
| Credential | a password/token/key obtained during testing | cred_type (password/api_key/session_token/ssh_key), scope, obtained_via_finding_id |
| Account | a user or service account | username, privilege_level (admin/standard/service) |
| DataStore | a database, bucket, file share | name, data_classification (PII/PCI/none), record_count_estimate, is_crown_jewel (bool) |
| Finding | a vulnerability | title, cwe, owasp_category, cvss_score, exploit_public (bool), auth_required (bool), evidence (text/screenshot refs), status (open/fixed/accepted-risk) |

### Edge types
| Edge type | From → To | Meaning |
|---|---|---|
| HOSTS | Asset → Service | asset runs this service |
| EXPOSES | Service → WebApplication/Endpoint | service serves this app/route |
| HAS_FINDING | Asset/Endpoint → Finding | this finding was found here |
| YIELDS | Finding → Credential/Account/DataStore | exploiting this finding gets you this |
| AUTHENTICATES_AS | Credential → Account | this credential logs in as this account |
| GRANTS_ACCESS_TO | Account → Asset/Endpoint/DataStore | this account can reach this |
| TRUSTS | Asset → Asset | e.g. SSRF pivot, subdomain takeover implications, shared session domain |

### Edge weight (for path-finding)
```
ease_score = normalize(cvss_score) * 0.4
           + exploit_public_availability * 0.3
           + (1 - auth_required) * 0.2
           + (1 - complexity) * 0.1
```
Path-finding cost = `1 - ease_score`, so Dijkstra's shortest path = the most realistic/likely chain, not just fewest hops.

## 5. Features

### MVP (must-have)
- Manual finding entry form (create nodes/edges by hand)
- Import parsers: Nmap XML, Nuclei JSON, Amass/Subfinder output, Burp/ZAP XML export
- Graph auto-construction from parsed + manual data
- Interactive graph visualization: pan/zoom, click a node for a detail panel (evidence, CVSS, notes)
- Filter graph by node type, severity, in-scope/out-of-scope
- Tag nodes as "entry point" or "crown jewel"

### Phase 2 (core differentiator)
- Path-finding engine: "show the easiest path to any crown jewel," "show all paths from this entry point"
- Configurable scoring weights (per engagement, since risk appetite differs bank vs. ecommerce client)
- Visual highlight of the winning chain (color + thickness on the graph)

### Phase 3 (reporting integration)
- Auto-generated plain-English chain narrative (LLM call: "describe this path as a paragraph for a pentest report")
- Export a chain (graph + narrative + evidence) as Markdown/JSON — designed to slot into your existing report builder
- Export graph view as PNG/SVG for report screenshots

### Phase 4 (workflow polish)
- Multiple engagements/workspaces, each with its own isolated graph
- Snapshot history — compare the graph at engagement start vs. after further testing
- Command palette (same pattern as your VAPT Console)
- Dashboard: node/edge counts, number of paths to crown jewels, highest-ease chain found

### Stretch (later)
- Migrate graph storage to Neo4j if a single engagement graph gets large enough that in-memory NetworkX gets slow
- Multi-user auth/roles if this becomes a team tool instead of solo
- "What haven't you tested yet" suggestions — LLM flags entry points with findings but no onward edges, meaning the chain might dead-end because nobody looked further

## 6. Architecture & Tech Stack
Keep this lean for v1 — no reason to run a graph database for a tool that's scoped to one engagement's worth of nodes (hundreds, not millions).

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy
- **Storage:** PostgreSQL — relational nodes and edges tables (adjacency-list style: `edges(id, source_node_id, target_node_id, edge_type, weight, metadata)`). Load into NetworkX in memory for graph algorithms (shortest path, centrality) on request; no separate graph DB needed at this scale.
- **Frontend:** React + TypeScript + Tailwind
- **Graph rendering:** Cytoscape.js (built for network graphs, has automatic layout algorithms — force-directed, hierarchical — and good interaction/filtering support out of the box)
- **Parsers:** one Python module per source tool, each normalizing to a common internal schema before it touches the DB:
  - `parsers/nmap.py` — Nmap XML (`-oX`) → Asset + Service nodes
  - `parsers/nuclei.py` — Nuclei JSON output → Finding nodes attached to Asset/Endpoint
  - `parsers/amass.py` — Amass/Subfinder output (txt/json) → Asset (subdomain) nodes
  - `parsers/burp.py` — Burp/ZAP XML export → Endpoint nodes + any findings tagged in Burp
- **Optional LLM integration:** Anthropic API (Claude) for the narrative-generation feature in Phase 3 — pass the winning path's nodes/edges/evidence as structured context, ask for a plain-English paragraph.
- **Auth:** none for v1 (single-user local tool). Add basic session auth only if/when this becomes multi-user.

## 7. Build Roadmap (Phased Walkthrough)

- **Phase 0 — Scaffold:** Repo structure (backend/ frontend/), docker-compose for Postgres, FastAPI health-check endpoint, React app skeleton, README with setup instructions.
- **Phase 1 — Data layer:** SQLAlchemy models for the node/edge schema above. Alembic migrations. The four parsers, each with unit tests against a small sample output file for that tool (check in a few real sanitized sample files from your own recon runs).
- **Phase 2 — Graph construction + API:** Endpoints to: upload a parser file and ingest it, manually create/edit nodes and edges, list/query the graph for an engagement. Load graph into NetworkX on read.
- **Phase 3 — Visualization:** Cytoscape.js graph view wired to the API. Node click → detail panel. Filter controls (type, severity, in-scope). Manual node/edge creation from the UI.
- **Phase 4 — Path-finding:** Tag entry points and crown jewels in the UI. Backend endpoint that runs weighted shortest-path (Dijkstra via NetworkX) from entry points to crown jewels. Highlight the result on the graph.
- **Phase 5 — Reporting:** LLM narrative generation for a selected path. Export path (graph + narrative + evidence) as Markdown/JSON.
- **Phase 6 — Multi-engagement + polish:** Workspace/engagement switcher, graph snapshots over time, command palette, dashboard stats, dark theme.
