import { useMemo, useState } from "react";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import ScoreExplainer from "../components/ScoreExplainer";
import { getActiveEngagement } from "../api/client";
import type { Edge, GraphResponse, NodeType, ScoreBreakdown } from "../types/graph";

type SortKey = "ease_score" | "cvss_score" | "label";
type FilterKey = "all" | "crown_jewel" | "entry_point" | "extended";

interface CorrelationPageProps {
  graph: GraphResponse;
}

/**
 * Correlation page — shows how findings correlate to their attack targets
 * and how extended risk factors (asset criticality, data sensitivity,
 * exposure) change their effective severity.
 *
 * Phase 3 deliverable: the same finding scores differently depending on
 * what it can reach. A SQLi that yields credentials to a PCI DataStore
 * is a different risk than the same SQLi that yields nothing. This page
 * makes that visible — sortable, filterable, with per-finding breakdown.
 */
export default function CorrelationPage({ graph }: CorrelationPageProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("ease_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const [selectedBreakdown, setSelectedBreakdown] = useState<{
    finding: GraphResponse["nodes"][0];
    targets: GraphResponse["nodes"][0][];
    breakdown: ScoreBreakdown;
  } | null>(null);

  const findings = useMemo(() => {
    return graph.nodes.filter((n) => n.node_type === NodeType.FINDING);
  }, [graph.nodes]);

  const edgesBySource = useMemo(() => {
    const map = new Map<string, Edge[]>();
    for (const e of graph.edges) {
      const arr = map.get(e.source) ?? [];
      arr.push(e);
      map.set(e.source, arr);
    }
    return map;
  }, [graph.edges]);

  const nodeById = useMemo(() => {
    const map = new Map<string, GraphResponse["nodes"][0]>();
    for (const n of graph.nodes) map.set(n.id, n);
    return map;
  }, [graph.nodes]);

  // Build scored rows: finding + its targets + breakdown
  const rows = useMemo(() => {
    const result: {
      finding: GraphResponse["nodes"][0];
      targets: GraphResponse["nodes"][0][];
      breakdown: ScoreBreakdown;
      hasExtended: boolean;
    }[] = [];

    for (const f of findings) {
      const yieldsEdges = (edgesBySource.get(f.id) ?? []).filter(
        (e) => e.edge_type === "YIELDS",
      );
      const targets = yieldsEdges
        .map((e) => nodeById.get(e.target))
        .filter((n): n is NonNullable<typeof n> => n != null);

      // Build a breakdown from the finding's existing score data — the
      // backend already computed this during path-finding, so we reuse
      // it here rather than asking the backend again.
      const breakdown: ScoreBreakdown = {
        ease_score: f.score ?? 0,
        normalized_cvss: (f.cvss_score ?? 0) / 10,
        exploit_public: f.exploit_public ? 1 : 0,
        unauthenticated: f.auth_required ? 0 : 1,
        complexity: 0.5,
        complexity_measured: false,
        asset_criticality: 0,
        data_sensitivity: 0,
        exposure_factor: 0,
        contributions: {},
      };

      // Derive extended factors from targets
      let maxCrit = 0;
      let maxSens = 0;
      let maxExpo = 0;
      for (const t of targets) {
        if (t.node_type === NodeType.ASSET) maxCrit = Math.max(maxCrit, 0.6);
        if (t.node_type === NodeType.DATA_STORE) {
          maxSens = Math.max(maxSens, t.data_classification === "pci" ? 1.0 : t.data_classification === "pii" ? 0.8 : 0.1);
        }
        if (t.is_entry_point) maxExpo = 1.0;
        else if (t.is_crown_jewel) maxExpo = Math.max(maxExpo, 0.9);
      }
      breakdown.asset_criticality = maxCrit;
      breakdown.data_sensitivity = maxSens;
      breakdown.exposure_factor = maxExpo;
      breakdown.contributions = {
        cvss: breakdown.normalized_cvss * 0.4,
        exploit_public: breakdown.exploit_public * 0.3,
        unauthenticated: breakdown.unauthenticated * 0.2,
        complexity: (1 - breakdown.complexity) * 0.1,
        asset_criticality: breakdown.asset_criticality * 0.3,
        data_sensitivity: breakdown.data_sensitivity * 0.25,
        exposure_factor: breakdown.exposure_factor * 0.15,
      };
      const rawTotal =
        breakdown.normalized_cvss * 0.4 +
        breakdown.exploit_public * 0.3 +
        breakdown.unauthenticated * 0.2 +
        (1 - breakdown.complexity) * 0.1 +
        breakdown.asset_criticality * 0.3 +
        breakdown.data_sensitivity * 0.25 +
        breakdown.exposure_factor * 0.15;
      breakdown.ease_score = Math.max(0, Math.min(1, rawTotal));

      const hasExtended = targets.some(
        (t) => t.is_crown_jewel || t.is_entry_point || (t.data_classification && t.data_classification !== "none"),
      );

      result.push({ finding: f, targets, breakdown, hasExtended });
    }

    // Sort
    result.sort((a, b) => {
      const cmp =
        sortKey === "label"
          ? a.finding.label.localeCompare(b.finding.label)
          : sortKey === "cvss_score"
            ? (a.finding.cvss_score ?? 0) - (b.finding.cvss_score ?? 0)
            : a.breakdown.ease_score - b.breakdown.ease_score;
      return sortDir === "asc" ? cmp : -cmp;
    });

    // Filter
    if (filterKey === "crown_jewel")
      return result.filter((r) => r.targets.some((t) => t.is_crown_jewel));
    if (filterKey === "entry_point")
      return result.filter((r) => r.targets.some((t) => t.is_entry_point));
    if (filterKey === "extended") return result.filter((r) => r.hasExtended);
    return result;
  }, [findings, edgesBySource, nodeById, sortKey, sortDir, filterKey]);

  function cycleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  // While graph data loads in AppShell, show a brief spinner
  if (graph.nodes.length === 0) {
    return <Spinner label="Loading correlation data…" />;
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex shrink-0 items-center gap-3 border-b border-border px-4 py-2.5">
        <h2 className="font-sans text-sm font-semibold text-text-primary">Correlation</h2>
        <span className="text-text-tertiary">
          {findings.length} finding{findings.length !== 1 ? "s" : ""}
        </span>

        <div className="ml-auto flex items-center gap-2">
          {/* Sort buttons */}
          <div className="flex rounded border border-border">
            {[
              { key: "ease_score" as SortKey, label: "ease score" },
              { key: "cvss_score" as SortKey, label: "CVSS" },
              { key: "label" as SortKey, label: "name" },
            ].map((btn) => (
              <button
                key={btn.key}
                onClick={() => cycleSort(btn.key)}
                className={`px-2 py-1 font-mono text-[10px] transition-colors ${
                  sortKey === btn.key
                    ? "bg-accent/15 text-accent"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {btn.label}
                {sortKey === btn.key && <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>}
              </button>
            ))}
          </div>

          {/* Filter */}
          <select
            value={filterKey}
            onChange={(e) => setFilterKey(e.target.value as FilterKey)}
            className="rounded border border-border bg-surface-1 px-2 py-1 font-mono text-[11px] text-text-secondary"
          >
            <option value="all">all findings</option>
            <option value="crown_jewel">→ crown jewel</option>
            <option value="entry_point">→ entry point</option>
            <option value="extended">has extended context</option>
          </select>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <div className="flex h-full items-center justify-center p-8">
            <p className="text-text-tertiary">No findings match this filter.</p>
          </div>
        ) : (
          <div className="divide-y divide-border-subtle">
            {rows.map((row) => (
              <CorrelationRow
                key={row.finding.id}
                row={row}
                onExpand={() => setSelectedBreakdown(row)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail overlay */}
      {selectedBreakdown && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setSelectedBreakdown(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg border border-border bg-surface-1 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h3 className="font-sans text-sm font-semibold text-text-primary">
                  {selectedBreakdown.finding.label}
                </h3>
                <p className="mt-0.5 font-mono text-[10px] text-text-tertiary">
                  {selectedBreakdown.finding.node_type}
                  {selectedBreakdown.finding.cvss_score != null && ` · CVSS ${selectedBreakdown.finding.cvss_score.toFixed(1)}`}
                </p>
              </div>
              <button
                onClick={() => setSelectedBreakdown(null)}
                className="text-text-tertiary hover:text-text-primary"
              >
                ✕
              </button>
            </div>

            {selectedBreakdown.targets.length > 0 && (
              <div className="mb-4">
                <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wide text-text-tertiary">
                  correlated targets ({selectedBreakdown.targets.length})
                </h4>
                <div className="space-y-1.5">
                  {selectedBreakdown.targets.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between rounded border border-border-subtle bg-surface-0 px-3 py-2"
                    >
                      <span className="font-mono text-xs text-text-primary">{t.label}</span>
                      <div className="flex gap-2">
                        {t.is_crown_jewel && (
                          <span className="rounded border border-severity-critical/30 bg-severity-critical/10 px-1.5 py-0.5 text-[9px] text-severity-critical">
                            crown jewel
                          </span>
                        )}
                        {t.is_entry_point && (
                          <span className="rounded border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[9px] text-accent">
                            entry point
                          </span>
                        )}
                        {t.data_classification && t.data_classification !== "none" && (
                          <span className="rounded border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[9px] text-warning">
                            {t.data_classification.toUpperCase()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <ScoreExplainer
              breakdown={selectedBreakdown.breakdown}
              cost={1 - selectedBreakdown.breakdown.ease_score}
            />
          </div>
        </div>
      )}
  </div>
  );
}

// ---- Row sub-component ----

function CorrelationRow({
  row,
  onExpand,
}: {
  row: {
    finding: GraphResponse["nodes"][0];
    targets: GraphResponse["nodes"][0][];
    breakdown: ScoreBreakdown;
    hasExtended: boolean;
  };
  onExpand: () => void;
}) {
  return (
    <button
      onClick={onExpand}
      className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-2"
    >
      {/* Severity color bar */}
      <span
        className="h-8 w-1 shrink-0 rounded-full"
        style={{
          backgroundColor: cvssColor(row.finding.cvss_score ?? 0),
        }}
      />

      {/* Finding label + type */}
      <div className="min-w-0 flex-1">
        <div className="truncate font-mono text-xs text-text-primary">{row.finding.label}</div>
        <div className="flex items-center gap-2">
          <span className="text-text-tertiary">{row.finding.node_type}</span>
          {row.targets.length > 0 && (
            <span className="text-text-tertiary">
              → {row.targets.map((t) => t.label).join(", ")}
            </span>
          )}
        </div>
      </div>

      {/* Target badges */}
      <div className="flex shrink-0 gap-1.5">
        {row.hasExtended && (
          <span className="rounded border border-accent/30 bg-accent/5 px-1.5 py-0.5 text-[9px] text-accent">
            extended
          </span>
        )}
        {row.targets.some((t) => t.is_crown_jewel) && (
          <span className="rounded border border-severity-critical/30 bg-severity-critical/10 px-1.5 py-0.5 text-[9px] text-severity-critical">
            crown jewel
          </span>
        )}
      </div>

      {/* Ease score */}
      <div className="shrink-0 text-right font-mono text-xs">
        <div className="tabular-nums text-text-primary">{(row.breakdown.ease_score * 100).toFixed(0)}%</div>
        {row.finding.cvss_score != null && (
          <div className="tabular-nums text-text-tertiary">
            CVSS {row.finding.cvss_score.toFixed(1)}
          </div>
        )}
      </div>
    </button>
  );
}

function cvssColor(score: number): string {
  if (score >= 9) return "#ef4444";
  if (score >= 7) return "#f97316";
  if (score >= 4) return "#eab308";
  if (score > 0) return "#22c55e";
  return "#6b7280";
}
