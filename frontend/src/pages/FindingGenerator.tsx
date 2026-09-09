import { useCallback, useEffect, useMemo, useState } from "react";
import {
  generateFindings,
  getFindingGenHealth,
  type GeneratedFinding,
  type FindingGenResponse,
} from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Tooltip from "../components/Tooltip";
import { colors, severityColor } from "../styles/tokens";

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

interface FindingGeneratorProps {
  onCreateFinding?: (data: Partial<GeneratedFinding>) => void;
}

export default function FindingGenerator({ onCreateFinding }: FindingGeneratorProps) {
  const [nodeId, setNodeId] = useState("");
  const [targetAssets, setTargetAssets] = useState("");
  const [extraContext, setExtraContext] = useState("");
  const [result, setResult] = useState<FindingGenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerReady, setProviderReady] = useState<boolean | null>(null);

  // Check provider on mount
  useEffect(() => {
    getFindingGenHealth()
      .then((r) => setProviderReady(r.configured))
      .catch(() => setProviderReady(false));
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!nodeId.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload: {
        node_id: string;
        target_assets?: string[];
        extra_context?: string;
      } = {
        node_id: nodeId.trim(),
      };
      const ta = targetAssets.split(",").map((s) => s.trim()).filter(Boolean);
      if (ta.length) payload.target_assets = ta;
      if (extraContext.trim()) payload.extra_context = extraContext.trim();
      const r = await generateFindings(payload);
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }, [nodeId, targetAssets, extraContext, loading]);

  const handleUseFinding = useCallback(
    (f: GeneratedFinding) => {
      onCreateFinding?.({
        title: f.title,
        description: f.description,
        severity: f.severity,
        cwe: f.cwe,
        owasp_category: f.owasp_category,
        cvss_score: f.cvss_score,
        cvss_vector: f.cvss_vector,
        exploit_public: f.exploit_public,
        auth_required: f.auth_required,
        evidence: f.evidence,
        tags: f.tags,
      });
    },
    [onCreateFinding],
  );

  if (providerReady === false) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <div className="text-lg font-semibold text-text-secondary">AI Provider Not Configured</div>
          <div className="mt-2 text-sm text-text-tertiary">
            Set the AI provider configuration in your environment variables.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      {/* Advisory banner */}
      <div
        className="rounded border border-accent/30 bg-accent/10 px-3 py-2 font-mono text-[11px] text-accent"
        role="note"
      >
        ⚠ AI-generated findings are advisory only. Review, edit, and submit via the manual finding
        form. No finding is written until you confirm.
      </div>

      {/* Input form */}
      <div className="space-y-3">
        <div>
          <label className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
            Node ID (asset / endpoint / service)
          </label>
          <input
            type="text"
            value={nodeId}
            onChange={(e) => setNodeId(e.target.value)}
            placeholder="UUID of the node to analyse"
            className="w-full rounded border border-border bg-surface-1 px-3 py-2 font-mono text-xs text-text-primary outline-none transition-colors focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
            Related assets (comma-separated, optional)
          </label>
          <input
            type="text"
            value={targetAssets}
            onChange={(e) => setTargetAssets(e.target.value)}
            placeholder="e.g. web-01, api-gateway"
            className="w-full rounded border border-border bg-surface-1 px-3 py-2 font-mono text-xs text-text-primary outline-none transition-colors focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
            Extra context (optional)
          </label>
          <textarea
            value={extraContext}
            onChange={(e) => setExtraContext(e.target.value)}
            rows={2}
            placeholder="Any additional context the AI should consider"
            className="w-full rounded border border-border bg-surface-1 px-3 py-2 font-mono text-xs text-text-primary outline-none transition-colors focus:border-accent"
          />
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading || !nodeId.trim()}
          className="w-full rounded bg-accent px-4 py-2.5 font-mono text-xs font-semibold text-bg transition-opacity disabled:opacity-50"
        >
          {loading ? "Generating…" : "Generate Findings"}
        </button>
      </div>

      {error && <ErrorBanner message={error} />}

      {loading && (
        <div className="flex items-center justify-center py-8">
          <Spinner />
        </div>
      )}

      {result && (
        <div className="space-y-3">
          {result.note && (
            <div className="font-mono text-[11px] text-text-tertiary">{result.note}</div>
          )}
          {result.assumptions.length > 0 && (
            <div className="font-mono text-[11px] text-text-tertiary">
              <span className="text-accent">Assumptions:</span> {result.assumptions.join(", ")}
            </div>
          )}
          {result.model && (
            <div className="font-mono text-[10px] text-text-disabled">
              Generated by {result.model}
            </div>
          )}

          {result.findings.length === 0 && (
            <div className="py-6 text-center font-mono text-xs text-text-tertiary">
              No findings generated — the context may be too limited.
            </div>
          )}

          {result.findings.map((f, i) => (
            <FindingCard key={i} finding={f} onUse={() => handleUseFinding(f)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Individual finding card ─────────────────────────────────────────────

function FindingCard({
  finding,
  onUse,
}: {
  finding: GeneratedFinding;
  onUse: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const sevColor =
    finding.severity === "critical"
      ? severityColor("critical")
      : finding.severity === "high"
        ? severityColor("high")
        : finding.severity === "medium"
          ? severityColor("medium")
          : finding.severity === "low"
            ? severityColor("low")
            : colors.text.tertiary;

  return (
    <div className="rounded border border-border bg-surface-1 transition-colors hover:border-accent/30">
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 p-3 text-left"
      >
        <span
          className="mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: sevColor }}
          title={finding.severity}
        />
        <div className="min-w-0 flex-1">
          <div className="font-mono text-xs font-semibold text-text-primary">{finding.title}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[10px] text-text-tertiary">
            <span style={{ color: sevColor }} className="uppercase">{finding.severity}</span>
            {finding.cwe && <span>{finding.cwe}</span>}
            {finding.cvss_score != null && <span>CVSS {finding.cvss_score.toFixed(1)}</span>}
            {finding.exploit_public && <span className="text-warning">Public exploit</span>}
          </div>
        </div>
        <span className="mt-1 shrink-0 text-text-disabled">{expanded ? "▾" : "▸"}</span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border px-3 pb-3 pt-2 space-y-2">
          <p className="text-xs leading-relaxed text-text-secondary">{finding.description}</p>

          {finding.remediation && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Remediation</span>
              <p className="mt-0.5 text-xs leading-relaxed text-text-secondary">{finding.remediation}</p>
            </div>
          )}

          {finding.affected_assets.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Affected</span>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {finding.affected_assets.map((a, i) => (
                  <span key={i} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">{a}</span>
                ))}
              </div>
            </div>
          )}

          {finding.evidence && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Evidence</span>
              <pre className="mt-0.5 max-h-32 overflow-y-auto rounded bg-bg/50 p-2 font-mono text-[10px] text-text-secondary whitespace-pre-wrap">{finding.evidence}</pre>
            </div>
          )}

          {finding.assumptions.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-accent">Assumptions</span>
              <ul className="mt-0.5 list-disc pl-4 text-[11px] text-text-secondary">
                {finding.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Action */}
          <div className="pt-2">
            <Tooltip label="Opens the manual finding form with this data pre-filled">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onUse();
                }}
                className="rounded bg-accent px-3 py-1.5 font-mono text-[11px] font-semibold text-bg transition-opacity hover:opacity-90"
              >
                Use as Finding
              </button>
            </Tooltip>
          </div>
        </div>
      )}
    </div>
  );
}
