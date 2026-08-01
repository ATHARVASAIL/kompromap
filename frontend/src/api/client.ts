import type {
  DashboardData,
  EdgeDetail,
  EdgeType,
  Engagement,
  ExportResponse,
  GraphDiff,
  GraphFilters,
  GraphResponse,
  NarrativeResponse,
  NodeDetail,
  NodeType,
  PathfindBestResponse,
  PathfindFromResponse,
  ScoringWeights,
  SnapshotDetail,
  SnapshotSummary,
} from "../types/graph";

// Base URL for the API. Empty string (default) assumes the frontend and
// backend share an origin — true for the docker-compose setup and for any
// reverse-proxy deployment that serves both under one domain. Set
// VITE_API_BASE_URL at build time if the frontend is hosted separately
// from the backend (e.g. a static host + a separately hosted API).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      // response wasn't JSON, keep statusText
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function fetchGraph(filters: GraphFilters = {}): Promise<GraphResponse> {
  const params = new URLSearchParams();
  if (filters.node_type) params.set("node_type", filters.node_type);
  if (filters.in_scope_only) params.set("in_scope_only", "true");
  if (filters.min_cvss !== undefined) params.set("min_cvss", String(filters.min_cvss));

  const qs = params.toString();
  return fetch(`${API_BASE}/api/graph${qs ? `?${qs}` : ""}`).then((r) => handle<GraphResponse>(r));
}

export function fetchNode(id: string): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes/${id}`).then((r) => handle<NodeDetail>(r));
}

export function createNode(payload: Record<string, unknown>): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => handle<NodeDetail>(r));
}

export function updateNode(id: string, payload: Record<string, unknown>): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => handle<NodeDetail>(r));
}

export function deleteNode(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/nodes/${id}`, { method: "DELETE" }).then((r) => handle<void>(r));
}

export function createEdge(payload: {
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  weight?: number;
}): Promise<EdgeDetail> {
  return fetch(`${API_BASE}/api/edges`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((r) => handle<EdgeDetail>(r));
}

export function deleteEdge(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/edges/${id}`, { method: "DELETE" }).then((r) => handle<void>(r));
}

export function listNodesByType(nodeType: NodeType): Promise<NodeDetail[]> {
  return fetch(`${API_BASE}/api/nodes?node_type=${nodeType}`).then((r) => handle<NodeDetail[]>(r));
}

export function ingestFile(tool: "nmap" | "nuclei" | "amass" | "burp", file: File, engagementId?: string) {
  const form = new FormData();
  form.append("file", file);
  if (engagementId) form.append("engagement_id", engagementId);
  return fetch(`${API_BASE}/api/ingest/${tool}`, { method: "POST", body: form }).then((r) => handle(r));
}

// --- Engagements -------------------------------------------------------

export function listEngagements(): Promise<Engagement[]> {
  return fetch(`${API_BASE}/api/engagements`).then((r) => handle<Engagement[]>(r));
}

export function getActiveEngagement(): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements/active`).then((r) => handle<Engagement>(r));
}

export function createEngagement(
  name: string,
  clientName?: string,
  activate = true,
): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, client_name: clientName ?? null, activate }),
  }).then((r) => handle<Engagement>(r));
}

export function activateEngagement(id: string): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements/${id}/activate`, { method: "POST" }).then((r) => handle<Engagement>(r));
}

export function deleteEngagement(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/engagements/${id}`, { method: "DELETE" }).then((r) => handle<void>(r));
}

export function getDashboard(engagementId: string): Promise<DashboardData> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/dashboard`).then((r) => handle<DashboardData>(r));
}

// --- Snapshots -----------------------------------------------------------

export function createSnapshot(engagementId: string, label: string): Promise<SnapshotSummary> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/snapshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  }).then((r) => handle<SnapshotSummary>(r));
}

export function listSnapshots(engagementId: string): Promise<SnapshotSummary[]> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/snapshots`).then((r) => handle<SnapshotSummary[]>(r));
}

export function getSnapshot(id: string): Promise<SnapshotDetail> {
  return fetch(`${API_BASE}/api/snapshots/${id}`).then((r) => handle<SnapshotDetail>(r));
}

export function diffSnapshot(id: string, compareTo?: string): Promise<GraphDiff> {
  const qs = compareTo ? `?compare_to=${compareTo}` : "";
  return fetch(`${API_BASE}/api/snapshots/${id}/diff${qs}`).then((r) => handle<GraphDiff>(r));
}

export function deleteSnapshot(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/snapshots/${id}`, { method: "DELETE" }).then((r) => handle<void>(r));
}

export function findBestPaths(weights?: Partial<ScoringWeights>): Promise<PathfindBestResponse> {
  return fetch(`${API_BASE}/api/pathfind/best`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(weights ? { weights } : {}),
  }).then((r) => handle<PathfindBestResponse>(r));
}

export function findPathsFromEntryPoint(
  entryPointId: string,
  weights?: Partial<ScoringWeights>,
): Promise<PathfindFromResponse> {
  return fetch(`${API_BASE}/api/pathfind/from/${entryPointId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(weights ? { weights } : {}),
  }).then((r) => handle<PathfindFromResponse>(r));
}

export function generateNarrative(nodeIds: string[]): Promise<NarrativeResponse> {
  return fetch(`${API_BASE}/api/reports/narrative`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_ids: nodeIds }),
  }).then((r) => handle<NarrativeResponse>(r));
}

export function exportChain(
  nodeIds: string[],
  format: "markdown" | "json",
  narrative?: string,
): Promise<ExportResponse> {
  return fetch(`${API_BASE}/api/reports/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ node_ids: nodeIds, format, ...(narrative ? { narrative } : {}) }),
  }).then((r) => handle<ExportResponse>(r));
}
