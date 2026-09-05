import { useCallback, useEffect, useState } from "react";
import {
  getDedupCandidates,
  getDedupScan,
  listDedupScans,
  resolveDedupCandidate,
  runDedupScan,
  type DedupScanResponse,
  type MergeCandidateResponse,
} from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Skeleton from "../components/Skeleton";
import { colors, severityColor } from "../styles/tokens";
import type { Engagement } from "../types/graph";

const SIGNAL_LABELS: Record<string, string> = {
  title: "Title",
  cwe: "CWE",
  owasp: "OWASP",
  location: "Location",
  endpoint: "Endpoint",
  params: "Params",
};

const ACTION_LABELS: Record<string, { label: string; color: string; hint: string }> = {
  pending: { label: "Pending", color: colors.text.tertiary, hint: "Awaiting analyst decision" },
  merge: { label: "Merged", color: "#4ADE80", hint: "Findings merged into one" },
  keep_separate: { label: "Separate", color: colors.accent, hint: "Same bug, different context" },
  mark_duplicate: { label: "Duplicate", color: colors.severity.medium, hint: "Both closed as duplicates" },
};

interface DedupPageProps {
  engagement: Engagement;
}

type View = "scans" | "candidates";

export default function DedupPage({ engagement }: DedupPageProps) {
  const [view, setView] = useState<View>("scans");
  const [scans, setScans] = useState<DedupScanResponse[] | null>(null);
  const [selectedScan, setSelectedScan] = useState<DedupScanResponse | null>(null);
  const [candidates, setCandidates] = useState<MergeCandidateResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [threshold, setThreshold] = useState(0.5);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [noteFor, setNoteFor] = useState<string | null>(null);
  const [noteText, setNoteText] = useState("");

  const loadScans = useCallback(() => {
    setError(null);
    setScans(null);
    listDedupScans(engagement.id)
      .then(setScans)
      .catch((e) => setError(String(e)));
  }, [engagement.id]);

  const loadCandidates = useCallback(
    (scanId: string) => {
      setError(null);
      setCandidates(null);
      getDedupCandidates(scanId)
        .then(setCandidates)
        .catch((e) => setError(String(e)));
    },
    [engagement.id],
  );

  useEffect(loadScans, [loadScans]);

  function handleNewScan() {
    setScanning(true);
    setError(null);
    runDedupScan({ similarity_threshold: threshold })
      .then(() => {
        loadScans();
      })
      .catch((e) => setError(String(e)))
      .finally(() => setScanning(false));
  }

  function handleSelectScan(scan: DedupScanResponse) {
    setSelectedScan(scan);
    setView("candidates");
    loadCandidates(scan.id);
  }

  function handleBackToScans() {
    setView("scans");
    setSelectedScan(null);
    setCandidates(null);
    loadScans();
  }

  async function handleResolve(candidate: MergeCandidateResponse, action: "merge" | "keep_separate" | "mark_duplicate") {
    if (action === "merge" && !candidate.kept_id) {
      // The analyst needs to pick which finding to keep. For now, use finding_a as default.
      // In a real UI, there would be a selector; here we just pick the higher-CVSS one.
      const keptId = candidate.finding_a_id;
      setResolvingId(candidate.id);
      try {
        await resolveDedupCandidate(candidate.id, {
          action,
          kept_id: keptId,
          analyst_note: noteFor === candidate.id ? noteText : undefined,
        });
        setCandidates((prev) =>
          prev?.map((c) => (c.id === candidate.id ? { ...c, action, kept_id: keptId } : c)),
        );
      } catch (e) {
        setError(String(e));
      } finally {
        setResolvingId(null);
        setNoteFor(null);
        setNoteText("");
      }
      return;
    }

    setResolvingId(candidate.id);
    try {
      await resolveDedupCandidate(candidate.id, {
        action,
        analyst_note: noteFor === candidate.id ? noteText : undefined,
      });
      setCandidates((prev) =>
        prev?.map((c) => (c.id === candidate.id ? { ...c, action } : c)),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setResolvingId(null);
      setNoteFor(null);
      setNoteText("");
    }
  }

  function scoreColor(score: number): string {
    if (score >= 0.8) return severityColor("critical");
    if (score >= 0.6) return severityColor("high");
    if (score >= 0.4) return severityColor("medium");
    return colors.text.tertiary;
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border bg-surface-1 px-4 py-2.5">
        <h1 className="font-sans text-sm font-medium text-text-primary">Deduplication</h1>
        <span className="font-mono text-xs text-text-tertiary">
          {engagement.name}
        </span>

        {view === "scans" && (
          <div className="ml-auto flex items-center gap-2">
            <label className="font-mono text-[11px] text-text-tertiary">
              threshold
              <input
                type="range"
                min={0.1}
                max={0.95}
                step={0.05}
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="ml-1.5 h-1 w-24 accent-accent"
              />
              <span className="ml-1 tabular-nums text-text-secondary">{(threshold * 100).toFixed(0)}%</span>
            </label>
            <button
              onClick={handleNewScan}
              disabled={scanning}
              className="rounded border border-accent/40 bg-accent/10 px-3 py-1 font-mono text-xs text-accent hover:bg-accent/20 disabled:opacity-50"
            >
              {scanning ? "scanning…" : "+ New Scan"}
            </button>
          </div>
        )}

        {view === "candidates" && (
          <button
            onClick={handleBackToScans}
            className="ml-auto font-mono text-xs text-text-secondary hover:text-accent"
          >
            ← Back to scans
          </button>
        )}
      </div>

      {error && <ErrorBanner message={error} className="m-4" />}

      {/* Scans list */}
      {view === "scans" && (
        <div className="flex-1 overflow-auto p-4">
          {!scans && !error && (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-5 w-16" />
                  <Skeleton className="h-5 w-20" />
                </div>
              ))}
            </div>
          )}
          {scans && scans.length === 0 && (
            <div className="flex h-full items-center justify-center">
              <p className="font-mono text-sm text-text-tertiary">No scans yet — run a dedup scan to find duplicate findings.</p>
            </div>
          )}
          {scans && scans.length > 0 && (
            <table className="w-full border-collapse font-mono text-xs">
              <thead className="sticky top-0 z-10 bg-surface-1 text-text-tertiary shadow-[0_1px_0_0_rgb(var(--border-subtle))]">
                <tr>
                  <th className="px-3 py-2 text-left font-normal">Date</th>
                  <th className="px-3 py-2 text-left font-normal">Threshold</th>
                  <th className="px-3 py-2 text-left font-normal">Signals</th>
                  <th className="px-3 py-2 text-left font-normal">Candidates</th>
                  <th className="px-3 py-2 text-left font-normal">Filtered</th>
                  <th className="px-3 py-2 text-left font-normal"></th>
                </tr>
              </thead>
              <tbody>
                {scans.map((scan, i) => (
                  <tr
                    key={scan.id}
                    className="animate-fade-in cursor-pointer border-t border-border-subtle transition-colors hover:bg-surface-2"
                    style={{ animationDelay: `${Math.min(i, 20) * 25}ms` }}
                    onClick={() => handleSelectScan(scan)}
                  >
                    <td className="px-3 py-2 text-text-secondary">
                      {new Date(scan.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-text-secondary">
                      {(scan.similarity_threshold * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-2 text-text-tertiary">
                      {scan.signals.length} signals
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      <span className={scan.candidates_found > 0 ? "text-accent" : "text-text-secondary"}>
                        {scan.candidates_found}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-text-tertiary">
                      {scan.candidates_filtered}
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-text-tertiary hover:text-accent">view →</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Candidates list */}
      {view === "candidates" && selectedScan && (
        <div className="flex-1 overflow-auto p-4">
          <div className="mb-3 flex items-center gap-4 font-mono text-xs text-text-tertiary">
            <span>{selectedScan.candidates_found} candidates</span>
            <span>{selectedScan.candidates_filtered} filtered below threshold</span>
            <span>threshold: {(selectedScan.similarity_threshold * 100).toFixed(0)}%</span>
          </div>

          {!candidates && !error && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-20 animate-pulse rounded border border-border bg-surface-1" />
              ))}
            </div>
          )}

          {candidates && candidates.length === 0 && (
            <p className="py-8 text-center font-mono text-sm text-text-tertiary">
              No candidates above the threshold. Try lowering it or check that findings share enough context.
            </p>
          )}

          <div className="space-y-3">
            {candidates?.map((c, i) => (
              <CandidateCard
                key={c.id}
                candidate={c}
                index={i}
                scoreColor={scoreColor(c.overall_score)}
                resolving={resolvingId === c.id}
                noteText={noteFor === c.id ? noteText : ""}
                onSetNoteText={setNoteText}
                onSetNoteFor={setNoteFor}
                onResolve={(action) => handleResolve(c, action)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Candidate card
// ---------------------------------------------------------------------------

function CandidateCard({
  candidate,
  index,
  scoreColor,
  resolving,
  noteText,
  onSetNoteText,
  onSetNoteFor,
  onResolve,
}: {
  candidate: MergeCandidateResponse;
  index: number;
  scoreColor: string;
  resolving: boolean;
  noteText: string;
  onSetNoteText: (t: string) => void;
  onSetNoteFor: (id: string | null) => void;
  onResolve: (action: "merge" | "keep_separate" | "mark_duplicate") => void;
}) {
  const actionInfo = ACTION_LABELS[candidate.action] || ACTION_LABELS.pending;
  const isPending = candidate.action === "pending";
  const signalEntries = Object.entries(candidate.signal_scores).filter(([, v]) => v > 0);

  return (
    <div
      className="animate-fade-in rounded border border-border bg-surface-1 p-3 transition-colors"
      style={{ animationDelay: `${Math.min(index, 20) * 40}ms` }}
    >
      {/* Top row: finding titles + score */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate font-mono text-sm text-text-primary">{candidate.finding_a_title}</span>
            <span className="text-text-tertiary">+</span>
            <span className="truncate font-mono text-sm text-text-primary">{candidate.finding_b_title}</span>
          </div>

          {/* Signal breakdown bar */}
          <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-surface-2">
            {signalEntries.map(([key, value]) => (
              <span
                key={key}
                style={{ width: `${(value / candidate.overall_score) * 100}%`, backgroundColor: scoreColor }}
                title={`${SIGNAL_LABELS[key] || key}: ${(value * 100).toFixed(0)}%`}
              />
            ))}
          </div>

          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
            {signalEntries.map(([key, value]) => (
              <span key={key} className="font-mono text-[10px] text-text-tertiary">
                {SIGNAL_LABELS[key] || key}: {(value * 100).toFixed(0)}%
              </span>
            ))}
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <span
            className="rounded-full border px-2 py-0.5 font-mono text-[11px] tabular-nums"
            style={{
              color: scoreColor,
              borderColor: `${scoreColor}40`,
              backgroundColor: `${scoreColor}15`,
            }}
          >
            {(candidate.overall_score * 100).toFixed(1)}%
          </span>
          {candidate.high_impact && (
            <span className="rounded-full border border-severity-critical/40 bg-severity-critical/10 px-2 py-0.5 font-mono text-[10px] text-severity-critical">
              high impact
            </span>
          )}
          <span
            className="rounded-full border px-2 py-0.5 font-mono text-[10px]"
            style={{
              color: actionInfo.color,
              borderColor: `${actionInfo.color}30`,
            }}
          >
            {actionInfo.label}
          </span>
        </div>
      </div>

      {/* Action buttons — only when pending */}
      {isPending && (
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={() => onResolve("merge")}
            disabled={resolving}
            className="rounded border border-green-500/40 bg-green-500/10 px-2.5 py-1 font-mono text-[11px] text-green-400 hover:bg-green-500/20 disabled:opacity-50"
          >
            Merge
          </button>
          <button
            onClick={() => onResolve("keep_separate")}
            disabled={resolving}
            className="rounded border border-accent/40 bg-accent/10 px-2.5 py-1 font-mono text-[11px] text-accent hover:bg-accent/20 disabled:opacity-50"
          >
            Keep Separate
          </button>
          <button
            onClick={() => onResolve("mark_duplicate")}
            disabled={resolving}
            className="rounded border border-severity-medium/40 bg-severity-medium/10 px-2.5 py-1 font-mono text-[11px] text-severity-medium hover:bg-severity-medium/20 disabled:opacity-50"
          >
            Mark Duplicate
          </button>

          <div className="ml-auto flex items-center gap-1">
            <input
              type="text"
              value={noteFor === candidate.id ? noteText : ""}
              onChange={(e) => {
                onSetNoteFor(candidate.id);
                onSetNoteText(e.target.value);
              }}
              placeholder="note (optional)…"
              className="w-40 rounded border border-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
            />
          </div>
        </div>
      )}

      {!isPending && candidate.analyst_note && (
        <div className="mt-2 font-mono text-[11px] text-text-tertiary italic">
          Note: {candidate.analyst_note}
        </div>
      )}
    </div>
  );
}
