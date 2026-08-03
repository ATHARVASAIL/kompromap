import { useMemo, useState } from "react";
import DetailPanel from "../components/DetailPanel";
import GraphCanvas from "../components/GraphCanvas";
import PathfindPanel from "../components/PathfindPanel";
import type { GraphResponse, PathResult } from "../types/graph";

interface PathAnalysisPageProps {
  graph: GraphResponse;
  highlightedPath: PathResult | null;
  onSelectPath: (path: PathResult | null) => void;
}

export default function PathAnalysisPage({ graph, highlightedPath, onSelectPath }: PathAnalysisPageProps) {
  // Clicking a node here previously did nothing at all. Inspecting a node
  // mid-analysis is exactly when you want its detail — "what actually is
  // this step?" — so it opens the same panel the Graph section uses.
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null);
  const entryPoints = useMemo(() => graph.nodes.filter((n) => n.is_entry_point), [graph.nodes]);
  const crownJewelCount = useMemo(() => graph.nodes.filter((n) => n.is_crown_jewel).length, [graph.nodes]);

  const highlight = highlightedPath
    ? {
        nodeIds: highlightedPath.nodes.map((n) => n.id),
        edgeIds: highlightedPath.edges.map((e) => e.id),
      }
    : null;

  return (
    <div className="flex h-full">
      <div className="relative flex-1">
        <GraphCanvas
          graph={graph}
          selectedNodeId={inspectedNodeId}
          onSelectNode={setInspectedNodeId}
          highlightedPath={highlight}
        />
      </div>

      {inspectedNodeId && (
        <DetailPanel
          nodeId={inspectedNodeId}
          onClose={() => setInspectedNodeId(null)}
          onChanged={() => {}}
          onDeleted={() => setInspectedNodeId(null)}
        />
      )}
      <PathfindPanel
        entryPoints={entryPoints}
        crownJewelCount={crownJewelCount}
        onSelectPath={onSelectPath}
      />
    </div>
  );
}
