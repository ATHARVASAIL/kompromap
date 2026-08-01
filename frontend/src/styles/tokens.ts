/**
 * Design tokens — hex constants mirroring the CSS custom properties in
 * index.css exactly. Tailwind utility classes (bg-surface-1, text-accent,
 * border-severity-critical, etc.) are the source of truth for anything
 * that's plain DOM/CSS; this file exists only for the handful of consumers
 * that need a raw hex/color string instead — chiefly Cytoscape.js, whose
 * style API takes its own JS objects and has no notion of Tailwind classes
 * at all.
 *
 * Keep this in sync with index.css's :root block if you touch either.
 */

export const colors = {
  surface: {
    0: "#0A0D12",
    1: "#0F131B",
    2: "#151A24",
    3: "#1C222E",
  },
  border: {
    subtle: "#232A38",
    default: "#2E3648",
    strong: "#3B4459",
  },
  text: {
    primary: "#E7EAF0",
    secondary: "#9099AC",
    tertiary: "#5C6478",
    disabled: "#3E4759",
  },
  accent: "#2DD4E8",
  accentHover: "#5CE1F0",
  // Distinct from the interactive accent on purpose: this marks an active
  // path-finding result (a transient "look here" signal), not a clickable
  // action, so it needs its own identity rather than reusing accent cyan.
  pathPulse: "#FBCB4A",
  severity: {
    critical: "#F2454E",
    high: "#F5883A",
    medium: "#F0C93A",
    low: "#4C8DF0",
    info: "#6B7488",
  },
} as const;

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

/**
 * Findings only store a raw CVSS score (spec's data model has no severity
 * enum — see backend/app/services/reporting.py's scoring notes for the
 * related complexity-field gap), so severity bands are derived from CVSS
 * v3's standard cutoffs: this keeps every part of the UI (graph, badges,
 * tables, dashboard chart) agreeing on the same bands from one place
 * instead of each component inventing its own thresholds.
 */
export function severityFromCvss(cvss: number | null | undefined): Severity {
  if (cvss === null || cvss === undefined) return "info";
  if (cvss >= 9.0) return "critical";
  if (cvss >= 7.0) return "high";
  if (cvss >= 4.0) return "medium";
  if (cvss > 0) return "low";
  return "info";
}

export function severityColor(severity: Severity): string {
  return colors.severity[severity];
}

/**
 * One base Cytoscape node shape per type, on top of the SVG icon — shape
 * carries type identity even at a glance/zoomed-out where the icon inside
 * isn't legible yet. `diamond` is deliberately not used here since it's
 * reserved as the crown-jewel override (see GraphCanvas) — using it for a
 * regular type too would blur that signal.
 */
export const nodeTypeShape = {
  asset: "ellipse",
  service: "round-rectangle",
  web_application: "rectangle",
  endpoint: "round-hexagon",
  credential: "star",
  account: "round-tag",
  data_store: "barrel",
  finding: "triangle",
} as const;

/**
 * One color per graph node type — used for the SVG icon stroke and the
 * chip border in GraphCanvas, plus legend swatches throughout the UI.
 */
export const nodeTypeColor = {
  asset: "#38BDF8",
  service: "#A78BFA",
  web_application: "#E879F9",
  endpoint: "#FBBF24",
  credential: "#FB7185",
  account: "#818CF8",
  data_store: "#EF4444",
  finding: "#F97316",
} as const;
