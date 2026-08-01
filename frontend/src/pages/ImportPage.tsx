import { useState } from "react";
import { ingestFile } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import { useToast } from "../components/ToastProvider";

interface ImportPageProps {
  engagementId: string;
  onImported: () => void;
}

type Tool = "nmap" | "nuclei" | "amass" | "burp";

const TOOLS: { value: Tool; label: string; accepts: string; hint: string }[] = [
  { value: "nmap", label: "Nmap", accepts: ".xml", hint: "XML output (nmap -oX)" },
  { value: "nuclei", label: "Nuclei", accepts: ".json,.jsonl", hint: "JSON or JSON Lines output" },
  {
    value: "amass",
    label: "Amass / Subfinder",
    accepts: ".txt,.json,.jsonl",
    hint: "Plain text or JSON subdomain list",
  },
  { value: "burp", label: "Burp Suite / ZAP", accepts: ".xml", hint: "XML issue/alert export" },
];

interface ImportSummary {
  source_tool: string;
  assets_created: number;
  assets_reused: number;
  services_created: number;
  endpoints_created: number;
  findings_created: number;
  edges_created: number;
  warnings: string[];
}

export default function ImportPage({ engagementId, onImported }: ImportPageProps) {
  const { toast } = useToast();
  const [tool, setTool] = useState<Tool>("nmap");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [history, setHistory] = useState<{ tool: Tool; fileName: string; summary: ImportSummary }[]>([]);

  const activeTool = TOOLS.find((t) => t.value === tool)!;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const result = (await ingestFile(tool, file, engagementId)) as ImportSummary;
      setSummary(result);
      setHistory((h) => [{ tool, fileName: file.name, summary: result }, ...h]);
      onImported();
      const total = result.assets_created + result.services_created + result.endpoints_created + result.findings_created;
      toast(`Import complete — ${total} node${total === 1 ? "" : "s"} created`, "success");
    } catch (err) {
      setError(String(err));
      toast("Import failed", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <h1 className="mb-1 font-sans text-base font-medium text-text-primary">Import scan data</h1>
      <p className="mb-6 font-sans text-xs text-text-tertiary">
        Upload recon or scan output and it's parsed straight into the graph — assets, services,
        endpoints, and findings get created and linked automatically.
      </p>

      <div className="grid grid-cols-[minmax(0,22rem)_1fr] gap-6">
        <form onSubmit={handleSubmit} className="space-y-4 font-mono text-xs">
          <div>
            <label className="mb-1.5 block text-text-tertiary">tool</label>
            <div className="grid grid-cols-2 gap-2">
              {TOOLS.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => {
                    setTool(t.value);
                    setFile(null);
                    setSummary(null);
                  }}
                  className={`rounded border px-2.5 py-2 text-left transition-colors ${
                    tool === t.value
                      ? "border-accent/60 bg-accent/10 text-accent"
                      : "border-border text-text-secondary hover:border-border-strong"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-text-tertiary">{activeTool.hint}</p>
          </div>

          <div>
            <label className="mb-1.5 block text-text-tertiary">file</label>
            <input
              type="file"
              accept={activeTool.accepts}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-secondary file:mr-2 file:rounded file:border-0 file:bg-surface-2 file:px-2 file:py-1 file:text-text-secondary"
            />
          </div>

          {error && <ErrorBanner message={error} />}

          <button
            type="submit"
            disabled={!file || loading}
            className="flex w-full items-center justify-center gap-2 rounded border border-accent/60 bg-accent/10 py-1.5 text-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading && <Spinner />}
            {loading ? "importing…" : "import"}
          </button>

          {summary && (
            <div className="rounded border border-accent/30 bg-accent/5 px-3 py-2">
              <div className="mb-1.5 text-accent">Import complete</div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                <SummaryRow label="assets" value={summary.assets_created} />
                <SummaryRow label="services" value={summary.services_created} />
                <SummaryRow label="endpoints" value={summary.endpoints_created} />
                <SummaryRow label="findings" value={summary.findings_created} />
                <SummaryRow label="edges" value={summary.edges_created} />
              </dl>
              {summary.warnings.length > 0 && (
                <p className="mt-2 text-[11px] text-severity-medium">
                  {summary.warnings.length} warning{summary.warnings.length === 1 ? "" : "s"}
                </p>
              )}
            </div>
          )}
        </form>

        <div>
          <h2 className="mb-2 font-sans text-xs font-medium text-text-secondary">This session</h2>
          {history.length === 0 ? (
            <EmptyState message="No imports yet this session." />
          ) : (
            <div className="space-y-2">
              {history.map((h, i) => (
                <div
                  key={i}
                  className={`rounded border border-border bg-surface-1 px-3 py-2 font-mono text-xs ${i === 0 ? "animate-fade-in-scale" : ""}`}
                >
                  <div className="flex items-center justify-between text-text-secondary">
                    <span>
                      {TOOLS.find((t) => t.value === h.tool)?.label} · {h.fileName}
                    </span>
                  </div>
                  <div className="mt-1 text-text-tertiary">
                    {h.summary.assets_created} assets · {h.summary.services_created} services ·{" "}
                    {h.summary.endpoints_created} endpoints · {h.summary.findings_created} findings ·{" "}
                    {h.summary.edges_created} edges
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: number }) {
  return (
    <>
      <dt className="text-text-tertiary">{label}</dt>
      <dd className="text-text-primary">{value}</dd>
    </>
  );
}
