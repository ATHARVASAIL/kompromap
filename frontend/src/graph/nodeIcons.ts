/**
 * One small line-icon per node type, rendered as a data-URI so Cytoscape
 * can use it as a node's `background-image`. Cytoscape's style API draws
 * these as plain images — there's no way to recolor an SVG at render time
 * the way you'd recolor with CSS `fill: currentColor` — so each icon is
 * generated once per type with that type's color already baked in, and
 * cached in nodeIconDataUri() below rather than re-encoded on every render.
 *
 * Icons are deliberately simple 24x24 stroke glyphs (no fills, ~1.6 stroke
 * width, round joins) so they read clearly at the small sizes a graph node
 * actually renders at, rather than detailed illustrations that turn to
 * mush below ~28px.
 */
import { nodeTypeColor } from "../styles/tokens";
import type { NodeType } from "../types/graph";

function svg(inner: string, color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
}

const ICON_BODY: Record<NodeType, string> = {
  // Globe — Asset (a domain/host/IP is a point on the network)
  asset: `
    <circle cx="12" cy="12" r="8.5" />
    <ellipse cx="12" cy="12" rx="3.6" ry="8.5" />
    <path d="M3.7 9.5h16.6M3.7 14.5h16.6" />
  `,
  // Plug — Service (a port/protocol running on an asset)
  service: `
    <path d="M9 2v5M15 2v5" />
    <path d="M6.5 7h11v4a5.5 5.5 0 0 1-11 0V7Z" />
    <path d="M12 16.5V21" />
  `,
  // Browser window — WebApplication
  web_application: `
    <rect x="3" y="4.5" width="18" height="15" rx="1.6" />
    <path d="M3 9h18" />
    <circle cx="6.2" cy="6.7" r="0.6" fill="__COLOR__" stroke="none" />
    <circle cx="8.4" cy="6.7" r="0.6" fill="__COLOR__" stroke="none" />
  `,
  // Signpost / route — Endpoint (a specific path on that app)
  endpoint: `
    <path d="M12 3v18" />
    <path d="M12 6h6.5L21 8.5 18.5 11H12" />
    <path d="M12 14H6.5L4 16.5 6.5 19H12" />
  `,
  // Key — Credential
  credential: `
    <circle cx="8" cy="15.5" r="4.3" />
    <path d="M11.2 12.3 19 4.5" />
    <path d="M15.5 8 18 10.5M18.3 5.2 21 7.9" />
  `,
  // Person — Account
  account: `
    <circle cx="12" cy="8" r="4" />
    <path d="M4.5 20.5c0-4.2 3.4-7 7.5-7s7.5 2.8 7.5 7" />
  `,
  // Cylinder — DataStore
  data_store: `
    <ellipse cx="12" cy="6" rx="7.5" ry="3" />
    <path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6" />
    <path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" />
  `,
  // Alert triangle — Finding (a vulnerability)
  finding: `
    <path d="M12 3.5 21.5 20h-19L12 3.5Z" />
    <path d="M12 10v4.2" />
    <circle cx="12" cy="17" r="0.75" fill="__COLOR__" stroke="none" />
  `,
};

function toDataUri(type: NodeType): string {
  const color = nodeTypeColor[type];
  // The two icons with small filled dots need the literal color substituted
  // in — `currentColor` doesn't resolve inside a standalone data-URI image
  // the way it would in inline DOM SVG, so a placeholder is swapped instead.
  const body = ICON_BODY[type].replace(/__COLOR__/g, color);
  const markup = svg(body, color);
  return `data:image/svg+xml;utf8,${encodeURIComponent(markup)}`;
}

const cache = new Map<NodeType, string>();
export function nodeIconDataUri(type: NodeType): string {
  let uri = cache.get(type);
  if (!uri) {
    uri = toDataUri(type);
    cache.set(type, uri);
  }
  return uri;
}
