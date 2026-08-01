import { useCallback, useEffect, useState } from "react";
import { fetchGraph, getActiveEngagement } from "../api/client";
import CommandPalette, { type Command } from "../components/CommandPalette";
import ErrorBanner from "../components/ErrorBanner";
import ShortcutsHelp from "../components/ShortcutsHelp";
import SnapshotPanel from "../components/SnapshotPanel";
import Sidebar, { type Section } from "../components/Sidebar";
import DashboardPage from "./DashboardPage";
import FindingsPage from "./FindingsPage";
import GraphSection from "./GraphSection";
import ImportPage from "./ImportPage";
import PathAnalysisPage from "./PathAnalysisPage";
import type { Engagement, GraphFilters, GraphResponse, PathResult } from "../types/graph";

export default function AppShell() {
  const [section, setSection] = useState<Section>("graph");
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [engagementError, setEngagementError] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [] });
  const [filters, setFilters] = useState<GraphFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<PathResult | null>(null);
  const [showCreateNode, setShowCreateNode] = useState(false);
  const [showCreateEdge, setShowCreateEdge] = useState(false);
  const [showSnapshots, setShowSnapshots] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const loadEngagement = useCallback(() => {
    getActiveEngagement()
      .then((e) => {
        setEngagement(e);
        setEngagementError(null);
      })
      .catch((e) => setEngagementError(String(e)));
  }, []);

  const loadGraph = useCallback(() => {
    setLoading(true);
    fetchGraph(filters)
      .then((g) => {
        setGraph(g);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(loadEngagement, [loadEngagement]);
  useEffect(loadGraph, [loadGraph]);

  function handleEngagementChanged() {
    loadEngagement();
    setSelectedNodeId(null);
    setHighlightedPath(null);
    loadGraph();
  }

  function goToNodeInGraph(nodeId: string) {
    setSection("graph");
    setSelectedNodeId(nodeId);
  }

  // Keyboard shortcuts, active anywhere in the app. Ignored while typing in
  // an editable field, except Escape (always works) and Ctrl/Cmd+K (a
  // deliberate override so the palette is reachable even mid-form).
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      const isTyping =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT";

      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setShowPalette((v) => !v);
        return;
      }

      if (e.key === "Escape") {
        if (showPalette) setShowPalette(false);
        else if (showShortcuts) setShowShortcuts(false);
        else if (showSnapshots) setShowSnapshots(false);
        else if (showCreateEdge) setShowCreateEdge(false);
        else if (showCreateNode) setShowCreateNode(false);
        else if (selectedNodeId) setSelectedNodeId(null);
        return;
      }

      if (isTyping) return;

      if (e.key === "/") {
        e.preventDefault();
        document.querySelector<HTMLInputElement>("[data-shortcut-search]")?.focus();
      } else if (e.key === "f") {
        e.preventDefault();
        document.querySelector<HTMLSelectElement>("[data-shortcut-filter]")?.focus();
      } else if (e.key === "?") {
        e.preventDefault();
        setShowShortcuts((v) => !v);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showPalette, showShortcuts, showSnapshots, showCreateEdge, showCreateNode, selectedNodeId]);

  const commands: Command[] = [
    { id: "go-graph", label: "Go to Graph", action: () => setSection("graph") },
    { id: "go-findings", label: "Go to Findings", action: () => setSection("findings") },
    { id: "go-pathfind", label: "Go to Path Analysis", keywords: "attack chain", action: () => setSection("pathfind") },
    { id: "go-dashboard", label: "Go to Dashboard", keywords: "stats overview", action: () => setSection("dashboard") },
    { id: "go-import", label: "Go to Import", keywords: "nmap nuclei amass burp upload", action: () => setSection("import") },
    { id: "new-node", label: "Create node", hint: "+ node", action: () => setShowCreateNode(true) },
    { id: "new-edge", label: "Create edge", hint: "+ edge", action: () => setShowCreateEdge(true) },
    { id: "snapshots", label: "Open snapshots", keywords: "history compare diff", action: () => setShowSnapshots(true) },
    {
      id: "clear-highlight",
      label: "Clear highlighted path",
      keywords: "reset deselect",
      action: () => setHighlightedPath(null),
    },
    { id: "shortcuts", label: "Show keyboard shortcuts", hint: "?", action: () => setShowShortcuts(true) },
  ];

  return (
    <div className="flex h-screen bg-surface-0 text-text-primary">
      <Sidebar
        active={section}
        onSelect={setSection}
        engagement={engagement}
        onEngagementChanged={handleEngagementChanged}
        nodeCount={graph.nodes.length}
        edgeCount={graph.edges.length}
        onShowShortcuts={() => setShowShortcuts(true)}
      />

      <div className="relative flex-1 overflow-hidden">
        {!engagement && engagementError && (section === "dashboard" || section === "import") && (
          <div className="flex h-full items-center justify-center p-8">
            <div className="max-w-sm space-y-3">
              <ErrorBanner message={`Couldn't load engagement: ${engagementError}`} />
              <button
                onClick={loadEngagement}
                className="w-full rounded border border-border py-1.5 font-mono text-xs text-text-secondary hover:border-accent/60 hover:text-accent"
              >
                retry
              </button>
            </div>
          </div>
        )}

        {section === "graph" && (
          <GraphSection
            graph={graph}
            loading={loading}
            error={error}
            filters={filters}
            onFiltersChange={setFilters}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            highlightedPath={highlightedPath}
            onNodeChanged={loadGraph}
            showCreateNode={showCreateNode}
            onOpenCreateNode={() => setShowCreateNode(true)}
            onCloseCreateNode={() => setShowCreateNode(false)}
            showCreateEdge={showCreateEdge}
            onOpenCreateEdge={() => setShowCreateEdge(true)}
            onCloseCreateEdge={() => setShowCreateEdge(false)}
            onGoToImport={() => setSection("import")}
          />
        )}

        {section === "findings" && <FindingsPage onViewInGraph={goToNodeInGraph} />}

        {section === "pathfind" && (
          <PathAnalysisPage graph={graph} highlightedPath={highlightedPath} onSelectPath={setHighlightedPath} />
        )}

        {section === "dashboard" && engagement && (
          <DashboardPage engagementId={engagement.id} onOpenSnapshots={() => setShowSnapshots(true)} />
        )}

        {section === "import" && engagement && (
          <ImportPage engagementId={engagement.id} onImported={loadGraph} />
        )}
      </div>

      {showSnapshots && engagement && (
        <SnapshotPanel engagementId={engagement.id} onClose={() => setShowSnapshots(false)} />
      )}

      {showPalette && <CommandPalette commands={commands} onClose={() => setShowPalette(false)} />}

      {showShortcuts && <ShortcutsHelp onClose={() => setShowShortcuts(false)} />}
    </div>
  );
}
