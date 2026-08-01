import { useEffect, useState } from "react";
import { createSnapshot, deleteSnapshot, diffSnapshot, listSnapshots } from "../api/client";
import EmptyState from "./EmptyState";
import ErrorBanner from "./ErrorBanner";
import Skeleton from "./Skeleton";
import type { GraphDiff, SnapshotSummary } from "../types/graph";

interface SnapshotPanelProps {
  engagementId: string;
  onClose: () => void;
}

export default function SnapshotPanel({ engagementId, onClose }: SnapshotPanelProps) {
  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [creating, setCreating] = useState(false);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [compareToId, setCompareToId] = useState<string>("");
  const [diff, setDiff] = useState<GraphDiff | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  function load() {
    setLoading(true);
    listSnapshots(engagementId)
      .then(setSnapshots)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [engagementId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newLabel.trim()) return;
    setCreating(true);
    try {
      await createSnapshot(engagementId, newLabel.trim());
      setNewLabel("");
      load();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteSnapshot(id);
      if (selectedId === id) {
        setSelectedId(null);
        setDiff(null);
      }
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  async function loadDiff(id: string, compareTo: string) {
    setSelectedId(id);
    setDiffLoading(true);
    setDiff(null);
    try {
      const result = await diffSnapshot(id, compareTo || undefined);
      setDiff(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setDiffLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 font-mono text-sm">
      <div className="flex max-h-[85vh] w-[42rem] animate-fade-in-scale overflow-hidden rounded border border-border bg-surface-1 shadow-xl">
        <div className="flex w-56 flex-col border-r border-border">
          <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
            <span className="text-text-tertiary">snapshots</span>
            <button onClick={onClose} className="text-text-tertiary hover:text-text-primary" aria-label="Close">
              ✕
            </button>
          </div>

          <form onSubmit={handleCreate} className="space-y-2 border-b border-border p-3">
            <input
              placeholder="label, e.g. 'Day 1'"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
            />
            <button
              type="submit"
              disabled={creating}
              className="w-full rounded border border-accent bg-accent/10 py-1.5 text-xs text-accent hover:bg-accent/20 disabled:opacity-50"
            >
              {creating ? "capturing…" : "capture snapshot"}
            </button>
          </form>

          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="space-y-2 px-3 py-3">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            )}
            {snapshots.map((s) => (
              <div
                key={s.id}
                className={`group flex items-center justify-between px-3 py-2 text-xs hover:bg-surface-2 ${
                  selectedId === s.id ? "bg-surface-2" : ""
                }`}
              >
                <button
                  onClick={() => loadDiff(s.id, "")}
                  className={`flex-1 truncate text-left ${selectedId === s.id ? "text-accent" : "text-text-secondary"}`}
                >
                  {s.label}
                  <div className="text-[10px] text-text-tertiary">
                    {s.node_count}n · {s.edge_count}e
                  </div>
                </button>
                <button
                  onClick={() => handleDelete(s.id)}
                  className="ml-2 text-text-tertiary opacity-0 hover:text-severity-critical group-hover:opacity-100"
                  aria-label="Delete snapshot"
                >
                  ✕
                </button>
              </div>
            ))}
            {!loading && snapshots.length === 0 && (
              <EmptyState message="No snapshots yet." className="mx-3 my-3" />
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 text-xs">
          {error && <ErrorBanner message={error} className="mb-3" />}

          {!selectedId ? (
            <EmptyState message="Select a snapshot to compare it against the current graph." />
          ) : (
            <>
              <div className="mb-3 flex items-center gap-2">
                <span className="text-text-tertiary">compare against</span>
                <select
                  value={compareToId}
                  onChange={(e) => {
                    setCompareToId(e.target.value);
                    loadDiff(selectedId, e.target.value);
                  }}
                  className="rounded border border-border bg-surface-0 px-2 py-1 text-text-secondary focus:border-accent focus:outline-none"
                >
                  <option value="">current live graph</option>
                  {snapshots
                    .filter((s) => s.id !== selectedId)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                </select>
              </div>

              {diffLoading && <p className="text-text-tertiary">computing diff…</p>}

              {diff && (
                <div className="space-y-4">
                  <DiffSection title="nodes added" entries={diff.nodes_added} color="text-accent" />
                  <DiffSection title="nodes removed" entries={diff.nodes_removed} color="text-severity-critical" />
                  <DiffSection title="edges added" entries={diff.edges_added} color="text-accent" />
                  <DiffSection title="edges removed" entries={diff.edges_removed} color="text-severity-critical" />
                  {diff.nodes_added.length === 0 &&
                    diff.nodes_removed.length === 0 &&
                    diff.edges_added.length === 0 &&
                    diff.edges_removed.length === 0 && (
                      <EmptyState message="No changes between these two points." />
                    )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function DiffSection({
  title,
  entries,
  color,
}: {
  title: string;
  entries: { id: string; label: string; node_type?: string; edge_type?: string }[];
  color: string;
}) {
  if (entries.length === 0) return null;
  return (
    <div>
      <div className={`mb-1.5 ${color}`}>
        {title} ({entries.length})
      </div>
      <div className="space-y-1">
        {entries.map((e) => (
          <div key={e.id} className="flex items-center gap-2 text-text-tertiary">
            <span className="text-text-tertiary">{e.node_type ?? e.edge_type}</span>
            <span className="truncate text-text-secondary">{e.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
