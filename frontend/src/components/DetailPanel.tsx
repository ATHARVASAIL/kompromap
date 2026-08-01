import { useEffect, useState } from "react";
import { deleteNode, fetchNode, updateNode } from "../api/client";
import ErrorBanner from "./ErrorBanner";
import Skeleton from "./Skeleton";
import Spinner from "./Spinner";
import { useToast } from "./ToastProvider";
import { NODE_TYPE_COLOR, NODE_TYPE_LABELS, type NodeDetail } from "../types/graph";

interface DetailPanelProps {
  nodeId: string;
  onClose: () => void;
  onChanged: () => void;
  onDeleted: () => void;
}

const HIDDEN_FIELDS = new Set([
  "id",
  "node_type",
  "is_entry_point",
  "is_crown_jewel",
  "notes",
  "created_at",
  "updated_at",
]);

export default function DetailPanel({ nodeId, onClose, onChanged, onDeleted }: DetailPanelProps) {
  const { toast } = useToast();
  const [node, setNode] = useState<NodeDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNode(null);
    setError(null);
    fetchNode(nodeId)
      .then((n) => {
        setNode(n);
        setNotes(n.notes ?? "");
      })
      .catch((e) => setError(String(e)));
  }, [nodeId]);

  async function toggleFlag(flag: "is_entry_point" | "is_crown_jewel") {
    if (!node) return;
    try {
      const updated = await updateNode(node.id, { [flag]: !node[flag] });
      setNode(updated);
      onChanged();
      toast(
        flag === "is_entry_point"
          ? updated.is_entry_point
            ? "Tagged as entry point"
            : "Entry point tag removed"
          : updated.is_crown_jewel
            ? "Tagged as crown jewel"
            : "Crown jewel tag removed",
        "success",
      );
    } catch (e) {
      setError(String(e));
      toast("Couldn't update node", "error");
    }
  }

  async function saveNotes() {
    if (!node) return;
    setSaving(true);
    try {
      const updated = await updateNode(node.id, { notes });
      setNode(updated);
      onChanged();
      toast("Notes saved", "success");
    } catch (e) {
      setError(String(e));
      toast("Couldn't save notes", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!node) return;
    if (!confirm(`Delete this ${NODE_TYPE_LABELS[node.node_type]} node? This can't be undone.`)) return;
    try {
      await deleteNode(node.id);
      toast("Node deleted", "success");
      onDeleted();
    } catch (e) {
      setError(String(e));
      toast("Couldn't delete node", "error");
    }
  }

  return (
    <aside className="flex h-full w-80 animate-slide-in-right flex-col border-l border-border bg-surface-1/70 font-mono text-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-text-tertiary">node detail</span>
        <button onClick={onClose} className="text-text-tertiary hover:text-text-primary" aria-label="Close">
          ✕
        </button>
      </div>

      {error && <ErrorBanner message={error} className="mx-4 mt-3" />}

      {!node ? (
        <div className="space-y-3 px-4 py-4">
          <Skeleton className="h-5 w-20" />
          <div className="flex gap-2">
            <Skeleton className="h-8 flex-1" />
            <Skeleton className="h-8 flex-1" />
          </div>
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      ) : (
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <div>
            <span
              className="inline-block rounded px-2 py-0.5 text-xs font-semibold text-surface-0"
              style={{ backgroundColor: NODE_TYPE_COLOR[node.node_type] }}
            >
              {NODE_TYPE_LABELS[node.node_type]}
            </span>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => toggleFlag("is_entry_point")}
              className={`flex-1 rounded border px-2 py-1.5 text-xs transition-colors ${
                node.is_entry_point
                  ? "border-accent bg-accent/10 text-accent"
                  : "border-border text-text-tertiary hover:border-border-strong"
              }`}
            >
              entry point
            </button>
            <button
              onClick={() => toggleFlag("is_crown_jewel")}
              className={`flex-1 rounded border px-2 py-1.5 text-xs transition-colors ${
                node.is_crown_jewel
                  ? "border-severity-critical bg-severity-critical/10 text-severity-critical"
                  : "border-border text-text-tertiary hover:border-border-strong"
              }`}
            >
              crown jewel
            </button>
          </div>

          <dl className="space-y-2 border-t border-border pt-4">
            {Object.entries(node)
              .filter(([key]) => !HIDDEN_FIELDS.has(key))
              .map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs text-text-tertiary">{key}</dt>
                  <dd className="break-words text-text-primary">
                    {Array.isArray(value)
                      ? value.length
                        ? value.join(", ")
                        : "—"
                      : value === null || value === ""
                        ? "—"
                        : String(value)}
                  </dd>
                </div>
              ))}
          </dl>

          <div className="border-t border-border pt-4">
            <label className="mb-1 block text-xs text-text-tertiary" htmlFor="notes">
              notes
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              className="w-full resize-none rounded border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
            />
            <button
              onClick={saveNotes}
              disabled={saving}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded border border-border py-1.5 text-xs text-text-secondary hover:border-accent hover:text-accent disabled:opacity-50"
            >
              {saving && <Spinner />}
              {saving ? "saving…" : "save notes"}
            </button>
          </div>

          <div className="border-t border-border pt-4 text-xs text-text-tertiary">
            created {new Date(node.created_at).toLocaleString()}
          </div>

          <button
            onClick={handleDelete}
            className="w-full rounded border border-severity-critical/50 py-1.5 text-xs text-severity-critical hover:bg-severity-critical/10"
          >
            delete node
          </button>
        </div>
      )}
    </aside>
  );
}
