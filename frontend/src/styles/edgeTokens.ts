/**
 * One visual treatment per edge type, so the graph reads its own legend at
 * a glance instead of everything being a uniform gray line. Grouped by
 * what the edge type actually represents:
 *
 * - HOSTS / EXPOSES: structural, observed infrastructure — solid, calm,
 *   neutral-toned.
 * - HAS_FINDING: "a finding lives here" — dashed, tinted to match the
 *   Finding node color so the eye can trace "this is where it was found."
 * - YIELDS: the one edge type that's an actual exploitation step (see
 *   backend app/services/scoring.py) — the only edge that gets real
 *   weight in path-finding, so it's visually the loudest: solid, thicker,
 *   colored with the severity-critical red.
 * - AUTHENTICATES_AS / GRANTS_ACCESS_TO: credential/account-tinted to
 *   match those node types, since they represent using something you
 *   obtained rather than a structural fact.
 * - TRUSTS: an inferred/implicit relationship (subdomain takeover
 *   implications, shared session domain) — a distinct dash-dot pattern
 *   marks it as "worth noting, not directly observed."
 */
import { colors, nodeTypeColor, severityColor } from "./tokens";
import type { EdgeType } from "../types/graph";

export interface EdgeStyle {
  color: string;
  lineStyle: "solid" | "dashed" | "dotted";
  dashPattern?: [number, number] | [number, number, number, number];
  arrowShape: string;
  width: number;
}

export const edgeTypeStyle: Record<EdgeType, EdgeStyle> = {
  HOSTS: {
    color: colors.border.strong,
    lineStyle: "solid",
    arrowShape: "triangle",
    width: 1.5,
  },
  EXPOSES: {
    color: "#5B7A9E",
    lineStyle: "solid",
    arrowShape: "triangle-tee",
    width: 1.5,
  },
  HAS_FINDING: {
    color: nodeTypeColor.finding,
    lineStyle: "dashed",
    dashPattern: [6, 3],
    arrowShape: "vee",
    width: 1.5,
  },
  YIELDS: {
    color: severityColor("critical"),
    lineStyle: "solid",
    arrowShape: "triangle",
    width: 2.5,
  },
  AUTHENTICATES_AS: {
    color: nodeTypeColor.credential,
    lineStyle: "dashed",
    dashPattern: [4, 3],
    arrowShape: "diamond",
    width: 1.5,
  },
  GRANTS_ACCESS_TO: {
    color: nodeTypeColor.account,
    lineStyle: "dotted",
    arrowShape: "circle",
    width: 1.5,
  },
  TRUSTS: {
    color: colors.text.tertiary,
    lineStyle: "dashed",
    dashPattern: [6, 3, 1, 3],
    arrowShape: "tee",
    width: 1.5,
  },
};
