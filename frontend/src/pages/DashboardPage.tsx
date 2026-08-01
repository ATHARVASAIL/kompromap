import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDashboard, listNodesByType } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Skeleton from "../components/Skeleton";
import { NODE_TYPE_COLOR, NODE_TYPE_LABELS, type DashboardData, type NodeType } from "../types/graph";
import { SEVERITY_LABELS, SEVERITY_ORDER, severityColor, severityFromCvss } from "../styles/tokens";

interface DashboardPageProps {
  engagementId: string;
  onOpenSnapshots: () => void;
}

export default function DashboardPage({ engagementId, onOpenSnapshots }: DashboardPageProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [severityCounts, setSeverityCounts] = useState<{ name: string; count: number; color: string }[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setSeverityCounts(null);
    setError(null);

    getDashboard(engagementId)
      .then(setData)
      .catch((e) => setError(String(e)));

    listNodesByType("finding")
      .then((findings) => {
        const counts = Object.fromEntries(SEVERITY_ORDER.map((s) => [s, 0])) as Record<string, number>;
        for (const f of findings) {
          const severity = severityFromCvss((f.cvss_score as number | null) ?? null);
          counts[severity] += 1;
        }
        setSeverityCounts(
          SEVERITY_ORDER.map((s) => ({ name: SEVERITY_LABELS[s], count: counts[s], color: severityColor(s) })),
        );
      })
      .catch((e) => setError(String(e)));
  }, [engagementId]);

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-5 flex items-center justify-between">
        <h1 className="font-sans text-base font-medium text-text-primary">Dashboard</h1>
        <button
          onClick={onOpenSnapshots}
          className="rounded border border-border px-3 py-1.5 font-mono text-xs text-text-secondary hover:border-accent/60 hover:text-accent"
        >
          snapshots
        </button>
      </div>

      {error && <ErrorBanner message={error} className="mb-4" />}

      {!data && !error && (
        <div className="grid grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-md border border-border bg-surface-1 px-4 py-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="mt-2 h-6 w-10" />
            </div>
          ))}
        </div>
      )}

      {data && (
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="Total nodes" value={data.total_nodes} delay={0} />
          <StatCard label="Total edges" value={data.total_edges} delay={40} />
          <StatCard label="Entry points" value={data.entry_point_count} accent="text-accent" delay={80} />
          <StatCard label="Crown jewels" value={data.crown_jewel_count} accent="text-severity-critical" delay={120} />
        </div>
      )}

      <div className="mt-6 grid grid-cols-2 gap-4">
        <Card title="Findings by severity">
          {severityCounts ? (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severityCounts} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <XAxis type="number" allowDecimals={false} stroke="#5C6478" fontSize={11} fontFamily="'JetBrains Mono', monospace" />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="#5C6478"
                    fontSize={11}
                    fontFamily="'JetBrains Mono', monospace"
                    width={64}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#151A24",
                      border: "1px solid #2E3648",
                      borderRadius: 6,
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#E7EAF0" }}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  />
                  <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                    {severityCounts.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          )}
        </Card>

        <Card title="Nodes by type">
          {data ? (
            <div className="space-y-1.5">
              {Object.entries(data.node_counts_by_type).map(([type, count]) => (
                <div key={type} className="flex items-center gap-2 font-mono text-xs">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: NODE_TYPE_COLOR[type as NodeType] }} />
                  <span className="flex-1 text-text-secondary">{NODE_TYPE_LABELS[type as NodeType] ?? type}</span>
                  <span className="text-text-primary">{count}</span>
                </div>
              ))}
              {Object.keys(data.node_counts_by_type).length === 0 && (
                <p className="font-mono text-xs text-text-tertiary">No nodes yet.</p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card title="Attack paths">
          {data ? (
            <div className="font-mono text-xs">
              <p className="mb-3 text-text-secondary">
                paths to crown jewels: <span className="text-text-primary">{data.paths_to_crown_jewels_count}</span>
              </p>
              {data.highest_ease_chain ? (
                <div className="rounded border border-severity-medium/30 bg-severity-medium/5 px-3 py-2">
                  <div className="mb-1 text-severity-medium">highest-ease chain found</div>
                  <div className="flex items-center gap-1.5 text-text-primary">
                    <span>{data.highest_ease_chain.entry_point.label}</span>
                    <span className="text-text-tertiary">→</span>
                    <span>{data.highest_ease_chain.crown_jewel.label}</span>
                  </div>
                  <div className="mt-1 text-text-tertiary">
                    cost {data.highest_ease_chain.total_cost.toFixed(2)} · {data.highest_ease_chain.nodes.length} nodes
                  </div>
                </div>
              ) : (
                <p className="text-text-tertiary">
                  no reachable chain yet — tag an entry point and a crown jewel, then connect them
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  delay = 0,
}: {
  label: string;
  value: number;
  accent?: string;
  delay?: number;
}) {
  return (
    <div
      style={{ animationDelay: `${delay}ms` }}
      className="animate-fade-in rounded-md border border-border bg-surface-1 px-4 py-3"
    >
      <div className="font-mono text-[11px] text-text-tertiary">{label}</div>
      <div className={`mt-1 font-sans text-2xl font-semibold ${accent ?? "text-text-primary"}`}>{value}</div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface-1 p-4">
      <h2 className="mb-3 font-sans text-xs font-medium text-text-secondary">{title}</h2>
      {children}
    </div>
  );
}
