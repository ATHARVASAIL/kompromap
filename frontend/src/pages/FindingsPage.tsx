import { useEffect, useMemo, useState } from "react";
import { listNodesByType } from "../api/client";
import { NodeTypeBadge, SeverityBadge, StatusBadge } from "../components/Badge";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Skeleton from "../components/Skeleton";
import { SEVERITY_LABELS, SEVERITY_ORDER, severityFromCvss, type Severity } from "../styles/tokens";
import type { NodeDetail } from "../types/graph";

interface FindingsPageProps {
  onViewInGraph: (nodeId: string) => void;
}

type SortKey = "severity" | "title" | "cvss_score" | "status";
type SortDir = "asc" | "desc";

interface FindingRow {
  id: string;
  title: string;
  cwe: string | null;
  owasp_category: string | null;
  cvss_score: number | null;
  exploit_public: boolean;
  auth_required: boolean;
  status: "open" | "fixed" | "accepted-risk";
  severity: Severity;
}

function toRow(n: NodeDetail): FindingRow {
  const cvss = (n.cvss_score as number | null) ?? null;
  return {
    id: n.id,
    title: (n.title as string) ?? "Untitled finding",
    cwe: (n.cwe as string | null) ?? null,
    owasp_category: (n.owasp_category as string | null) ?? null,
    cvss_score: cvss,
    exploit_public: Boolean(n.exploit_public),
    auth_required: Boolean(n.auth_required),
    status: (n.status as FindingRow["status"]) ?? "open",
    severity: severityFromCvss(cvss),
  };
}

export default function FindingsPage({ onViewInGraph }: FindingsPageProps) {
  const [rows, setRows] = useState<FindingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [statusFilter, setStatusFilter] = useState<FindingRow["status"] | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("severity");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [dense, setDense] = useState(false);

  function load() {
    setError(null);
    listNodesByType("finding")
      .then((data) => setRows(data.map(toRow)))
      .catch((e) => setError(String(e)));
  }

  useEffect(load, []);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = search.trim().toLowerCase();
    let result = rows.filter((r) => {
      if (q && !r.title.toLowerCase().includes(q) && !(r.cwe ?? "").toLowerCase().includes(q)) return false;
      if (severityFilter !== "all" && r.severity !== severityFilter) return false;
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      return true;
    });

    const severityRank = (s: Severity) => SEVERITY_ORDER.indexOf(s);
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "severity") cmp = severityRank(a.severity) - severityRank(b.severity);
      else if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "cvss_score") cmp = (a.cvss_score ?? -1) - (b.cvss_score ?? -1);
      else if (sortKey === "status") cmp = a.status.localeCompare(b.status);
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [rows, search, severityFilter, statusFilter, sortKey, sortDir]);

  const activeFilterChips: { label: string; onRemove: () => void }[] = [];
  if (severityFilter !== "all") {
    activeFilterChips.push({
      label: `Severity: ${SEVERITY_LABELS[severityFilter]}`,
      onRemove: () => setSeverityFilter("all"),
    });
  }
  if (statusFilter !== "all") {
    activeFilterChips.push({ label: `Status: ${statusFilter}`, onRemove: () => setStatusFilter("all") });
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border bg-surface-1 px-4 py-2.5">
        <h1 className="font-sans text-sm font-medium text-text-primary">Findings</h1>
        <span className="font-mono text-xs text-text-tertiary">{filtered.length}</span>

        <input
          data-shortcut-search
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="search title or CWE…"
          className="ml-2 w-56 rounded border border-border bg-surface-0 px-2 py-1 font-mono text-xs text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
        />

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
          className="rounded border border-border bg-surface-0 px-2 py-1 font-mono text-xs text-text-secondary focus:border-accent/60 focus:outline-none"
        >
          <option value="all">all severities</option>
          {SEVERITY_ORDER.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_LABELS[s]}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as FindingRow["status"] | "all")}
          className="rounded border border-border bg-surface-0 px-2 py-1 font-mono text-xs text-text-secondary focus:border-accent/60 focus:outline-none"
        >
          <option value="all">all statuses</option>
          <option value="open">open</option>
          <option value="fixed">fixed</option>
          <option value="accepted-risk">accepted-risk</option>
        </select>

        <label className="ml-auto flex items-center gap-1.5 font-mono text-xs text-text-tertiary">
          <input type="checkbox" checked={dense} onChange={(e) => setDense(e.target.checked)} className="accent-accent" />
          dense
        </label>
      </div>

      {activeFilterChips.length > 0 && (
        <div className="flex gap-2 border-b border-border bg-surface-1/50 px-4 py-1.5 font-mono text-[11px]">
          {activeFilterChips.map((chip) => (
            <button
              key={chip.label}
              onClick={chip.onRemove}
              className="flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-accent hover:bg-accent/20"
            >
              {chip.label}
              <span aria-hidden>✕</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {error && <ErrorBanner message={error} className="m-4" />}
        {!rows && !error && (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        )}
        {rows && rows.length === 0 && (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState message="No findings yet — findings created manually or via import will show up here." />
          </div>
        )}
        {rows && rows.length > 0 && (
          <table className="w-full border-collapse font-mono text-xs">
            <thead className="sticky top-0 z-10 bg-surface-1 text-text-tertiary shadow-[0_1px_0_0_rgb(var(--border-subtle))]">
              <tr>
                <SortableHeader label="Severity" active={sortKey === "severity"} dir={sortDir} onClick={() => toggleSort("severity")} />
                <SortableHeader label="Title" active={sortKey === "title"} dir={sortDir} onClick={() => toggleSort("title")} />
                <th className="px-3 py-2 text-left font-normal">CWE</th>
                <SortableHeader label="CVSS" active={sortKey === "cvss_score"} dir={sortDir} onClick={() => toggleSort("cvss_score")} />
                <SortableHeader label="Status" active={sortKey === "status"} dir={sortDir} onClick={() => toggleSort("status")} />
                <th className="px-3 py-2 text-left font-normal">Type</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr
                  key={row.id}
                  onClick={() => onViewInGraph(row.id)}
                  style={{ animationDelay: `${Math.min(i, 20) * 25}ms` }}
                  className="group animate-fade-in cursor-pointer border-t border-border-subtle transition-colors duration-150 hover:bg-surface-2"
                >
                  <td className={dense ? "px-3 py-1" : "px-3 py-2"}>
                    <SeverityBadge severity={row.severity} />
                  </td>
                  <td className={`${dense ? "px-3 py-1" : "px-3 py-2"} text-text-primary`}>{row.title}</td>
                  <td className={`${dense ? "px-3 py-1" : "px-3 py-2"} text-text-secondary`}>{row.cwe ?? "—"}</td>
                  <td className={`${dense ? "px-3 py-1" : "px-3 py-2"} text-text-secondary`}>
                    {row.cvss_score ?? "—"}
                  </td>
                  <td className={dense ? "px-3 py-1" : "px-3 py-2"}>
                    <StatusBadge status={row.status} />
                  </td>
                  <td className={dense ? "px-3 py-1" : "px-3 py-2"}>
                    <NodeTypeBadge nodeType="finding" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SortableHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}) {
  return (
    <th className="px-3 py-2 text-left font-normal">
      <button onClick={onClick} className={`flex items-center gap-1 hover:text-text-primary ${active ? "text-text-primary" : ""}`}>
        {label}
        {active && <span className="text-accent">{dir === "asc" ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}
