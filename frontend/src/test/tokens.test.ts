/**
 * Design-token and severity-banding tests.
 *
 * severityFromCvss() is shared by the findings table, the severity badges
 * and the dashboard chart, so a regression here mislabels risk everywhere
 * at once — quietly, since nothing throws.
 */
import { describe, expect, it } from "vitest";
import {
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  colors,
  nodeTypeColor,
  nodeTypeShape,
  severityColor,
  severityFromCvss,
} from "../styles/tokens";
import { edgeTypeStyle } from "../styles/edgeTokens";
import { nodeIconDataUri } from "../graph/nodeIcons";
import { EDGE_TYPE_LABELS, NODE_TYPE_LABELS, type EdgeType, type NodeType } from "../types/graph";

describe("severityFromCvss", () => {
  it("bands on CVSS v3 cutoffs", () => {
    expect(severityFromCvss(10)).toBe("critical");
    expect(severityFromCvss(9.0)).toBe("critical");
    expect(severityFromCvss(8.9)).toBe("high");
    expect(severityFromCvss(7.0)).toBe("high");
    expect(severityFromCvss(6.9)).toBe("medium");
    expect(severityFromCvss(4.0)).toBe("medium");
    expect(severityFromCvss(3.9)).toBe("low");
    expect(severityFromCvss(0.1)).toBe("low");
  });

  it("treats 0 and missing scores as info, not low", () => {
    expect(severityFromCvss(0)).toBe("info");
    expect(severityFromCvss(null)).toBe("info");
    expect(severityFromCvss(undefined)).toBe("info");
  });

  it("returns a severity that always has a label and a color", () => {
    for (const score of [null, 0, 1, 4, 7, 9, 10]) {
      const sev = severityFromCvss(score);
      expect(SEVERITY_LABELS[sev]).toBeTruthy();
      expect(severityColor(sev)).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });
});

describe("severity scale", () => {
  it("is ordered most severe first", () => {
    expect(SEVERITY_ORDER).toEqual(["critical", "high", "medium", "low", "info"]);
  });

  it("gives every band a distinct color", () => {
    const used = SEVERITY_ORDER.map(severityColor);
    expect(new Set(used).size).toBe(SEVERITY_ORDER.length);
  });

  it("avoids a red/green pairing at the extremes (most common CVD)", () => {
    // Low is deliberately blue, not green — see index.css token comments.
    const low = severityColor("low").toLowerCase();
    expect(low).toBe("#4c8df0");
  });
});

describe("node type tokens", () => {
  const types = Object.keys(NODE_TYPE_LABELS) as NodeType[];

  it("covers all 8 node types with a label, color, shape and icon", () => {
    expect(types).toHaveLength(8);
    for (const t of types) {
      expect(NODE_TYPE_LABELS[t]).toBeTruthy();
      expect(nodeTypeColor[t]).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(nodeTypeShape[t]).toBeTruthy();
      expect(nodeIconDataUri(t)).toMatch(/^data:image\/svg\+xml/);
    }
  });

  it("gives each type a visually distinct color", () => {
    const used = types.map((t) => nodeTypeColor[t]);
    expect(new Set(used).size).toBe(types.length);
  });

  it("never uses diamond for a type — that shape means crown jewel", () => {
    expect(Object.values(nodeTypeShape)).not.toContain("diamond");
  });

  it("bakes the type color into the icon, since Cytoscape can't recolor a data URI", () => {
    const uri = decodeURIComponent(nodeIconDataUri("finding"));
    expect(uri).toContain(nodeTypeColor.finding);
    expect(uri).not.toContain("__COLOR__"); // placeholder must be substituted
    expect(uri).not.toContain("currentColor"); // wouldn't resolve in a standalone image
  });

  it("caches icons rather than re-encoding per render", () => {
    expect(nodeIconDataUri("asset")).toBe(nodeIconDataUri("asset"));
  });
});

describe("edge type tokens", () => {
  const types = Object.keys(EDGE_TYPE_LABELS) as EdgeType[];

  it("covers all 7 edge types", () => {
    expect(types).toHaveLength(7);
    for (const t of types) {
      expect(edgeTypeStyle[t]).toBeDefined();
      expect(edgeTypeStyle[t].color).toBeTruthy();
      expect(edgeTypeStyle[t].arrowShape).toBeTruthy();
    }
  });

  it("makes YIELDS the visually loudest — it's the only real exploitation step", () => {
    const yields = edgeTypeStyle.YIELDS;
    const others = types.filter((t) => t !== "YIELDS").map((t) => edgeTypeStyle[t].width);
    expect(yields.width).toBeGreaterThan(Math.max(...others));
    expect(yields.color).toBe(colors.severity.critical);
  });

  it("uses only arrow shapes Cytoscape actually supports", () => {
    const valid = new Set([
      "triangle", "triangle-tee", "triangle-cross", "triangle-backcurve",
      "vee", "tee", "square", "circle", "diamond", "chevron", "none",
    ]);
    for (const t of types) {
      expect(valid.has(edgeTypeStyle[t].arrowShape)).toBe(true);
    }
  });
});

describe("surface palette", () => {
  it("gets progressively lighter from surface 0 to 3", () => {
    const lum = (hex: string) => parseInt(hex.slice(1), 16);
    expect(lum(colors.surface[0])).toBeLessThan(lum(colors.surface[1]));
    expect(lum(colors.surface[1])).toBeLessThan(lum(colors.surface[2]));
    expect(lum(colors.surface[2])).toBeLessThan(lum(colors.surface[3]));
  });
});
