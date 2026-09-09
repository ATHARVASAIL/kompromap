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

export function generateEngagementReport(
  format: ReportFormat,
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

// --- Deduplication (Phase 2) ---------------------------------------------

export interface DedupScanResponse {
  scan: {
    id: string;
    engagement_id: string;
    created_at: string;
    total_candidates: number;
    high_confidence_count: number;
    merged_count: number;
    dismissed_count: number;
    settings_snapshot: Record<string, unknown>;
  };
  candidates: MergeCandidateRead[];
}

export interface MergeCandidateRead {
  id: string;
  scan_id: string;
  engagement_id: string;
  finding_a_id: string;
  finding_b_id: string;
  dimensions: {
    url_similarity: number;
    endpoint_similarity: number;
    param_similarity: number;
    cwe_similarity: number;
    request_similarity: number;
    response_similarity: number;
  };
  overall_score: number;
  threshold_used: number;
  status: string;
  notes: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface MergeCandidateResolve {
  action: "merged" | "dismissed";
  notes?: string | null;
}

export function runDedupScan(threshold = 0.75): Promise<DedupScanResponse> {
  return fetch(`${API_BASE}/api/dedup/scan`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ threshold }),
  }).then((r) => handle<DedupScanResponse>(r));
}

export function listDedupCandidates(status?: string): Promise<MergeCandidateRead[]> {
  const qs = status ? `?status=${status}` : "";
  return fetch(`${API_BASE}/api/dedup/candidates${qs}`, { headers: authHeaders() }).then((r) =>
    handle<MergeCandidateRead[]>(r),
  );
}

export function resolveDedupCandidate(
  candidateId: string,
  action: "merged" | "dismissed",
  notes?: string | null,
): Promise<MergeCandidateRead> {
  return fetch(`${API_BASE}/api/dedup/candidates/${candidateId}/resolve`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ action, notes }),
  }).then((r) => handle<MergeCandidateRead>(r));
}

// --- Correlation / extended risk (Phase 3) ------------------------------

export interface RiskFactorResponse {
  asset_id: string;
  name: string;
  type: string;
  base_cvss: number;
  criticality: number;
  sensitivity: number;
  exposure: number;
  extended_risk: number;
  finding_count: number;
  critical_findings: number;
  attack_paths_in: number;
}

export interface CorrelationResponse {
  engagement_id: string;
  total_findings: number;
  unique_cwes: number;
  cwe_groups: Record<string | null, Array<Record<string, unknown>>>;
  asset_risks: RiskFactorResponse[];
  assets_exposed: number;
  average_risk: number;
}

export function getCorrelation(): Promise<CorrelationResponse> {
  return fetch(`${API_BASE}/api/correlation`, { headers: authHeaders() }).then((r) =>
    handle<CorrelationResponse>(r),
  );
}

// --- Knowledge base (Phase 5) --------------------------------------------

export interface KBEntry {
  id: string;
  reference_id: string;
  title: string;
  description: string | null;
  source: string;
  severity: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export function searchKnowledgeBase(query: string): Promise<KBEntry[]> {
  const qs = query ? `?q=${encodeURIComponent(query)}` : "";
  return fetch(`${API_BASE}/api/knowledge${qs}`, { headers: authHeaders() }).then((r) =>
    handle<KBEntry[]>(r),
  );
}

export function getKBEntry(id: string): Promise<KBEntry> {
  return fetch(`${API_BASE}/api/knowledge/${id}`, { headers: authHeaders() }).then((r) =>
    handle<KBEntry>(r),
  );
}


// ── Finding generator (Phase 4) ─────────────────────────────────────────

export interface GeneratedFinding {
  title: string;
  description: string;
  severity: string;
  cwe: string | null;
  owasp_category: string | null;
  cvss_score: number | null;
  cvss_vector: string | null;
  exploit_public: boolean;
  auth_required: boolean;
  remediation: string;
  affected_assets: string[];
  evidence: string | null;
  tags: string[];
  assumptions: string[];
}

export interface FindingGenResponse {
  findings: GeneratedFinding[];
  model: string | null;
  generated_at: string | null;
  assumptions: string[];
  note: string;
}

export function generateFindings(payload: {
  node_id: string;
  target_assets?: string[];
  extra_context?: string;
}): Promise<FindingGenResponse> {
  return fetch(`${API_BASE}/api/finding-gen/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  }).then((r) => handle<FindingGenResponse>(r));
}

export function getFindingGenHealth(): Promise<{ configured: boolean; provider: string }> {
  return fetch(`${API_BASE}/api/finding-gen/health`).then((r) => handle(r));
}
