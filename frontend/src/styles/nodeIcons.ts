/**
 * One small line-art SVG icon per node type, rendered as a Cytoscape
 * `background-image` data URI on top of each node's shape+color. Kept
 * deliberately simple (few primitives, no fine detail) — these render at
 * ~16px inside a graph node, so anything intricate would just turn to
 * mud at that size.
 *
 * Icon stroke is white — every node-type fill color in tokens.ts is
 * saturated/mid-brightness, so white reads clearly against all of them
 * without needing a per-type icon color.
 */
import type { NodeType } from "../types/graph";

const STROKE = "#FFFFFF";

function icon(inner: string): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ` +
    `stroke="${STROKE}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

// prettier-ignore
const ICON_MARKUP: Record<NodeType, string> = {
  // Monitor — a host/domain/IP on the attack surface
  asset: icon(`<rect x="3" y="4" width="18" height="12" rx="1"/><line x1="8" y1="20" x2="16" y2="20"/><line x1="12" y1="16" x2="12" y2="20"/>`),
  // Chip — a running process/service on a port
  service: icon(`<rect x="7" y="7" width="10" height="10" rx="1"/><line x1="7" y1="3" x2="7" y2="7"/><line x1="17" y1="3" x2="17" y2="7"/><line x1="7" y1="17" x2="7" y2="21"/><line x1="17" y1="17" x2="17" y2="21"/><line x1="3" y1="7" x2="7" y2="7"/><line x1="17" y1="7" x2="21" y2="7"/><line x1="3" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="21" y2="17"/>`),
  // Browser window — an app running on that service
  web_application: icon(`<rect x="3" y="4" width="18" height="16" rx="1"/><line x1="3" y1="9" x2="21" y2="9"/>`),
  // Route arrow — a specific path/route on that app
  endpoint: icon(`<path d="M4 12h12"/><path d="M12 6l6 6-6 6"/>`),
  // Key — a credential obtained during testing
  credential: icon(`<circle cx="7" cy="12" r="4"/><line x1="11" y1="12" x2="21" y2="12"/><line x1="17" y1="12" x2="17" y2="16"/><line x1="21" y1="12" x2="21" y2="15"/>`),
  // Person — a user or service account
  account: icon(`<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/>`),
  // Database cylinder — a data store
  data_store: icon(`<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>`),
  // Exclamation — a finding/vulnerability (node shape is already a triangle, so no outline here)
  finding: icon(`<line x1="12" y1="7" x2="12" y2="13"/><circle cx="12" cy="17" r="1" fill="${STROKE}" stroke="none"/>`),
};

export const NODE_TYPE_ICON: Record<NodeType, string> = ICON_MARKUP;

/**
 * Cytoscape shape per node type — chosen for a real (if lightweight)
 * metaphor rather than arbitrarily, and specifically NOT reusing diamond,
 * since that shape used to mean "crown jewel" in the previous styling.
 * Crown-jewel/entry-point status is now conveyed by a glow (see
 * GraphCanvas's underlay-* styles), so shape is free to mean "type" only.
 */
export const NODE_TYPE_SHAPE: Record<NodeType, string> = {
  asset: "hexagon", // a host with many possible connections
  service: "round-rectangle", // a process block
  web_application: "round-tag", // a bookmarked/labeled app
  endpoint: "rhomboid", // a route/path
  credential: "round-diamond", // a gem/key
  account: "ellipse", // a person
  data_store: "barrel", // a cylinder — the classic database glyph
  finding: "triangle", // a warning
};
