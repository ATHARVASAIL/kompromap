import { useState } from "react";
import { generateEngagementReport, type ReportFormat } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Tooltip from "../components/Tooltip";
import { useToast } from "../components/toastContext";
import { SEVERITY_LABELS, SEVERITY_ORDER, severityColor } from "../styles/tokens";

interface ReportPageProps {
  engagementId: string;
  engagementName: string;
}

interface ReportSummary {
  total_findings: number;
  severity_counts: Record<string, number>;
  chain_count: number;
  easiest_chain_cost: number | null;
  findings_on_a_chain: number;
  entry_point_count: number;
  crown_jewel_count: number;
  total_nodes: number;
  findings_with_measured_complexity: number;
}

interface ReportData {
  summary: ReportSummary;
  caveats: string[];
  remediation: { rank: number; title: string; severity: string; breaks_chain: boolean; rationale: string[] }[];
  chains: { rank: number; entry_point: string; crown_jewel: string; total_cost: number }[];
}

const FORMATS: { id: ReportFormat; label: string; hint: string; ext: string; mime: string }[] = [
  {
    id: "html",
    label: "HTML",
    hint: "Self-contained page — opens anywhere and prints straight to PDF.",
    ext: "html",
    mime: "text/html",
  },
  {
    id: "markdown",
    label: "Markdown",
    hint: "Paste into an existing report template.",
    ext: "md",
    mime: "text/markdown",
  },
  {
    id: "json",
    label: "JSON",
    hint: "Structured data for further processing or a custom template.",
    ext: "json",
    mime: "application/json",
  },
];

function download(filename: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Report generation.
 *
 * The preview deliberately shows the *summary and caveats* rather than the
 * whole document: those are the two things worth checking before you hand
 * it to a client — the numbers, and what the report admits it doesn't
 * know. The full text goes to a file.
 */
export default function ReportPage({ engagementId, engagementName }: ReportPageProps) {
  const { toast } = useToast();
  const [preview, setPreview] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<ReportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeNarratives, setIncludeNarratives] = useState(false);

  async function loadPreview() {
    setLoading(true);
    setError(null);
    try {
      const res = await generateEngagementReport("json", { engagementId, includeNarratives });
      setPreview(res.data as unknown as ReportData);
      toast("Report generated");
    } catch (e) {
      setError(String(e));
      toast("Couldn't generate report", "error");
    } finally {
      setLoading(false);
    }
  }

  async function exportAs(fmt: (typeof FORMATS)[number]) {
    setExporting(fmt.id);
    setError(null);
    try {
      const res = await generateEngagementReport(fmt.id, { engagementId, includeNarratives });
      const body =
        fmt.id === "json" ? JSON.stringify(res.data, null, 2) : (res.content ?? "");
      const stem = engagementName.replace(/[^\w-]+/g, "_").toLowerCase();
      const date = new Date().toISOString().slice(0, 10);
      download(`kompromap-report-${stem}-${date}.${fmt.ext}`, body, fmt.mime);
      toast(`Exported as .${fmt.ext}`);
    } catch (e) {
      setError(String(e));
      toast("Export failed", "error");
    } finally {
      setExporting(null);
    }
  }

  const s = preview?.summary;
  const totalSeverity = s ? Object.values(s.severity_counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-1 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-base font-medium text-text-primary">Report</h1>
          <p className="mt-1 max-w-xl font-sans text-xs leading-relaxed text-text-tertiary">
            Assembles the whole engagement into a deliverable — executive summary, every
            finding, every attack chain with its scoring rationale, prioritised remediation,
            and the report's own caveats.
          </p>
        </div>
        <button
          onClick={loadPreview}
          disabled={loading}
          className="flex shrink-0 items-center gap-2 rounded border border-accent/60 bg-accent/10 px-3.5 py-1.5 font-mono text-xs text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
        >
          {loading && <Spinner />}
          {loading ? "generating…" : preview ? "regenerate" : "generate report"}
        </button>
      </div>

      <label className="mt-3 flex w-fit items-center gap-2 font-mono text-xs text-text-tertiary">
        <input
          type="checkbox"
          checked={includeNarratives}
          onChange={(e) => setIncludeNarratives(e.target.checked)}
          className="accent-accent"
        />
        include written narratives per chain
        <Tooltip label="Generates a prose paragraph describing each chain. Slower, and uses the Anthropic API if a key is configured — falls back to a template otherwise.">
          <span className="cursor-help text-text-disabled">ⓘ</span>
        </Tooltip>
      </label>

      {error && <ErrorBanner message={error} className="mt-4" />}

      {!preview && !loading && !error && (
        <div className="mt-8">
          <EmptyState message="Generate a report to preview its summary and caveats before exporting." />
        </div>
      )}

      {s && (
        <>
          <div className="mt-6 grid grid-cols-4 gap-3">
            <Stat label="Findings" value={s.total_findings} />
            <Stat
              label="Attack chains"
              value={s.chain_count}
              accent={s.chain_count ? "text-severity-critical" : undefined}
            />
            <Stat label="On a chain" value={s.findings_on_a_chain} accent="text-severity-high" />
            <Stat label="Mapped nodes" value={s.total_nodes} />
          </div>

          <div className="mt-4 rounded-lg border border-border bg-surface-1 bg-surface-sheen p-4 shadow-card">
            <h2 className="mb-3 font-sans text-xs font-medium uppercase tracking-wide text-text-tertiary">
              Severity distribution
            </h2>
            <div className="mb-3 flex h-2 overflow-hidden rounded-full bg-surface-2">
              {SEVERITY_ORDER.map((sev) => {
                const n = s.severity_counts[SEVERITY_LABELS[sev]] ?? 0;
                if (!n || !totalSeverity) return null;
                return (
                  <span
                    key={sev}
                    style={{
                      width: `${(n / totalSeverity) * 100}%`,
                      backgroundColor: severityColor(sev),
                    }}
                    className="transition-all duration-500 ease-smooth"
                  />
                );
              })}
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1 font-mono text-xs">
              {SEVERITY_ORDER.map((sev) => (
                <span key={sev} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: severityColor(sev) }}
                  />
                  <span className="text-text-tertiary">{SEVERITY_LABELS[sev]}</span>
                  <span className="tabular-nums text-text-primary">
                    {s.severity_counts[SEVERITY_LABELS[sev]] ?? 0}
                  </span>
                </span>
              ))}
            </div>
          </div>

          {preview.remediation.length > 0 && (
            <div className="mt-4 rounded-lg border border-border bg-surface-1 bg-surface-sheen p-4 shadow-card">
              <h2 className="mb-1 font-sans text-xs font-medium uppercase tracking-wide text-text-tertiary">
                Top remediation priorities
              </h2>
              <p className="mb-3 font-sans text-[11px] text-text-tertiary">
                Ranked by chain impact, not raw severity — a medium finding on the cheapest
                path outranks an unreachable critical.
              </p>
              <ol className="space-y-1.5 font-mono text-xs">
                {preview.remediation.slice(0, 5).map((r) => (
                  <li key={r.rank} className="flex items-baseline gap-2">
                    <span className="w-4 shrink-0 tabular-nums text-text-tertiary">{r.rank}</span>
                    <span className="truncate text-text-primary">{r.title}</span>
                    {r.breaks_chain && (
                      <span className="shrink-0 rounded-full border border-severity-critical/40 bg-severity-critical/10 px-1.5 text-[10px] text-severity-critical">
                        breaks a chain
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {preview.caveats.length > 0 && (
            <div className="mt-4 rounded-lg border border-severity-medium/30 bg-severity-medium/5 p-4">
              <h2 className="mb-2 font-sans text-xs font-medium uppercase tracking-wide text-severity-medium">
                What this report does not know
              </h2>
              <ul className="space-y-1.5 font-sans text-xs leading-relaxed text-text-secondary">
                {preview.caveats.map((c) => (
                  <li key={c} className="flex gap-2">
                    <span className="shrink-0 text-severity-medium">·</span>
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-6">
            <h2 className="mb-2 font-sans text-xs font-medium uppercase tracking-wide text-text-tertiary">
              Export
            </h2>
            <div className="flex gap-2">
              {FORMATS.map((f) => (
                <Tooltip key={f.id} label={f.hint}>
                  <button
                    onClick={() => exportAs(f)}
                    disabled={exporting !== null}
                    className="flex items-center gap-2 rounded border border-border px-3.5 py-2 font-mono text-xs text-text-secondary transition-colors hover:border-accent/60 hover:text-accent disabled:opacity-40"
                  >
                    {exporting === f.id && <Spinner />}
                    .{f.ext}
                  </button>
                </Tooltip>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 bg-surface-sheen px-4 py-3 shadow-card">
      <div className="font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
        {label}
      </div>
      <div className={`mt-1 font-sans text-2xl font-semibold tabular-nums ${accent ?? "text-text-primary"}`}>
        {value}
      </div>
    </div>
  );
}
