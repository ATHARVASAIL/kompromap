/**
 * One-off verification script (not part of the shipped app) — confirms
 * the graph stylesheet from GraphCanvas.tsx actually constructs and lays
 * out correctly at real pentest data volumes, per the UI modernization
 * brief's explicit "test with a reasonably dense sample graph, not just 5
 * nodes" requirement. Run with: npx tsx scripts/graphStressTest.ts
 */
import cytoscape from "cytoscape";
import { performance } from "node:perf_hooks";
import { EDGE_TYPE_STYLE } from "../src/styles/edgeStyles";
import { NODE_TYPE_ICON, NODE_TYPE_SHAPE } from "../src/styles/nodeIcons";
import { colors, nodeTypeColor } from "../src/styles/tokens";

const NODE_TYPES = Object.keys(NODE_TYPE_SHAPE) as (keyof typeof NODE_TYPE_SHAPE)[];
const EDGE_TYPES = Object.keys(EDGE_TYPE_STYLE) as (keyof typeof EDGE_TYPE_STYLE)[];

const NODE_COUNT = 400;
const EDGE_COUNT = 550;

function buildStylesheet() {
  const nodeTypeStyles = NODE_TYPES.map((type) => ({
    selector: `node[node_type = "${type}"]`,
    style: {
      shape: NODE_TYPE_SHAPE[type],
      "background-color": nodeTypeColor[type],
      "background-image": NODE_TYPE_ICON[type],
    },
  }));

  const edgeTypeStyles = EDGE_TYPES.map((type) => {
    const s = EDGE_TYPE_STYLE[type];
    return {
      selector: `edge[edge_type = "${type}"]`,
      style: {
        "line-color": s.color,
        "target-arrow-color": s.color,
        "target-arrow-shape": s.arrowShape,
        "line-style": s.lineStyle,
        width: s.width,
      },
    };
  });

  return [
    { selector: "node", style: { "background-color": colors.surface[2], width: 30, height: 30 } },
    ...nodeTypeStyles,
    { selector: "node[?is_crown_jewel]", style: { "underlay-color": colors.severity.critical } },
    { selector: "edge", style: { "curve-style": "bezier" } },
    ...edgeTypeStyles,
  ];
}

function buildSyntheticGraph(nodeCount: number, edgeCount: number) {
  const elements: cytoscape.ElementDefinition[] = [];
  for (let i = 0; i < nodeCount; i++) {
    const type = NODE_TYPES[i % NODE_TYPES.length];
    elements.push({
      data: {
        id: `n${i}`,
        label: `node-${i}`,
        node_type: type,
        is_entry_point: i % 37 === 0,
        is_crown_jewel: i % 53 === 0,
      },
    });
  }
  for (let i = 0; i < edgeCount; i++) {
    const source = `n${i % nodeCount}`;
    const target = `n${(i * 7 + 3) % nodeCount}`;
    if (source === target) continue;
    elements.push({
      data: {
        id: `e${i}`,
        source,
        target,
        edge_type: EDGE_TYPES[i % EDGE_TYPES.length],
      },
    });
  }
  return elements;
}

console.log(`Building headless cytoscape instance: ${NODE_COUNT} nodes, ~${EDGE_COUNT} edges...`);

const t0 = performance.now();
const cy = cytoscape({
  headless: true,
  styleEnabled: true,
  elements: buildSyntheticGraph(NODE_COUNT, EDGE_COUNT),
  style: buildStylesheet() as cytoscape.StylesheetJson,
});
const tConstruct = performance.now();
console.log(`Instance constructed in ${(tConstruct - t0).toFixed(1)}ms`);
console.log(`  nodes: ${cy.nodes().length}, edges: ${cy.edges().length}`);

// Spot-check that type-based selectors actually resolve to the right style,
// not just that the stylesheet didn't throw.
const sampleNode = cy.getElementById("n0");
const resolvedShape = sampleNode.style("shape");
const expectedShape = NODE_TYPE_SHAPE[NODE_TYPES[0]];
console.log(`  n0 (type=${NODE_TYPES[0]}) resolved shape: ${resolvedShape} (expected ${expectedShape})`);
if (resolvedShape !== expectedShape) {
  console.error("MISMATCH -- selector did not resolve to the expected per-type style");
  process.exit(1);
}

const crownJewelNodes = cy.nodes("[?is_crown_jewel]");
console.log(`  crown-jewel nodes matched by selector: ${crownJewelNodes.length}`);

const t1 = performance.now();
const layout = cy.layout({ name: "cose", animate: false, randomize: true });
layout.run();
const t2 = performance.now();
console.log(`cose layout completed in ${(t2 - t1).toFixed(1)}ms for ${cy.elements().length} elements`);

// Confirm every node actually got a finite position (a common failure mode
// for cose on disconnected or malformed graphs).
const badPositions = cy.nodes().filter((n) => {
  const p = n.position();
  return !Number.isFinite(p.x) || !Number.isFinite(p.y);
});
if (badPositions.length > 0) {
  console.error(`${badPositions.length} nodes ended up with non-finite positions after layout`);
  process.exit(1);
}
console.log(`All ${cy.nodes().length} nodes have finite positions after layout`);

console.log("\nAll checks passed.");
