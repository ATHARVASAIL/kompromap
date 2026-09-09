import { colors, severityColor } from "../styles/tokens";
import Tooltip from "./Tooltip";
import type { ScoreBreakdown } from "../types/graph";

interface ScoreExplainerProps {
  breakdown: ScoreBreakdown;
  cost: number;
}

const TERM_META: Record<string, { label: string; color: string; hint: string }> = {
  cvss: {
    label: "CVSS",
    color: severityColor("critical"),
    hint: "Normalized CVSS score — how severe the finding is rated.",
  },
  exploit_public: {
    label: "public exploit",
    color: severityColor("high"),
    hint: "A public exploit exists, so this is weaponized rather than theoretical.",
  },
  unauthenticated: {
    label: "no auth",
    color: colors.accent,
    hint: "Reachable without credentials. Taken from the CVSS vector's Privileges Required when available, which is more precise than a yes/no auth flag.",
  },
  complexity: {
    label: "low complexity",
    color: severityColor("low"),
    hint: "How easy the exploit is to pull off. Derived from the CVSS vector's Attack Complexity, Privileges Required and User Interaction fields.",
  },
};

/**
 * Explains a single exploitation step's cost.
 *
 * Path ranking used to be an opaque number, which made "why is this chain
 * first?" unanswerable — the most obvious question a tester would ask of a
 * tool whose whole job is ranking chains. This shows each weighted term as
 * a proportional bar.
 *
 * The measured-vs-assumed badge matters: complexity comes from a real CVSS
 * vector when one exists and a configured fallback otherwise, and showing
 * both with the same confidence would overstate what we actually know.
 */
export default function ScoreExplainer({ breakdown, cost }: ScoreExplainerProps) {
  const entries = Object.entries(breakdown.contributions).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  return (
    <div className="rounded border border-border-subtle bg-surface-0/60 p-2.5 font-mono text-[11px]">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-text-tertiary">why this step costs {cost.toFixed(3)}</span>
        <Tooltip
          label={
            breakdown.complexity_measured
              ? "Complexity was read from this finding's CVSS vector."
              : "No CVSS vector on this finding, so the fallback complexity was assumed."
          }
        >
          <span
            className={`cursor-help rounded-full border px-1.5 py-0.5 text-[9px] uppercase tracking-wide ${
              breakdown.complexity_measured
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-border bg-surface-2 text-text-tertiary"
            }`}
          >
            {breakdown.complexity_measured ? "measured" : "assumed"}
          </span>
        </Tooltip>
      </div>

      {/* Proportional stacked bar — shows contribution share at a glance */}
      <div className="mb-2 flex h-1.5 overflow-hidden rounded-full bg-surface-2">
        {entries.map(([key, value]) => (
          <span
            key={key}
            style={{
              width: `${total > 0 ? (value / total) * 100 : 0}%`,
              backgroundColor: TERM_META[key]?.color ?? colors.text.tertiary,
            }}
            className="transition-all duration-500 ease-smooth"
          />
        ))}
      </div>

      <dl className="space-y-1">
        {entries.map(([key, value]) => {
          const meta = TERM_META[key];
          return (
            <div key={key} className="flex items-center gap-2">
              <span
                className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: meta?.color ?? colors.text.tertiary }}
              />
              <Tooltip label={meta?.hint ?? key}>
                <dt className="cursor-help text-text-secondary">{meta?.label ?? key}</dt>
              </Tooltip>
              <dd className="ml-auto tabular-nums text-text-primary">+{value.toFixed(3)}</dd>
            </div>
          );
        })}
      </dl>

      <div className="mt-2 flex items-center justify-between border-t border-border-subtle pt-2 text-text-tertiary">
        <span>ease score</span>
        <span className="tabular-nums text-text-primary">{breakdown.ease_score.toFixed(3)}</span>
      </div>
    </div>
  );
}
