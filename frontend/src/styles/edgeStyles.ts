/**
 * Per-edge-type visual language. Every edge type gets a genuinely distinct
 * {color, line-style, arrowhead} combination — not just a color swap —
 * so the relationship type is readable even in grayscale or from the
 * edge's silhouette alone.
 *
 * YIELDS is deliberately the loudest (thickest, brightest, most severity-
 * critical-adjacent): per spec §4/scoring.ts, it's the one edge type that
 * represents an actual exploitation step with a real cost, not just an
 * observed structural relationship — the visual weight should match that.
 */
import type { EdgeType } from "../types/graph";
import { colors } from "./tokens";

export interface EdgeVisualStyle {
  color: string;
  lineStyle: "solid" | "dashed" | "dotted";
  arrowShape: string;
  width: number;
}

export const EDGE_TYPE_STYLE: Record<EdgeType, EdgeVisualStyle> = {
  HOSTS: { color: colors.border.strong, lineStyle: "solid", arrowShape: "triangle", width: 1.5 },
  EXPOSES: { color: colors.text.tertiary, lineStyle: "solid", arrowShape: "vee", width: 1.5 },
  HAS_FINDING: { color: colors.severity.high, lineStyle: "dashed", arrowShape: "triangle", width: 1.5 },
  YIELDS: { color: colors.severity.critical, lineStyle: "solid", arrowShape: "chevron", width: 2.75 },
  AUTHENTICATES_AS: { color: colors.severity.medium, lineStyle: "dashed", arrowShape: "diamond", width: 1.5 },
  GRANTS_ACCESS_TO: { color: colors.accent, lineStyle: "solid", arrowShape: "triangle-backcurve", width: 2 },
  TRUSTS: { color: colors.text.secondary, lineStyle: "dotted", arrowShape: "circle", width: 1.2 },
};
