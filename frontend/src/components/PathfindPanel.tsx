import { useState } from "react";
import { exportChain, findBestPaths, findPathsFromEntryPoint, generateNarrative } from "../api/client";
import EmptyState from "./EmptyState";
import ErrorBanner from "./ErrorBanner";
import Spinner from "./Spinner";
import { useToast } from "./ToastProvider";
import { EDGE_TYPE_LABELS, NODE_TYPE_COLOR, type GraphNode, type PathResult } from "../types/graph";

interface PathfindPanelProps {
  entryPoints: GraphNode[];
  crownJewelCount: number;
  onSelectPath: (path: PathResult | null) => void;
  onClose: () => void;
}

function downloadFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function PathfindPanel({
  entryPoints,
  crownJewelCount,
  onSelectPath,
  onClose,
}: PathfindPanelProps) {
  const { toast } = useToast();
  const [scope, setScope] = useState<"all" | string>("all");
  const [paths, setPaths] = useState<PathResult[] | null>(null);
  const [unreachableCount, setUnreachableCount] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [narrative, setNarrative] = useState<string | null>(null);
  const [narrativeSource, setNarrativeSource] = useState<"llm" | "template" | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function run() {
    setLoading(true);
    setError(null);
    setPaths(null);
    setSelectedIndex(null);
    setNarrative(null);
    setNarrativeSource(null);
    onSelectPath(null);
    try {
      if (scope === "all") {
        const res = await findBestPaths();
        setPaths(res.paths);
        setUnreachableCount(res.unreachable_entry_points.length);
        toast(`Path computed — ${res.paths.length} result${res.paths.length === 1 ? "" : "s"}`, "success");
      } else {
        const res = await findPathsFromEntryPoint(scope);
        setPaths(res.paths);
        setUnreachableCount(res.unreachable_crown_jewels.length);
        toast(`Path computed — ${res.paths.length} result${res.paths.length === 1 ? "" : "s"}`, "success");
      }
    } catch (e) {
      setError(String(e));
      toast("Path-finding failed", "error");
    } finally {
      setLoading(false);
    }
  }

  function select(index: number) {
    setSelectedIndex(index);
    setNarrative(null);
    setNarrativeSource(null);
    onSelectPath(paths![index]);
  }

  async function handleGenerateNarrative() {
    if (selectedIndex === null || !paths) return;
    setNarrativeLoading(true);
    setError(null);
    try {
      const nodeIds = paths[selectedIndex].nodes.map((n) => n.id);
      const res = await generateNarrative(nodeIds);
      setNarrative(res.narrative);
      setNarrativeSource(res.narrative_source);
      toast("Narrative generated", "success");
    } catch (e) {
      setError(String(e));
      toast("Couldn't generate narrative", "error");
    } finally {
      setNarrativeLoading(false);
    }
  }

  async function handleExport(format: "markdown" | "json") {
    if (selectedIndex === null || !paths) return;
    setExporting(true);
    setError(null);
    try {
      const nodeIds = paths[selectedIndex].nodes.map((n) => n.id);
      const res = await exportChain(nodeIds, format, narrative ?? undefined);
      const path = paths[selectedIndex];
      const stem = `kompromap-${path.entry_point.label}-to-${path.crown_jewel.label}`.replace(/[^\w-]+/g, "_");
      if (format === "markdown") {
        downloadFile(`${stem}.md`, res.content ?? "", "text/markdown");
      } else {
        downloadFile(`${stem}.json`, JSON.stringify(res.data, null, 2), "application/json");
      }
      toast(`Exported as .${format === "markdown" ? "md" : "json"}`, "success");
    } catch (e) {
      setError(String(e));
      toast("Export failed", "error");
    } finally {
      setExporting(false);
    }
  }

  return (
    <aside className="flex h-full w-96 animate-slide-in-right flex-col border-l border-border bg-surface-1/70 font-mono text-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-text-tertiary">path-finder</span>
        <button onClick={onClose} className="text-text-tertiary hover:text-text-primary" aria-label="Close">
          ✕
        </button>
      </div>

      <div className="space-y-3 border-b border-border px-4 py-4">
        {(entryPoints.length === 0 || crownJewelCount === 0) && (
          <p className="text-xs text-severity-medium">
            Tag at least one node "entry point" and one "crown jewel" in the detail panel first.
          </p>
        )}

        <div>
          <label className="mb-1 block text-xs text-text-tertiary">scope</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="all">easiest path per entry point → any crown jewel</option>
            {entryPoints.map((ep) => (
              <option key={ep.id} value={ep.id}>
                from: {ep.label}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={run}
          disabled={loading || entryPoints.length === 0 || crownJewelCount === 0}
          className="flex w-full items-center justify-center gap-2 rounded border border-accent bg-accent/10 py-1.5 text-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading && <Spinner />}
          {loading ? "computing…" : "find paths"}
        </button>

        {error && <ErrorBanner message={error} />}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {paths === null ? (
          <EmptyState message="No results yet." />
        ) : paths.length === 0 ? (
          <EmptyState message="No reachable chain found with the current graph." />
        ) : (
          <div className="space-y-2">
            {unreachableCount > 0 && (
              <p className="text-xs text-severity-medium">
                {unreachableCount} {scope === "all" ? "entry point(s)" : "crown jewel(s)"} unreachable.
              </p>
            )}
            {paths.map((p, i) => (
              <button
                key={i}
                onClick={() => select(i)}
                className={`w-full rounded border px-3 py-2 text-left text-xs transition-colors ${
                  selectedIndex === i
                    ? "border-severity-medium bg-severity-medium/10"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <div className="mb-1 flex items-center justify-between text-text-secondary">
                  <span>{p.entry_point.label}</span>
                  <span className="text-text-tertiary">→</span>
                  <span>{p.crown_jewel.label}</span>
                </div>
                <div className="text-text-tertiary">
                  cost {p.total_cost.toFixed(2)} · {p.nodes.length} nodes
                </div>
                {selectedIndex === i && (
                  <div className="mt-2 space-y-1 border-t border-border pt-2">
                    {p.nodes.map((n, ni) => (
                      <div key={n.id} className="flex items-center gap-1.5 text-text-tertiary">
                        <span
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: NODE_TYPE_COLOR[n.node_type] }}
                        />
                        <span className="truncate">{n.label}</span>
                        {ni < p.edges.length && (
                          <span className="ml-auto shrink-0 text-text-tertiary">
                            {EDGE_TYPE_LABELS[p.edges[ni].edge_type]} →
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}

        {selectedIndex !== null && paths && (
          <div className="mt-4 space-y-2 border-t border-border pt-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-tertiary">report</span>
              {narrativeSource && (
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                    narrativeSource === "llm"
                      ? "bg-accent/10 text-accent"
                      : "bg-surface-2/50 text-text-tertiary"
                  }`}
                >
                  {narrativeSource === "llm" ? "AI-generated" : "template"}
                </span>
              )}
            </div>

            {narrative === null ? (
              <button
                onClick={handleGenerateNarrative}
                disabled={narrativeLoading}
                className="flex w-full items-center justify-center gap-2 rounded border border-border py-1.5 text-xs text-text-secondary hover:border-accent hover:text-accent disabled:opacity-50"
              >
                {narrativeLoading && <Spinner />}
                {narrativeLoading ? "generating…" : "generate narrative"}
              </button>
            ) : (
              <textarea
                value={narrative}
                onChange={(e) => setNarrative(e.target.value)}
                rows={5}
                className="w-full resize-none rounded border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
              />
            )}

            <div className="flex gap-2">
              <button
                onClick={() => handleExport("markdown")}
                disabled={exporting}
                className="flex-1 rounded border border-border py-1.5 text-xs text-text-secondary hover:border-border-strong disabled:opacity-50"
              >
                export .md
              </button>
              <button
                onClick={() => handleExport("json")}
                disabled={exporting}
                className="flex-1 rounded border border-border py-1.5 text-xs text-text-secondary hover:border-border-strong disabled:opacity-50"
              >
                export .json
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
