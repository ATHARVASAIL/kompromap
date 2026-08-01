import { useState } from "react";
import { createEdge } from "../api/client";
import ErrorBanner from "./ErrorBanner";
import Spinner from "./Spinner";
import { useToast } from "./ToastProvider";
import { EDGE_TYPE_LABELS, type EdgeType, type GraphNode } from "../types/graph";

interface CreateEdgeModalProps {
  nodes: GraphNode[];
  onClose: () => void;
  onCreated: () => void;
}

const EDGE_TYPES = Object.keys(EDGE_TYPE_LABELS) as EdgeType[];

export default function CreateEdgeModal({ nodes, onClose, onCreated }: CreateEdgeModalProps) {
  const { toast } = useToast();
  const [sourceId, setSourceId] = useState(nodes[0]?.id ?? "");
  const [targetId, setTargetId] = useState(nodes[1]?.id ?? nodes[0]?.id ?? "");
  const [edgeType, setEdgeType] = useState<EdgeType>("HOSTS");
  const [weight, setWeight] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createEdge({
        source_node_id: sourceId,
        target_node_id: targetId,
        edge_type: edgeType,
        ...(weight ? { weight: Number(weight) } : {}),
      });
      toast(`${edgeType} edge created`, "success");
      onCreated();
    } catch (err) {
      setError(String(err));
      toast("Couldn't create edge", "error");
    } finally {
      setSaving(false);
    }
  }

  if (nodes.length < 2) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 font-mono text-sm">
        <div className="w-96 animate-fade-in-scale rounded border border-border bg-surface-1 p-5 shadow-xl">
          <p className="text-text-secondary">You need at least two nodes on the graph before you can connect them.</p>
          <button
            onClick={onClose}
            className="mt-4 w-full rounded border border-border py-1.5 text-text-tertiary hover:border-border-strong"
          >
            close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 font-mono text-sm">
      <form
        onSubmit={handleSubmit}
        className="w-96 animate-fade-in-scale rounded border border-border bg-surface-1 p-5 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-text-primary">create edge</h2>
          <button type="button" onClick={onClose} className="text-text-tertiary hover:text-text-primary">
            ✕
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-text-tertiary">source</label>
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  [{n.node_type}] {n.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-tertiary">edge type</label>
            <select
              value={edgeType}
              onChange={(e) => setEdgeType(e.target.value as EdgeType)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
            >
              {EDGE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-tertiary">target</label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  [{n.node_type}] {n.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-text-tertiary">
              ease weight (optional, 0–1)
            </label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        {error && <ErrorBanner message={error} className="mt-3" />}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded border border-border py-1.5 text-text-tertiary hover:border-border-strong"
          >
            cancel
          </button>
          <button
            type="submit"
            disabled={saving || sourceId === targetId}
            className="flex flex-1 items-center justify-center gap-2 rounded border border-accent bg-accent/10 py-1.5 text-accent hover:bg-accent/20 disabled:opacity-50"
          >
            {saving && <Spinner />}
            {saving ? "creating…" : "create"}
          </button>
        </div>
        {sourceId === targetId && (
          <p className="mt-2 text-xs text-severity-medium">source and target must be different nodes</p>
        )}
      </form>
    </div>
  );
}
