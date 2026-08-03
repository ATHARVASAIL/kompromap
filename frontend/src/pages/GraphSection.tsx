import { useCallback, useState } from "react";
import CreateEdgeModal from "../components/CreateEdgeModal";
import CreateNodeModal from "../components/CreateNodeModal";
import DetailPanel from "../components/DetailPanel";
import EmptyGraphState from "../components/EmptyGraphState";
import ErrorBanner from "../components/ErrorBanner";
import FilterBar from "../components/FilterBar";
import GraphCanvas from "../components/GraphCanvas";
import LayoutSwitcher from "../components/LayoutSwitcher";
import NodeContextMenu, { type ContextMenuAction } from "../components/NodeContextMenu";
import { DEFAULT_LAYOUT, type LayoutName } from "../graph/layouts";
import { deleteNode, updateNode } from "../api/client";
import { useToast } from "../components/toastContext";
import type { GraphFilters, GraphResponse, PathResult } from "../types/graph";

interface GraphSectionProps {
  graph: GraphResponse;
  loading: boolean;
  error: string | null;
  filters: GraphFilters;
  onFiltersChange: (filters: GraphFilters) => void;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  highlightedPath: PathResult | null;
  onNodeChanged: () => void;
  showCreateNode: boolean;
  onOpenCreateNode: () => void;
  onCloseCreateNode: () => void;
  showCreateEdge: boolean;
  onOpenCreateEdge: () => void;
  onCloseCreateEdge: () => void;
  onGoToImport: () => void;
}

export default function GraphSection({
  graph,
  loading,
  error,
  filters,
  onFiltersChange,
  selectedNodeId,
  onSelectNode,
  highlightedPath,
  onNodeChanged,
  showCreateNode,
  onOpenCreateNode,
  onCloseCreateNode,
  showCreateEdge,
  onOpenCreateEdge,
  onCloseCreateEdge,
  onGoToImport,
}: GraphSectionProps) {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [layout, setLayout] = useState<LayoutName>(DEFAULT_LAYOUT);
  const [menu, setMenu] = useState<{ nodeId: string; x: number; y: number } | null>(null);

  const handleContextMenu = useCallback((nodeId: string, pos: { x: number; y: number }) => {
    setMenu({ nodeId, x: pos.x, y: pos.y });
  }, []);

  const menuNode = menu ? graph.nodes.find((n) => n.id === menu.nodeId) : null;

  async function toggleFlag(nodeId: string, flag: "is_entry_point" | "is_crown_jewel", next: boolean) {
    try {
      await updateNode(nodeId, { [flag]: next });
      toast(
        flag === "is_entry_point"
          ? next ? "Tagged as entry point" : "Entry point tag removed"
          : next ? "Tagged as crown jewel" : "Crown jewel tag removed",
      );
      onNodeChanged();
    } catch (e) {
      toast(String(e), "error");
    }
  }

  const menuActions: ContextMenuAction[] = menuNode
    ? [
        { id: "open", label: "Open details", onSelect: () => onSelectNode(menuNode.id) },
        {
          id: "entry",
          label: menuNode.is_entry_point ? "Remove entry point" : "Mark as entry point",
          onSelect: () => toggleFlag(menuNode.id, "is_entry_point", !menuNode.is_entry_point),
        },
        {
          id: "jewel",
          label: menuNode.is_crown_jewel ? "Remove crown jewel" : "Mark as crown jewel",
          onSelect: () => toggleFlag(menuNode.id, "is_crown_jewel", !menuNode.is_crown_jewel),
        },
        {
          id: "delete",
          label: "Delete node",
          destructive: true,
          onSelect: async () => {
            if (!confirm(`Delete "${menuNode.label}"? This can't be undone.`)) return;
            try {
              await deleteNode(menuNode.id);
              toast("Node deleted");
              onNodeChanged();
            } catch (e) {
              toast(String(e), "error");
            }
          },
        },
      ]
    : [];

  const highlight = highlightedPath
    ? {
        nodeIds: highlightedPath.nodes.map((n) => n.id),
        edgeIds: highlightedPath.edges.map((e) => e.id),
      }
    : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-surface-1 px-4 py-2">
        <h1 className="font-sans text-sm font-medium text-text-primary">Graph</h1>
        <div className="flex items-center gap-2 font-mono text-xs">
          <LayoutSwitcher value={layout} onChange={setLayout} />
          <input
            data-shortcut-search
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="search nodes… ( / )"
            className="w-48 rounded border border-border bg-surface-0 px-2 py-1.5 text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
          />
          <button
            onClick={onOpenCreateNode}
            className="rounded border border-border px-3 py-1.5 text-text-secondary hover:border-accent/60 hover:text-accent"
          >
            + node
          </button>
          <button
            onClick={onOpenCreateEdge}
            className="rounded border border-border px-3 py-1.5 text-text-secondary hover:border-accent/60 hover:text-accent"
          >
            + edge
          </button>
        </div>
      </div>

      <FilterBar filters={filters} onChange={onFiltersChange} />

      <div className="relative flex flex-1 overflow-hidden">
        <div className="relative flex-1">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-0/60 font-mono text-sm text-text-secondary">
              loading graph…
            </div>
          )}
          {error && (
            <div className="absolute left-4 top-4 z-10">
              <ErrorBanner message={error} />
            </div>
          )}
          {!loading && graph.nodes.length === 0 && !error ? (
            <EmptyGraphState onImport={onGoToImport} onCreateNode={onOpenCreateNode} />
          ) : (
            <GraphCanvas
              graph={graph}
              selectedNodeId={selectedNodeId}
              onSelectNode={onSelectNode}
              highlightedPath={highlight}
              searchQuery={searchQuery}
              layout={layout}
              onNodeContextMenu={handleContextMenu}
            />
          )}
        </div>

        {menu && menuNode && (
          <NodeContextMenu
            x={menu.x}
            y={menu.y}
            title={menuNode.label}
            actions={menuActions}
            onClose={() => setMenu(null)}
          />
        )}

        {selectedNodeId && (
          <DetailPanel
            nodeId={selectedNodeId}
            onClose={() => onSelectNode(null)}
            onChanged={onNodeChanged}
            onDeleted={() => {
              onSelectNode(null);
              onNodeChanged();
            }}
          />
        )}
      </div>

      {showCreateNode && (
        <CreateNodeModal
          onClose={onCloseCreateNode}
          onCreated={() => {
            onCloseCreateNode();
            onNodeChanged();
          }}
        />
      )}

      {showCreateEdge && (
        <CreateEdgeModal
          nodes={graph.nodes}
          onClose={onCloseCreateEdge}
          onCreated={() => {
            onCloseCreateEdge();
            onNodeChanged();
          }}
        />
      )}
    </div>
  );
}
