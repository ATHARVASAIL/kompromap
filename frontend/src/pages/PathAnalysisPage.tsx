import { useMemo } from "react";
import GraphCanvas from "../components/GraphCanvas";
import PathfindPanel from "../components/PathfindPanel";
import type { GraphResponse, PathResult } from "../types/graph";

interface PathAnalysisPageProps {
  graph: GraphResponse;
  highlightedPath: PathResult | null;
  onSelectPath: (path: PathResult | null) => void;
}

export default function PathAnalysisPage({ graph, highlightedPath, onSelectPath }: PathAnalysisPageProps) {
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
        <GraphCanvas graph={graph} selectedNodeId={null} onSelectNode={() => {}} highlightedPath={highlight} />
      </div>
      <PathfindPanel
        entryPoints={entryPoints}
        crownJewelCount={crownJewelCount}
        onSelectPath={onSelectPath}
        onClose={() => onSelectPath(null)}
      />
    </div>
  );
}
