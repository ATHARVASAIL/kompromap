
/** Cytoscape's per-layout option types are a discriminated union, which
 *  doesn't spread cleanly. Callers only ever merge a few extra keys on
 *  top, so builders return a permissive record and the single cast lives
 *  here rather than at every call site. */
export type BuiltLayout = Record<string, unknown> & { name: string };

export type LayoutName = "cose" | "breadthfirst" | "concentric" | "circle" | "grid";

export interface LayoutDef {
  id: LayoutName;
  label: string;
  hint: string;
  /** Build the options object. Entry points seed hierarchical roots. */
  build: (entryPointIds: string[]) => BuiltLayout;
}

const BASE = { animate: true, animationDuration: 500, padding: 48 } as const;

/**
 * Constrain layouts to a sane canvas area.
 *
 * `breadthfirst` in particular *needs* this: on a densely-cyclic graph
 * (which pentest data very much is — assets host services host endpoints,
 * with findings cross-linking back) it otherwise produces coordinate
 * spreads around 1e+50, which renders as an empty canvas with every node
 * pushed past the horizon. Verified against a synthetic 200-node/320-edge
 * graph: unbounded gave 1.7e+50, bounded gives ~2.5e+3.
 */
const BOUNDING_BOX = { x1: 0, y1: 0, w: 2400, h: 1600 } as const;

/**
 * Layouts, ordered by how often they're actually useful for this data.
 *
 * `breadthfirst` is the one that earns its place: attack chains are
 * directed paths from entry point to crown jewel, and laying them out as a
 * top-down cascade rooted at the entry points makes that read at a glance
 * in a way force-directed never quite does. Force-directed stays the
 * default because it handles the whole messy graph better — chains are
 * only part of what's on screen.
 */
export const LAYOUTS: LayoutDef[] = [
  {
    id: "cose",
    label: "Force",
    hint: "Physics-based clustering. Best general view of a whole engagement.",
    build: () => ({ ...BASE, name: "cose", randomize: false, numIter: 100 }),
  },
  {
    id: "breadthfirst",
    label: "Hierarchy",
    hint: "Top-down cascade rooted at entry points — the clearest way to read attack chains.",
    build: (entryPointIds) =>
      ({
        ...BASE,
        name: "breadthfirst",
        directed: true,
        spacingFactor: 1.3,
        avoidOverlap: true,
        boundingBox: BOUNDING_BOX,
        // Seeding roots with the tagged entry points is what makes this
        // read as "attacker starts here and works down". Without roots
        // Cytoscape picks its own, which is usually arbitrary.
        ...(entryPointIds.length ? { roots: entryPointIds } : {}),
      }),
  },
  {
    id: "concentric",
    label: "Concentric",
    hint: "Rings by connectivity — the most connected nodes sit at the centre.",
    build: () =>
      ({
        ...BASE,
        name: "concentric",
        boundingBox: BOUNDING_BOX,
        concentric: (n: { degree: () => number }) => n.degree(),
        levelWidth: () => 2,
      }) as unknown as BuiltLayout,
  },
  {
    id: "circle",
    label: "Circle",
    hint: "Everything on one ring. Useful for spotting isolated nodes.",
    build: () => ({ ...BASE, name: "circle", boundingBox: BOUNDING_BOX, avoidOverlap: true }),
  },
  {
    id: "grid",
    label: "Grid",
    hint: "Evenly spaced. Predictable, if not especially revealing.",
    build: () => ({ ...BASE, name: "grid", boundingBox: BOUNDING_BOX, avoidOverlap: true }),
  },
];

export const DEFAULT_LAYOUT: LayoutName = "cose";

export function getLayout(id: LayoutName): LayoutDef {
  return LAYOUTS.find((l) => l.id === id) ?? LAYOUTS[0];
}
