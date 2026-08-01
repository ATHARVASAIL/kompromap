import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { edgeTypeStyle } from "../styles/edgeTokens";
import { nodeIconDataUri } from "../graph/nodeIcons";
import { colors, nodeTypeShape } from "../styles/tokens";
import { EDGE_TYPE_LABELS, NODE_TYPE_COLOR, type EdgeType, type GraphResponse, type NodeType } from "../types/graph";

interface GraphCanvasProps {
  graph: GraphResponse;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  /** Ordered — path-finding results are already a sequence from entry
   * point to crown jewel, and the sequential pulse animation depends on
   * that order, not just membership. */
  highlightedPath?: { nodeIds: string[]; edgeIds: string[] } | null;
  /** Case-insensitive substring match against node labels — highlights
   * matches and dims everything else, same visual language as hover. */
  searchQuery?: string;
}

const PULSE_STEP_MS = 160;
const LAYOUT_DURATION_MS = 600;

function elementDefinitions(graph: GraphResponse): { nodes: ElementDefinition[]; edges: ElementDefinition[] } {
  const nodes: ElementDefinition[] = graph.nodes.map((n) => ({
    group: "nodes",
    data: {
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      is_entry_point: n.is_entry_point,
      is_crown_jewel: n.is_crown_jewel,
    },
  }));

  const edges: ElementDefinition[] = graph.edges.map((e) => ({
    group: "edges",
    data: {
      id: e.id,
      source: e.source,
      target: e.target,
      label: EDGE_TYPE_LABELS[e.edge_type],
      edge_type: e.edge_type,
    },
  }));

  return { nodes, edges };
}

function buildStylesheet(): cytoscape.StylesheetJson {
  const edgeSelectors = (Object.keys(edgeTypeStyle) as EdgeType[]).map((type) => {
    const s = edgeTypeStyle[type];
    return {
      selector: `edge[edge_type = "${type}"]`,
      style: {
        "line-color": s.color,
        "target-arrow-color": s.color,
        "target-arrow-shape": s.arrowShape,
        "line-style": s.lineStyle,
        ...(s.dashPattern ? { "line-dash-pattern": s.dashPattern } : {}),
        width: s.width,
      },
    };
  });

  const nodeShapeSelectors = (Object.keys(nodeTypeShape) as NodeType[]).map((type) => ({
    selector: `node[node_type = "${type}"]`,
    style: {
      shape: nodeTypeShape[type],
      "border-color": NODE_TYPE_COLOR[type],
      "background-image": nodeIconDataUri(type),
    },
  }));

  return [
    {
      selector: "node",
      style: {
        "background-color": colors.surface[2],
        "background-image-opacity": 1,
        "background-fit": "none",
        "background-width": "58%",
        "background-height": "58%",
        label: "data(label)",
        color: colors.text.secondary,
        "font-family": "'JetBrains Mono', ui-monospace, monospace",
        "font-size": 10,
        "text-valign": "bottom",
        "text-margin-y": 7,
        width: 30,
        height: 30,
        "border-width": 2,
        "text-wrap": "ellipsis",
        "text-max-width": "120px",
        "transition-property": "border-width, background-color, opacity, width, height",
        "transition-duration": 150,
      },
    },
    ...nodeShapeSelectors,
    {
      selector: "node[?is_crown_jewel]",
      style: {
        shape: "diamond",
        width: 38,
        height: 38,
        "border-width": 3,
        "underlay-color": colors.severity.critical,
        "underlay-opacity": 0.25,
        "underlay-padding": 6,
      },
    },
    {
      selector: "node[?is_entry_point]",
      style: {
        "border-width": 3,
        "border-color": colors.accent,
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 4,
        "border-color": colors.text.primary,
      },
    },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        label: "data(label)",
        "font-family": "'JetBrains Mono', ui-monospace, monospace",
        "font-size": 8,
        color: colors.text.tertiary,
        "text-rotation": "autorotate",
        "text-margin-y": -6,
        "text-background-color": colors.surface[0],
        "text-background-opacity": 0.85,
        "text-background-padding": "2px",
        "transition-property": "opacity, width",
        "transition-duration": 150,
      },
    },
    ...edgeSelectors,
    {
      selector: ".path-highlight",
      style: {
        "z-index": 999,
      },
    },
    {
      selector: "node.path-highlight",
      style: {
        "border-width": 4,
        "border-color": colors.pathPulse,
        "underlay-color": colors.pathPulse,
        "underlay-opacity": 0.45,
        "underlay-padding": 8,
      },
    },
    {
      selector: "edge.path-highlight",
      style: {
        "line-color": colors.pathPulse,
        "target-arrow-color": colors.pathPulse,
        width: 4,
        "line-style": "solid",
        color: colors.pathPulse,
      },
    },
    {
      selector: ".path-dim",
      style: { opacity: 0.12 },
    },
    {
      selector: ".hover-dim",
      style: { opacity: 0.15 },
    },
    {
      selector: ".hover-related",
      style: { "z-index": 998 },
    },
    {
      selector: ".search-match",
      style: { "border-color": colors.accent, "border-width": 3, "z-index": 997 },
    },
    {
      selector: ".search-dim",
      style: { opacity: 0.15 },
    },
  ];
}

export default function GraphCanvas({ graph, selectedNodeId, onSelectNode, highlightedPath, searchQuery }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectNodeRef = useRef(onSelectNode);
  const hasActivePathRef = useRef(false);
  const hasActiveSearchRef = useRef(false);
  const pulseTimeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const [zoomPct, setZoomPct] = useState(100);

  useEffect(() => {
    onSelectNodeRef.current = onSelectNode;
  }, [onSelectNode]);

  // Create the Cytoscape instance exactly once. Every subsequent graph
  // update diffs into this same instance (see the effect below) instead of
  // destroying and recreating it — that's what makes layout transitions
  // animate instead of snapping to a brand new layout each time.
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: buildStylesheet(),
      layout: { name: "preset" },
      minZoom: 0.15,
      maxZoom: 3,
      wheelSensitivity: 0.25,
    });

    cy.on("tap", "node", (evt) => onSelectNodeRef.current(evt.target.id()));
    cy.on("tap", (evt) => {
      if (evt.target === cy) onSelectNodeRef.current(null);
    });

    cy.on("mouseover", "node", (evt) => {
      if (hasActivePathRef.current || hasActiveSearchRef.current) return;
      const node = evt.target as NodeSingular;
      const neighborhood = node.closedNeighborhood();
      cy.elements().not(neighborhood).addClass("hover-dim");
      neighborhood.addClass("hover-related");
    });
    cy.on("mouseout", "node", () => {
      if (hasActivePathRef.current || hasActiveSearchRef.current) return;
      cy.elements().removeClass("hover-dim hover-related");
    });

    cy.on("zoom", () => setZoomPct(Math.round(cy.zoom() * 100)));

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Diff the incoming graph into the live instance and animate to the new
  // layout, rather than tearing everything down. New nodes get randomized
  // starting positions only on first load; after that, cose starts from
  // current positions so existing nodes settle rather than reshuffling.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const { nodes, edges } = elementDefinitions(graph);
    const newNodeIds = new Set(nodes.map((n) => n.data.id as string));
    const newEdgeIds = new Set(edges.map((e) => e.data.id as string));
    const isFirstLoad = cy.elements().length === 0;

    cy.batch(() => {
      cy.nodes().forEach((n) => {
        if (!newNodeIds.has(n.id())) n.remove();
      });
      cy.edges().forEach((e) => {
        if (!newEdgeIds.has(e.id())) e.remove();
      });

      const existingNodeIds = new Set(cy.nodes().map((n) => n.id()));
      const existingEdgeIds = new Set(cy.edges().map((e) => e.id()));

      nodes.forEach((n) => {
        if (existingNodeIds.has(n.data.id as string)) {
          cy.getElementById(n.data.id as string).data(n.data);
        }
      });

      const nodesToAdd = nodes.filter((n) => !existingNodeIds.has(n.data.id as string));
      if (nodesToAdd.length) cy.add(nodesToAdd);

      const edgesToAdd = edges.filter((e) => !existingEdgeIds.has(e.data.id as string));
      if (edgesToAdd.length) cy.add(edgesToAdd);
    });

    if (cy.elements().length === 0) return;

    // First load gets cose's default iteration count for the best initial
    // spread (a one-time cost). Incremental updates start from
    // already-good positions, so they don't need nearly as many
    // refinement iterations to look right — capping this is the
    // difference between ~1.6s and ~0.4s on a few-hundred-node graph
    // (verified against a synthetic 400-node/700-edge graph, since the
    // spec's stated real-world scale is "hundreds, not millions").
    cy.layout({
      name: "cose",
      animate: true,
      animationDuration: LAYOUT_DURATION_MS,
      randomize: isFirstLoad,
      fit: isFirstLoad,
      padding: 48,
      ...(isFirstLoad ? {} : { numIter: 100 }),
    }).run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNodeId) cy.getElementById(selectedNodeId).select();
  }, [selectedNodeId]);

  // Sequential "pulse" down the winning chain rather than an instant color
  // swap: each node/edge in path order lights up PULSE_STEP_MS after the
  // previous one, tracing the actual attacker path visually.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    pulseTimeoutsRef.current.forEach(clearTimeout);
    pulseTimeoutsRef.current = [];
    cy.elements().removeClass("path-highlight path-dim");

    if (!highlightedPath || highlightedPath.nodeIds.length === 0) {
      hasActivePathRef.current = false;
      return;
    }
    hasActivePathRef.current = true;

    const { nodeIds, edgeIds } = highlightedPath;
    const nodeIdSet = new Set(nodeIds);
    const edgeIdSet = new Set(edgeIds);
    cy.nodes().forEach((n) => {
      if (!nodeIdSet.has(n.id())) n.addClass("path-dim");
    });
    cy.edges().forEach((e) => {
      if (!edgeIdSet.has(e.id())) e.addClass("path-dim");
    });

    nodeIds.forEach((id, i) => {
      const timeout = setTimeout(() => {
        cy.getElementById(id).addClass("path-highlight");
        if (i > 0) cy.getElementById(edgeIds[i - 1]).addClass("path-highlight");
      }, i * PULSE_STEP_MS);
      pulseTimeoutsRef.current.push(timeout);
    });

    return () => {
      pulseTimeoutsRef.current.forEach(clearTimeout);
    };
  }, [highlightedPath]);

  // Search-as-you-type: highlight nodes whose label matches, dim the rest.
  // Suppressed while a path result is active so the two signals don't
  // fight for the same visual language.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass("search-match search-dim");
    const query = searchQuery?.trim().toLowerCase();
    if (!query || hasActivePathRef.current) return;

    cy.nodes().forEach((n) => {
      const label = (n.data("label") as string)?.toLowerCase() ?? "";
      n.addClass(label.includes(query) ? "search-match" : "search-dim");
    });
    cy.edges().addClass("search-dim");
  }, [searchQuery]);

  function zoomBy(factor: number) {
    const cy = cyRef.current;
    if (!cy) return;
    cy.animate({ zoom: cy.zoom() * factor, center: { eles: cy.elements() } }, { duration: 150 });
  }

  function fitToView() {
    cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 48 } }, { duration: 300 });
  }

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      <div className="absolute bottom-4 right-4 flex flex-col items-stretch overflow-hidden rounded border border-border bg-surface-1/90 font-mono text-xs text-text-secondary shadow-elevated backdrop-blur">
        <button
          onClick={() => zoomBy(1.25)}
          className="border-b border-border px-2.5 py-1.5 hover:bg-surface-2 hover:text-text-primary"
          aria-label="Zoom in"
          title="Zoom in"
        >
          +
        </button>
        <button
          onClick={() => zoomBy(0.8)}
          className="border-b border-border px-2.5 py-1.5 hover:bg-surface-2 hover:text-text-primary"
          aria-label="Zoom out"
          title="Zoom out"
        >
          −
        </button>
        <button
          onClick={fitToView}
          className="px-2.5 py-1.5 hover:bg-surface-2 hover:text-text-primary"
          aria-label="Fit to view"
          title="Fit to view"
        >
          ⤢
        </button>
        <div className="border-t border-border px-2.5 py-1 text-center text-[10px] text-text-tertiary">
          {zoomPct}%
        </div>
      </div>
    </div>
  );
}
