import { useEffect, useMemo, useState } from "react";
import { getCorrelation, type RiskFactorResponse } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";

function barColor(risk: number): string {
  if (risk >= 7) return "#F2454E";
  if (risk >= 4) return "#F5883A";
  if (risk >= 2) return "#F0C93A";
  return "#4C8DF0";
}

export default function CorrelationPage() {
  const [data, setData] = useState<{ asset_risks: RiskFactorResponse[]; total_findings: number; assets_exposed: number; average_risk: number; cwe_groups: Record<string | null, Array<Record<string, unknown>>> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getCorrelation()
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const sorted = useMemo(() => data?.asset_risks ? [...data.asset_risks].sort((a, b) => b.extended_risk - a.extended_risk) : [], [data]);

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return <ErrorBanner message={error} className="m-4" />;
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="font-mono text-sm text-text-tertiary">No correlation data available.</div>
      </div>
    );
  }

  const maxRisk = Math.max(...sorted.map((r) => r.extended_risk), 1);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-border bg-surface-1 px-4 py-3">
        <h1 className="font-sans text-sm font-medium text-text-primary">Correlation & Extended Risk</h1>
        <p className="font-mono text-xs text-text-tertiary">Asset criticality × data sensitivity × exposure</p>
        <div className="ml-auto flex gap-4 font-mono text-xs text-text-secondary">
          <span>Findings: {data.total_findings}</span>
          <span>Assets exposed: {data.assets_exposed}</span>
          <span>Avg risk: {data.average_risk.toFixed(2)}</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center p-8">
            <div className="font-mono text-sm text-text-tertiary">No assets with extended risk data yet.</div>
          </div>
        ) : (
          <table className="w-full border-collapse font-mono text-xs">
            <thead className="sticky top-0 z-10 bg-surface-1 text-text-tertiary shadow-[0_1px_0_0_rgb(var(--border-subtle))]">
              <tr>
                <th className="px-3 py-2 text-left font-normal">Asset</th>
                <th className="px-3 py-2 text-left font-normal">Type</th>
                <th className="px-3 py-2 text-right font-normal">Criticality</th>
                <th className="px-3 py-2 text-right font-normal">Sensitivity</th>
                <th className="px-3 py-2 text-right font-normal">Exposure</th>
                <th className="px-3 py-2 text-right font-normal">Base CVSS</th>
                <th className="px-3 py-2 text-left font-normal">Extended Risk</th>
                <th className="px-3 py-2 text-center font-normal">Findings</th>
                <th className="px-3 py-2 text-center font-normal">Paths in</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r, i) => (
                <tr
                  key={r.asset_id}
                  style={{ animationDelay: `${Math.min(i, 30) * 20}ms` }}
                  className="group animate-fade-in border-t border-border-subtle transition-colors duration-150 hover:bg-surface-2"
                >
                  <td className="px-3 py-2 text-text-primary">{r.name}</td>
                  <td className="px-3 py-2 text-text-secondary capitalize">{r.type.replace("_", " ")}</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{(r.criticality * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{(r.sensitivity * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{(r.exposure * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{r.base_cvss.toFixed(1)}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-1">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${(r.extended_risk / maxRisk) * 100}%`, backgroundColor: barColor(r.extended_risk) }}
                        />
                      </div>
                      <span className="font-mono text-[11px]" style={{ color: barColor(r.extended_risk) }}>
                        {r.extended_risk.toFixed(2)}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-center text-text-secondary">
                    {r.finding_count}
                    {r.critical_findings > 0 && <span className="ml-1 text-warning">({r.critical_findings} crit)</span>}
                  </td>
                  <td className="px-3 py-2 text-center text-text-secondary">{r.attack_paths_in}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
