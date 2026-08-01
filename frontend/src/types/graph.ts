export type NodeType =
  | "asset"
  | "service"
  | "web_application"
  | "endpoint"
  | "credential"
  | "account"
  | "data_store"
  | "finding";

export type EdgeType =
  | "HOSTS"
  | "EXPOSES"
  | "HAS_FINDING"
  | "YIELDS"
  | "AUTHENTICATES_AS"
  | "GRANTS_ACCESS_TO"
  | "TRUSTS";

export interface GraphNode {
  id: string;
  node_type: NodeType;
  label: string;
  is_entry_point: boolean;
  is_crown_jewel: boolean;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  edge_type: EdgeType;
  weight: number | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphFilters {
  node_type?: NodeType;
  in_scope_only?: boolean;
  min_cvss?: number;
}

// Full per-node detail, as returned by GET /api/nodes/{id} — a superset of
// GraphNode's flattened `properties`, including fields the graph endpoint
// doesn't surface (notes, timestamps).
export interface NodeDetail {
  id: string;
  node_type: NodeType;
  is_entry_point: boolean;
  is_crown_jewel: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

export interface EdgeDetail {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  weight: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface PathNode {
  id: string;
  node_type: NodeType;
  label: string;
}

export interface PathEdgeResult {
  id: string;
  source: string;
  target: string;
  edge_type: EdgeType;
  cost: number;
}

export interface PathResult {
  entry_point: PathNode;
  crown_jewel: PathNode;
  total_cost: number;
  nodes: PathNode[];
  edges: PathEdgeResult[];
}

export interface ScoringWeights {
  cvss: number;
  exploit_public: number;
  auth_required: number;
  complexity: number;
  default_complexity: number;
}

export interface PathfindBestResponse {
  paths: PathResult[];
  unreachable_entry_points: PathNode[];
}

export interface PathfindFromResponse {
  paths: PathResult[];
  unreachable_crown_jewels: PathNode[];
}

export interface NarrativeResponse {
  narrative: string;
  narrative_source: "llm" | "template";
}

export interface ExportResponse {
  format: "markdown" | "json";
  narrative_source: "llm" | "template";
  content: string | null;
  data: Record<string, unknown> | null;
}

export interface Engagement {
  id: string;
  name: string;
  client_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SnapshotSummary {
  id: string;
  engagement_id: string;
  label: string;
  node_count: number;
  edge_count: number;
  created_at: string;
}

export interface SnapshotDetail extends SnapshotSummary {
  data: GraphResponse;
}

export interface DiffEntry {
  id: string;
  label: string;
  node_type?: string;
  edge_type?: string;
}

export interface GraphDiff {
  nodes_added: DiffEntry[];
  nodes_removed: DiffEntry[];
  edges_added: DiffEntry[];
  edges_removed: DiffEntry[];
}

export interface DashboardData {
  total_nodes: number;
  total_edges: number;
  node_counts_by_type: Record<string, number>;
  edge_counts_by_type: Record<string, number>;
  entry_point_count: number;
  crown_jewel_count: number;
  paths_to_crown_jewels_count: number;
  highest_ease_chain: PathResult | null;
}

export const NODE_TYPE_LABELS: Record<NodeType, string> = {
  asset: "Asset",
  service: "Service",
  web_application: "Web Application",
  endpoint: "Endpoint",
  credential: "Credential",
  account: "Account",
  data_store: "Data Store",
  finding: "Finding",
};

export const EDGE_TYPE_LABELS: Record<EdgeType, string> = {
  HOSTS: "hosts",
  EXPOSES: "exposes",
  HAS_FINDING: "has finding",
  YIELDS: "yields",
  AUTHENTICATES_AS: "authenticates as",
  GRANTS_ACCESS_TO: "grants access to",
  TRUSTS: "trusts",
};

// Colors for graph nodes/edges are centralized in src/styles/tokens.ts —
// re-exported here under the original name so every existing import site
// keeps working unmodified.
export { nodeTypeColor as NODE_TYPE_COLOR } from "../styles/tokens";
