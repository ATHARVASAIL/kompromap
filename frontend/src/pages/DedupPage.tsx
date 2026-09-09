import { useEffect, useMemo, useState } from "react";
import {
  runDedupScan,
  listDedupCandidates,
  resolveDedupCandidate,
  type MergeCandidateRead,
  type MergeCandidateResolve,
} from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";

interface ScanState {
  scan: { id: string; total_candidates: number; high_confidence_count: number; merged_count: number; dismissed_count: number } | null;
  candidates: MergeCandidateRead[];
  loading: boolean;
  error: string | null;
}

type Tab = "pending" | "merged" | "dismissed";

export default function DedupPage() {
  const [state, setState] = useState<ScanState>({ scan: null, candidates: [], loading: false, error: null });
  const [tab, setTab] = useState<Tab>("pending");
  const [threshold, setThreshold] = useState(0.75);
  const [running, setRunning] = useState(false);

  function loadCandidates() {
    setState((s) => ({ ...s, loading: true, error: null }));
    listDedupCandidates(tab === "pending" ? undefined : tab)
      .then((candidates) => setState((s) => ({ ...s, candidates, loading: false })))
      .catch((e) => setState((s) => ({ ...s, error: String(e), loading: false })));
  }

  useEffect(() => { loadCandidates(); }, [tab]);

  async function handleScan() {
    setRunning(true);
    setState((s) => ({ ...s, error: null }));
    try {
      const res = await runDedupScan(threshold);
      setState({ scan: res.scan, candidates: res.candidates, loading: false, error: null });
      setTab("pending");
    } catch (e) {
      setState((s) => ({ ...s, error: String(e) }));
    } finally {
      setRunning(false);
    }
  }

  async function handleResolve(id: string, action: "merged" | "dismissed") {
    const notes = prompt(action === "merged" ? "Notes on this merge (optional):" : "Notes on this dismissal (optional):");
    if (notes === null) return;
    try {
      await resolveDedupCandidate(id, action, notes || undefined);
      setState((s) => ({
        ...s,
        candidates: s.candidates.map((c) => (c.id === id ? { ...c, status: action, notes: notes || c.notes, resolved_at: new Date().toISOString() } : c)),
      }));
    } catch (e) {
      setState((s) => ({ ...s, error: String(e) }));
    }
  }

  const displayed = useMemo(() => state.candidates.filter((c) => c.status === tab), [state.candidates, tab]);

  function scoreColor(score: number): string {
    if (score >= 0.85) return "text-critical";
    if (score >= 0.75) return "text-warning";
    return "text-text-tertiary";
  }

  function scoreLabel(score: number): string {
    if (score >= 0.85) return "High";
    if (score >= 0.75) return "Medium";
    return "Low";
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-border bg-surface-1 px-4 py-3">
        <h1 className="font-sans text-sm font-medium text-text-primary">Deduplication</h1>
        <p className="font-mono text-xs text-text-tertiary">Similarity scoring across findings — analyst approves every merge.</p>
        <div className="ml-auto flex items-center gap-2">
          <label className="font-mono text-xs text-text-tertiary">Threshold</label>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value) || 0.75)}
            className="w-16 rounded border border-border bg-surface-0 px-2 py-1 font-mono text-xs text-text-secondary focus:border-accent/60 focus:outline-none"
          />
          <button
            onClick={handleScan}
            disabled={running}
            className="rounded bg-accent px-3 py-1 font-mono text-xs text-black hover:bg-accent/80 disabled:opacity-50"
          >
            {running ? "Scanning…" : state.scan ? "Rescan" : "Run Scan"}
          </button>
        </div>
      </div>

      {state.error && <ErrorBanner message={state.error} className="m-4" />}

      {state.scan && (
        <div className="flex gap-4 border-b border-border bg-surface-1/50 px-4 py-2 font-mono text-xs text-text-secondary">
          <span>Total: {state.scan.total_candidates}</span>
          <span className="text-warning">High confidence: {state.scan.high_confidence_count}</span>
          <span className="text-success">Merged: {state.scan.merged_count}</span>
          <span className="text-text-tertiary">Dismissed: {state.scan.dismissed_count}</span>
        </div>
      )}

      <div className="flex gap-1 border-b border-border bg-surface-1 px-4">
        {(["pending", "merged", "dismissed"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 font-mono text-xs capitalize transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent" : "text-text-tertiary hover:text-text-secondary"
            }`}
          >
            {t} {t === "pending" && state.candidates.filter((c) => c.status === "pending").length > 0 && `(${state.candidates.filter((c) => c.status === "pending").length})`}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        {state.loading && (
          <div className="flex items-center justify-center p-8"><Spinner /></div>
        )}
        {!state.loading && displayed.length === 0 && (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState message={tab === "pending" ? "Run a dedup scan to find similar findings." : `No ${tab} candidates.`} />
          </div>
        )}
        {!state.loading && displayed.length > 0 && (
          <table className="w-full border-collapse font-mono text-xs">
            <thead className="sticky top-0 z-10 bg-surface-1 text-text-tertiary shadow-[0_1px_0_0_rgb(var(--border-subtle))]">
              <tr>
                <th className="px-3 py-2 text-left font-normal">Score</th>
                <th className="px-3 py-2 text-left font-normal">Finding A</th>
                <th className="px-3 py-2 text-left font-normal">Finding B</th>
                <th className="px-3 py-2 text-left font-normal">Endpoint</th>
                <th className="px-3 py-2 text-left font-normal">CWE</th>
                <th className="px-3 py-2 text-left font-normal">Confidence</th>
                {tab === "pending" && <th className="px-3 py-2 text-right font-normal">Action</th>}
              </tr>
            </thead>
            <tbody>
              {displayed.map((c, i) => (
                <tr
                  key={c.id}
                  style={{ animationDelay: `${Math.min(i, 20) * 25}ms` }}
                  className="group animate-fade-in border-t border-border-subtle transition-colors duration-150 hover:bg-surface-2"
                >
                  <td className={`px-3 py-2 font-mono ${scoreColor(c.overall_score)}`}>
                    {(c.overall_score * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-text-primary">{c.finding_a_id.slice(0, 8)}…</td>
                  <td className="px-3 py-2 text-text-primary">{c.finding_b_id.slice(0, 8)}…</td>
                  <td className="px-3 py-2 text-text-secondary">{(c.endpoint_similarity * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-text-secondary">{(c.cwe_similarity * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 ${c.overall_score >= 0.85 ? "bg-warning/15 text-warning" : c.overall_score >= 0.75 ? "bg-accent/15 text-accent" : "bg-surface-2 text-text-tertiary"}`}>
                      {scoreLabel(c.overall_score)}
                    </span>
                  </td>
                  {tab === "pending" && (
                    <td className="px-3 py-2 text-right">
                      <div className="flex justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          onClick={() => handleResolve(c.id, "merged")}
                          className="rounded border border-success/40 px-2 py-0.5 font-mono text-[11px] text-success hover:bg-success/10"
                        >
                          Merge
                        </button>
                        <button
                          onClick={() => handleResolve(c.id, "dismissed")}
                          className="rounded border border-border px-2 py-0.5 font-mono text-[11px] text-text-tertiary hover:border-accent/40 hover:text-accent"
                        >
                          Keep separate
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
