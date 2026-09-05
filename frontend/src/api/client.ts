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

// Optional API key, matching the backend's API_KEY setting. Unset in local
// single-user mode. Note this is baked into the built bundle and therefore
// visible to anyone who loads the page — it gates casual/anonymous access
// to a self-hosted instance, it is not a per-user secret. See
// app/core/security.py and DEPLOYMENT.md for the threat model.
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return API_KEY ? { ...extra, "X-API-Key": API_KEY } : extra;
}

const JSON_HEADERS = () => authHeaders({ "Content-Type": "application/json" });

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
  return fetch(`${API_BASE}/api/graph${qs ? `?${qs}` : ""}`, { headers: authHeaders() }).then((r) =>
    handle<GraphResponse>(r),
  );
}

export function fetchNode(id: string): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes/${id}`, { headers: authHeaders() }).then((r) => handle<NodeDetail>(r));
}

export function createNode(payload: Record<string, unknown>): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(payload),
  }).then((r) => handle<NodeDetail>(r));
}

export function updateNode(id: string, payload: Record<string, unknown>): Promise<NodeDetail> {
  return fetch(`${API_BASE}/api/nodes/${id}`, {
    method: "PATCH",
    headers: JSON_HEADERS(),
    body: JSON.stringify(payload),
  }).then((r) => handle<NodeDetail>(r));
}

export function deleteNode(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/nodes/${id}`, { method: "DELETE", headers: authHeaders() }).then((r) => handle<void>(r));
}

export function createEdge(payload: {
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  weight?: number;
}): Promise<EdgeDetail> {
  return fetch(`${API_BASE}/api/edges`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(payload),
  }).then((r) => handle<EdgeDetail>(r));
}

export function deleteEdge(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/edges/${id}`, { method: "DELETE", headers: authHeaders() }).then((r) => handle<void>(r));
}

export function listNodesByType(nodeType: NodeType): Promise<NodeDetail[]> {
  return fetch(`${API_BASE}/api/nodes?node_type=${nodeType}`, { headers: authHeaders() }).then((r) => handle<NodeDetail[]>(r));
}

export function ingestFile(tool: "nmap" | "nuclei" | "amass" | "burp", file: File, engagementId?: string) {
  const form = new FormData();
  form.append("file", file);
  if (engagementId) form.append("engagement_id", engagementId);
  return fetch(`${API_BASE}/api/ingest/${tool}`, { method: "POST", body: form, headers: authHeaders() }).then((r) => handle(r));
}

// --- Engagements -------------------------------------------------------

export function listEngagements(): Promise<Engagement[]> {
  return fetch(`${API_BASE}/api/engagements`, { headers: authHeaders() }).then((r) => handle<Engagement[]>(r));
}

export function getActiveEngagement(): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements/active`, { headers: authHeaders() }).then((r) => handle<Engagement>(r));
}

export function createEngagement(
  name: string,
  clientName?: string,
  activate = true,
): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ name, client_name: clientName ?? null, activate }),
  }).then((r) => handle<Engagement>(r));
}

export function activateEngagement(id: string): Promise<Engagement> {
  return fetch(`${API_BASE}/api/engagements/${id}/activate`, { method: "POST", headers: authHeaders() }).then((r) => handle<Engagement>(r));
}

export function deleteEngagement(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/engagements/${id}`, { method: "DELETE", headers: authHeaders() }).then((r) => handle<void>(r));
}

export function getDashboard(engagementId: string): Promise<DashboardData> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/dashboard`, { headers: authHeaders() }).then((r) => handle<DashboardData>(r));
}

// --- Snapshots -----------------------------------------------------------

export function createSnapshot(engagementId: string, label: string): Promise<SnapshotSummary> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/snapshots`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ label }),
  }).then((r) => handle<SnapshotSummary>(r));
}

export function listSnapshots(engagementId: string): Promise<SnapshotSummary[]> {
  return fetch(`${API_BASE}/api/engagements/${engagementId}/snapshots`, { headers: authHeaders() }).then((r) => handle<SnapshotSummary[]>(r));
}

export function getSnapshot(id: string): Promise<SnapshotDetail> {
  return fetch(`${API_BASE}/api/snapshots/${id}`, { headers: authHeaders() }).then((r) => handle<SnapshotDetail>(r));
}

export function diffSnapshot(id: string, compareTo?: string): Promise<GraphDiff> {
  const qs = compareTo ? `?compare_to=${compareTo}` : "";
  return fetch(`${API_BASE}/api/snapshots/${id}/diff${qs}`, { headers: authHeaders() }).then((r) => handle<GraphDiff>(r));
}

export function deleteSnapshot(id: string): Promise<void> {
  return fetch(`${API_BASE}/api/snapshots/${id}`, { method: "DELETE", headers: authHeaders() }).then((r) => handle<void>(r));
}

export function findBestPaths(weights?: Partial<ScoringWeights>): Promise<PathfindBestResponse> {
  return fetch(`${API_BASE}/api/pathfind/best`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(weights ? { weights } : {}),
  }).then((r) => handle<PathfindBestResponse>(r));
}

export function findPathsFromEntryPoint(
  entryPointId: string,
  weights?: Partial<ScoringWeights>,
): Promise<PathfindFromResponse> {
  return fetch(`${API_BASE}/api/pathfind/from/${entryPointId}`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(weights ? { weights } : {}),
  }).then((r) => handle<PathfindFromResponse>(r));
}

export function generateNarrative(nodeIds: string[]): Promise<NarrativeResponse> {
  return fetch(`${API_BASE}/api/reports/narrative`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ node_ids: nodeIds }),
  }).then((r) => handle<NarrativeResponse>(r));
}

export type ReportFormat = "json" | "markdown" | "html" | "docx" | "pdf";

export interface EngagementReportResponse {
  format: ReportFormat;
  content?: string;
  data?: Record<string, unknown>;
}

/** Full engagement report — every finding, chain, scope item and caveat. */
// --- AI triage ------------------------------------------------------

export type TriageAssessment = "likely_valid" | "likely_false_positive" | "insufficient_evidence";
export type TriageSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface AITriageResult {
  assessment: TriageAssessment;
  confidence: number;
  severity: TriageSeverity;
  reasoning_summary: string;
  evidence_supporting: string[];
  evidence_missing: string[];
  assumptions: string[];
  recommended_validation: string[];
  potential_impact: string[];
  related_vulnerability_types: string[];
}

export interface TriageResponse {
  finding_id: string;
  available: boolean;
  assessment?: AITriageResult | null;
  error?: string | null;
  model?: string | null;
  analyzed_at?: string | null;
  /** Always true. Restated per-response so a client can't render an
   *  assessment without having been told it's advisory. */
  advisory_only: boolean;
}

export interface TriageStatus {
  available: boolean;
  provider: string;
  reason?: string | null;
}

export interface GeneratedFinding {
  title: string;
  description: string;
  remediation_steps: string[];
  references: string[];
  confidence: number;
}

export interface FindingGenResponse {
  finding_id: string;
  available: boolean;
  generated: GeneratedFinding | null;
  error?: string | null;
  model?: string | null;
}

export interface FindingGenStatus {
  available: boolean;
  provider: string;
  reason?: string | null;
}

export function getTriageStatus(): Promise<TriageStatus> {
  return fetch(`${API_BASE}/api/triage/status`, { headers: authHeaders() }).then((r) =>
    handle<TriageStatus>(r),
  );
}

export function analyzeFinding(findingId: string): Promise<TriageResponse> {
  return fetch(`${API_BASE}/api/triage/findings/${findingId}/analyze`, {
    method: "POST",
    headers: authHeaders(),
  }).then((r) => handle<TriageResponse>(r));
}

export function getFindingAssessment(findingId: string): Promise<TriageResponse> {
  return fetch(`${API_BASE}/api/triage/findings/${findingId}`, {
    headers: authHeaders(),
  }).then((r) => handle<TriageResponse>(r));
}

export function getFindingGenStatus(): Promise<FindingGenStatus> {
  return fetch(`${API_BASE}/api/finding-gen/status`, { headers: authHeaders() }).then((r) =>
    handle<FindingGenStatus>(r),
  );
}

export function generateFindingDescription(findingId: string): Promise<FindingGenResponse> {
  return fetch(`${API_BASE}/api/finding-gen/generate`, {
    method: "POST",
    headers: { ...JSON_HEADERS(), ...authHeaders() },
    body: JSON.stringify({ finding_id: findingId }),
  }).then((r) => handle<FindingGenResponse>(r));
}

// ── Knowledge base ──────────────────────────────────────────────────────
export interface KnowledgeBaseEntryResponse {
  id: string;
  cwe_id: string | null;
  name: string;
  description: string;
  remediation: string;
  references: string[];
  tags: string[];
  owasp_category: string | null;
  severity_guidance: string | null;
  created_at: string;
  updated_at: string;
}

export interface SimilarSearchResponse {
  query_cwe: string | null;
  query_tags: string[];
  matches: {
    entry_id: string;
    cwe_id: string | null;
    name: string;
    score: number;
    match_reason: string;
  }[];
}

export function getKbEntries(opts?: { cweId?: string; tag?: string; search?: string; limit?: number }): Promise<KnowledgeBaseEntryResponse[]> {
  const params = new URLSearchParams();
  if (opts?.cweId) params.set("cwe_id", opts.cweId);
  if (opts?.tag) params.set("tag", opts.tag);
  if (opts?.search) params.set("search", opts.search);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetch(`${API_BASE}/api/knowledge-base/${qs ? "?" + qs : ""}`, { headers: authHeaders() })
    .then((r) => handle<KnowledgeBaseEntryResponse[]>(r));
}

export function seedKb(): Promise<{ inserted: number }> {
  return fetch(`${API_BASE}/api/knowledge-base/seed`, {
    method: "POST",
    headers: authHeaders(),
  }).then((r) => handle<{ inserted: number }>(r));
}

export function searchKbSimilar(
  payload: { cwe_id?: string; tags?: string[]; description?: string; top_n?: number; min_score?: number },
): Promise<SimilarSearchResponse> {
  return fetch(`${API_BASE}/api/knowledge-base/search`, {
    method: "POST",
    headers: { ...JSON_HEADERS(), ...authHeaders() },
    body: JSON.stringify(payload),
  }).then((r) => handle<SimilarSearchResponse>(r));
}

export function generateEngagementReport(
  format: Exclude<ReportFormat, "docx" | "pdf">,
  opts: { engagementId?: string; includeNarratives?: boolean; weights?: ScoringWeights } = {},
): Promise<EngagementReportResponse> {
  return fetch(`${API_BASE}/api/reports/engagement`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({
      format,
      ...(opts.engagementId ? { engagement_id: opts.engagementId } : {}),
      include_narratives: opts.includeNarratives ?? false,
      ...(opts.weights ? { weights: opts.weights } : {}),
    }),
  }).then((r) => handle<EngagementReportResponse>(r));
}

export function downloadEngagementReport(
  format: "docx" | "pdf",
  opts: { engagementId?: string; includeNarratives?: boolean; weights?: ScoringWeights } = {},
): Promise<{ blob: Blob; filename: string; format: string }> {
  return fetch(`${API_BASE}/api/reports/engagement`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({
      format,
      ...(opts.engagementId ? { engagement_id: opts.engagementId } : {}),
      include_narratives: opts.includeNarratives ?? false,
      ...(opts.weights ? { weights: opts.weights } : {}),
    }),
  }).then((r) => {
    if (!r.ok) return handle<never>(r);
    const contentDisposition = r.headers.get("content-disposition") || "";
    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
    const filename = filenameMatch ? filenameMatch[1] : `report.${format}`;
    const detectedFormat = r.headers.get("content-type")?.includes("pdf") ? "pdf" : "html-fallback";
    return r.blob().then((blob) => ({ blob, filename, format: detectedFormat }));
  });
}

export function exportChain(
  nodeIds: string[],
  format: "markdown" | "json",
  narrative?: string,
): Promise<ExportResponse> {
  return fetch(`${API_BASE}/api/reports/export`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ node_ids: nodeIds, format, ...(narrative ? { narrative } : {}) }),
  }).then((r) => handle<ExportResponse>(r));
}

// --- Dedup ----------------------------------------------------------

export interface DedupScanResponse {
  id: string;
  engagement_id: string;
  similarity_threshold: number;
  signals: string[];
  candidates_found: number;
  candidates_filtered: number;
  created_at: string;
}

export interface MergeCandidateResponse {
  id: string;
  scan_id: string;
  finding_a_id: string;
  finding_b_id: string;
  signal_scores: Record<string, number>;
  overall_score: number;
  high_impact: boolean;
  action: string;
  kept_id: string | null;
  analyst_note: string | null;
  resolved_at: string | null;
  created_at: string;
  finding_a_title: string;
  finding_b_title: string;
}

export interface MergeCandidateActionPayload {
  action: "merge" | "keep_separate" | "mark_duplicate";
  kept_id?: string;
  analyst_note?: string;
}

export function runDedupScan(payload: { similarity_threshold?: number; signals?: string[]; weights?: Record<string, number> } = {}): Promise<DedupScanResponse> {
  return fetch(`${API_BASE}/api/dedup/scan`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(payload),
  }).then((r) => handle<DedupScanResponse>(r));
}

export function listDedupScans(engagementId?: string): Promise<DedupScanResponse[]> {
  const qs = engagementId ? `?engagement_id=${engagementId}` : "";
  return fetch(`${API_BASE}/api/dedup/scans${qs}`, { headers: authHeaders() }).then((r) =>
    handle<DedupScanResponse[]>(r),
  );
}

export function getDedupScan(scanId: string): Promise<DedupScanResponse> {
  return fetch(`${API_BASE}/api/dedup/scans/${scanId}`, { headers: authHeaders() }).then((r) =>
    handle<DedupScanResponse>(r),
  );
}

export function getDedupCandidates(scanId: string, action?: string): Promise<MergeCandidateResponse[]> {
  const qs = action ? `?action=${action}` : "";
  return fetch(`${API_BASE}/api/dedup/scans/${scanId}/candidates${qs}`, { headers: authHeaders() }).then((r) =>
    handle<MergeCandidateResponse[]>(r),
  );
}

export function resolveDedupCandidate(
  candidateId: string,
  payload: MergeCandidateActionPayload,
): Promise<{ id: string; action: string; kept_id: string | null; analyst_note: string | null; resolved_at: string | null }> {
  return fetch(`${API_BASE}/api/dedup/candidates/${candidateId}/resolve`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(payload),
  }).then((r) => handle(r));
}
