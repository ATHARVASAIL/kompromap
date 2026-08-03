/**
 * Graph layout tests.
 *
 * These exist because of a real bug found by running the layouts at scale
 * rather than eyeballing them: `breadthfirst` on a densely-cyclic graph
 * (which pentest data is — assets host services host endpoints, with
 * findings cross-linking back) produced coordinate spreads around 1e+50
 * without an explicit boundingBox. That renders as a completely empty
 * canvas with every node pushed past the horizon, and nothing throws.
 */
import cytoscape from "cytoscape";
import { describe, expect, it } from "vitest";
import { DEFAULT_LAYOUT, LAYOUTS, getLayout } from "../graph/layouts";

/** A graph shaped like real engagement data: cyclic, uneven degree. */
function buildGraph(n = 200, e = 320) {
  const nodes = Array.from({ length: n }, (_, i) => ({
    data: { id: `n${i}`, is_entry_point: i % 40 === 0 },
  }));
  const edges: { data: Record<string, string> }[] = [];
  for (let i = 0; i < e; i++) {
    const s = i % n;
    const t = (i * 7 + 3) % n;
    if (s !== t) edges.push({ data: { id: `e${i}`, source: `n${s}`, target: `n${t}` } });
  }
  return cytoscape({ headless: true, elements: [...nodes, ...edges] });
}

function runLayout(cy: cytoscape.Core, id: string) {
  const def = getLayout(id as never);
  const roots = cy
    .nodes()
    .filter((n) => n.data("is_entry_point"))
    .map((n) => n.id());
  cy.layout({ ...def.build(roots), animate: false } as never).run();
  return cy.nodes().map((n) => n.position());
}

describe("layout catalogue", () => {
  it("offers the layouts the switcher expects", () => {
    expect(LAYOUTS.map((l) => l.id)).toEqual([
      "cose",
      "breadthfirst",
      "concentric",
      "circle",
      "grid",
    ]);
  });

  it("defaults to force-directed — it handles a whole messy engagement best", () => {
    expect(DEFAULT_LAYOUT).toBe("cose");
  });

  it("gives every layout a label and an explanatory hint", () => {
    for (const l of LAYOUTS) {
      expect(l.label).toBeTruthy();
      expect(l.hint.length).toBeGreaterThan(20);
    }
  });

  it("falls back to the first layout for an unknown id", () => {
    expect(getLayout("nope" as never).id).toBe("cose");
  });
});

describe("layout output is renderable", () => {
  for (const def of LAYOUTS) {
    it(`${def.id} produces finite coordinates`, () => {
      const positions = runLayout(buildGraph(), def.id);
      expect(positions.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
    });

    it(`${def.id} keeps the spread within a viewable range`, () => {
      const positions = runLayout(buildGraph(), def.id);
      const xs = positions.map((p) => p.x);
      const ys = positions.map((p) => p.y);
      const spread = Math.max(
        Math.max(...xs) - Math.min(...xs),
        Math.max(...ys) - Math.min(...ys),
      );
      // The bug produced ~1e+50 here. Anything past six figures means a
      // canvas the user can't meaningfully navigate.
      expect(spread).toBeLessThan(100_000);
    });

    it(`${def.id} does not stack every node on one point`, () => {
      const positions = runLayout(buildGraph(60, 90), def.id);
      const distinct = new Set(positions.map((p) => `${Math.round(p.x)},${Math.round(p.y)}`));
      expect(distinct.size).toBeGreaterThan(positions.length * 0.5);
    });
  }
});

describe("hierarchy layout", () => {
  it("stacks a linear chain into distinct levels", () => {
    const cy = cytoscape({
      headless: true,
      elements: [
        { data: { id: "a", is_entry_point: true } },
        { data: { id: "b" } },
        { data: { id: "c" } },
        { data: { id: "d" } },
        { data: { id: "e1", source: "a", target: "b" } },
        { data: { id: "e2", source: "b", target: "c" } },
        { data: { id: "e3", source: "c", target: "d" } },
      ],
    });
    runLayout(cy, "breadthfirst");
    const ys = ["a", "b", "c", "d"].map((id) => cy.getElementById(id).position().y);
    // Each hop should sit strictly below the previous — that top-down
    // cascade is the entire reason this layout is offered.
    expect(ys[0]).toBeLessThan(ys[1]);
    expect(ys[1]).toBeLessThan(ys[2]);
    expect(ys[2]).toBeLessThan(ys[3]);
  });

  it("works when nothing is tagged as an entry point", () => {
    const cy = cytoscape({
      headless: true,
      elements: [
        { data: { id: "a" } },
        { data: { id: "b" } },
        { data: { id: "e1", source: "a", target: "b" } },
      ],
    });
    expect(() => runLayout(cy, "breadthfirst")).not.toThrow();
  });
});

describe("manual positioning", () => {
  it("a pinned position survives a layout re-run", () => {
    const cy = buildGraph(40, 60);
    runLayout(cy, "cose");

    const pinned = new Map([["n5", { x: 9999, y: 8888 }]]);
    cy.getElementById("n5").position(pinned.get("n5")!);

    runLayout(cy, "cose");
    pinned.forEach((pos, id) => cy.getElementById(id).position(pos));

    expect(cy.getElementById("n5").position()).toEqual({ x: 9999, y: 8888 });
  });
});

describe("fit zoom is usable without manual zooming", () => {
  /**
   * Regression guard for a real, user-reported bug: unbounded `cose` on a
   * sparse 118-node engagement grew to 2743x3421, which forced `fit` down
   * to ~19% zoom. At that scale node icons and labels are unreadable
   * specks and every session starts with the user zooming and panning.
   *
   * The viewport figures below approximate the app's canvas area with the
   * sidebar and toolbar accounted for.
   */
  const VIEWPORT_W = 1330;
  const VIEWPORT_H = 680;

  function fitZoom(positions: { x: number; y: number }[]) {
    const xs = positions.map((p) => p.x);
    const ys = positions.map((p) => p.y);
    const w = Math.max(...xs) - Math.min(...xs);
    const h = Math.max(...ys) - Math.min(...ys);
    return Math.min(VIEWPORT_W / (w + 120), VIEWPORT_H / (h + 120));
  }

  /** Sparse graph with many small components — what ingesting a subdomain
   *  list actually produces, and the shape that broke the old layout. */
  function sparseGraph(n = 118, e = 92) {
    const nodes = Array.from({ length: n }, (_, i) => ({ data: { id: `n${i}` } }));
    const edges: { data: Record<string, string> }[] = [];
    for (let i = 0; i < e; i++) {
      const s = i % n;
      const t = (i * 3 + 1) % n;
      if (s !== t) edges.push({ data: { id: `e${i}`, source: `n${s}`, target: `n${t}` } });
    }
    return cytoscape({ headless: true, elements: [...nodes, ...edges] });
  }

  for (const def of LAYOUTS) {
    it(`${def.id} fits at a legible zoom level`, () => {
      const cy = sparseGraph();
      cy.layout({ ...def.build([]), animate: false } as never).run();
      // 0.35 matches GraphCanvas's minZoom — below it, nodes are specks.
      expect(fitZoom(cy.nodes().map((n) => n.position()))).toBeGreaterThan(0.35);
    });
  }

  it("force layout in particular stays wide rather than tall", () => {
    /** The original bug was vertical growth fighting a landscape viewport. */
    const cy = sparseGraph();
    const def = getLayout("cose");
    cy.layout({ ...def.build([]), animate: false } as never).run();
    const ps = cy.nodes().map((n) => n.position());
    const w = Math.max(...ps.map((p) => p.x)) - Math.min(...ps.map((p) => p.x));
    const h = Math.max(...ps.map((p) => p.y)) - Math.min(...ps.map((p) => p.y));
    expect(w).toBeGreaterThan(h);
  });
});
