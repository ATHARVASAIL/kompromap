import { useEffect, useMemo, useState } from "react";
import { searchKnowledgeBase, getKBEntry, type KBEntry } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Skeleton from "../components/Skeleton";
import Spinner from "../components/Spinner";

type View = "list" | "detail";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#F2454E",
  high: "#F5883A",
  medium: "#F0C93A",
  low: "#4C8DF0",
  info: "#6B7488",
};

export default function KnowledgePage() {
  const [entries, setEntries] = useState<KBEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<KBEntry | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    searchKnowledgeBase("")
      .then((data) => { setEntries(data); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) { setSelectedEntry(null); return; }
    setDetailLoading(true);
    getKBEntry(selectedId)
      .then((entry) => { setSelectedEntry(entry); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        e.reference_id.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        (e.description && e.description.toLowerCase().includes(q)),
    );
  }, [entries, query]);

  if (error) return <ErrorBanner message={error} className="m-4" />;

  return (
    <div className="flex h-full">
      <div className="flex w-1/3 flex-col border-r border-border">
        <div className="border-b border-border bg-surface-1 px-4 py-3">
          <h1 className="font-sans text-sm font-medium text-text-primary">Knowledge Base</h1>
          <p className="font-mono text-[11px] text-text-tertiary">{entries.length} entries</p>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="search CVE, CWE, keyword…"
            className="mt-2 w-full rounded border border-border bg-surface-0 px-2 py-1 font-mono text-xs text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
          />
        </div>
        <div className="flex-1 overflow-auto">
          {loading && (
            <div className="p-4 space-y-2">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="p-4 font-mono text-xs text-text-tertiary">No matching entries.</div>
          )}
          {!loading && filtered.map((e) => (
            <button
              key={e.id}
              onClick={() => setSelectedId(e.id)}
              className={`block w-full border-b border-border-subtle px-3 py-2 text-left transition-colors ${
                selectedId === e.id ? "bg-accent/10" : "hover:bg-surface-2"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-text-tertiary">{e.source.toUpperCase()}</span>
                <span className="font-mono text-xs text-text-primary">{e.reference_id}</span>
              </div>
              <div className="mt-0.5 truncate font-sans text-xs text-text-secondary">{e.title}</div>
              {e.severity && (
                <span className="mt-1 inline-block rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ backgroundColor: SEVERITY_COLORS[e.severity] + "25", color: SEVERITY_COLORS[e.severity] }}>
                  {e.severity}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-surface-0">
        {detailLoading && (
          <div className="flex h-full items-center justify-center"><Spinner /></div>
        )}
        {!detailLoading && selectedEntry && (
          <div className="mx-auto max-w-2xl p-6">
            <div className="mb-4 flex items-center gap-2">
              <span className="rounded bg-accent/15 px-2 py-0.5 font-mono text-[10px] text-accent">{selectedEntry.source.toUpperCase()}</span>
              <span className="font-mono text-sm text-text-primary">{selectedEntry.reference_id}</span>
              {selectedEntry.severity && (
                <span className="rounded px-2 py-0.5 font-mono text-[10px]" style={{ backgroundColor: SEVERITY_COLORS[selectedEntry.severity] + "25", color: SEVERITY_COLORS[selectedEntry.severity] }}>
                  {selectedEntry.severity}
                </span>
              )}
            </div>
            <h2 className="font-sans text-lg font-medium text-text-primary">{selectedEntry.title}</h2>
            {selectedEntry.description && (
              <p className="mt-3 text-sm leading-relaxed text-text-secondary">{selectedEntry.description}</p>
            )}
            {selectedEntry.tags && selectedEntry.tags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1">
                {selectedEntry.tags.map((t) => (
                  <span key={t} className="rounded bg-surface-2 px-2 py-0.5 font-mono text-[10px] text-text-tertiary">{t}</span>
                ))}
              </div>
            )}
            {selectedEntry.mitigations && (
              <div className="mt-6">
                <h3 className="font-mono text-xs font-medium text-text-tertiary">Mitigations</h3>
                <div className="mt-2 whitespace-pre-wrap rounded border border-border bg-surface-1 p-3 font-mono text-xs text-text-secondary">{selectedEntry.mitigations}</div>
              </div>
            )}
            {selectedEntry.references && (
              <div className="mt-4">
                <h3 className="font-mono text-xs font-medium text-text-tertiary">References</h3>
                <div className="mt-2 whitespace-pre-wrap rounded border border-border bg-surface-1 p-3 font-mono text-[11px] text-text-tertiary">{selectedEntry.references}</div>
              </div>
            )}
            <div className="mt-6 font-mono text-[10px] text-text-tertiary">
              Created {selectedEntry.created_at ? new Date(selectedEntry.created_at).toLocaleDateString() : "—"} · Updated {selectedEntry.updated_at ? new Date(selectedEntry.updated_at).toLocaleDateString() : "—"}
            </div>
          </div>
        )}
        {!detailLoading && !selectedEntry && (
          <div className="flex h-full items-center justify-center p-8">
            <div className="font-mono text-sm text-text-tertiary">Select an entry to view details.</div>
          </div>
        )}
      </div>
    </div>
  );
}
