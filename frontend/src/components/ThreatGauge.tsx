import { useCountUp } from "../hooks/useCountUp";
import { colors, severityColor, type Severity } from "../styles/tokens";

interface ThreatGaugeProps {
  /** Lowest total_cost across all discovered paths, or null if none. */
  bestPathCost: number | null;
  pathCount: number;
  crownJewelCount: number;
  entryPointCount: number;
}

/**
 * The one question this whole tool exists to answer: how easily does an
 * unauthenticated attacker reach something that matters?
 *
 * Path cost is 1 - ease_score summed across the chain (see
 * backend/app/services/scoring.py), so *lower cost = easier attack*. This
 * inverts that into an exposure score where higher = worse, because "92
 * exposure" reads correctly to a human in a way "0.08 cost" does not.
 *
 * The arc is deliberately the only large graphic on the dashboard —
 * everything else there is quiet by comparison.
 */

const RADIUS = 62;
const STROKE = 10;
// 270° sweep (leaves a gap at the bottom) — a full ring reads as a loading
// spinner, an open arc reads as a gauge.
const SWEEP = 0.75;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const ARC_LENGTH = CIRCUMFERENCE * SWEEP;

function exposureFromCost(cost: number | null): number {
  if (cost === null) return 0;
  // Costs in practice land roughly in 0–3. Clamp and invert so a
  // near-zero cost (trivial chain) maps to ~100.
  const normalized = Math.min(Math.max(cost, 0), 3) / 3;
  return Math.round((1 - normalized) * 100);
}

function bandFor(exposure: number): { severity: Severity; label: string; note: string } {
  if (exposure >= 80)
    return {
      severity: "critical",
      label: "Critical exposure",
      note: "A crown jewel is reachable through a chain that needs little effort.",
    };
  if (exposure >= 60)
    return {
      severity: "high",
      label: "High exposure",
      note: "A workable path exists with moderate effort.",
    };
  if (exposure >= 35)
    return {
      severity: "medium",
      label: "Moderate exposure",
      note: "Paths exist but each step costs the attacker something.",
    };
  return {
    severity: "low",
    label: "Limited exposure",
    note: "Reaching a crown jewel would take significant work.",
  };
}

export default function ThreatGauge({
  bestPathCost,
  pathCount,
  crownJewelCount,
  entryPointCount,
}: ThreatGaugeProps) {
  const hasPath = bestPathCost !== null && pathCount > 0;
  const exposure = hasPath ? exposureFromCost(bestPathCost) : 0;
  const animated = useCountUp(exposure, 900);
  const band = bandFor(exposure);
  const color = hasPath ? severityColor(band.severity) : colors.text.tertiary;

  const offset = ARC_LENGTH - (ARC_LENGTH * exposure) / 100;

  return (
    <div className="flex items-center gap-6 rounded-lg border border-border bg-surface-1 bg-surface-sheen p-5 shadow-card">
      <div className="relative shrink-0" style={{ width: 150, height: 150 }}>
        <svg width="150" height="150" viewBox="0 0 150 150" className="-rotate-[225deg]">
          {/* Track */}
          <circle
            cx="75"
            cy="75"
            r={RADIUS}
            fill="none"
            stroke={colors.surface[3]}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${ARC_LENGTH} ${CIRCUMFERENCE}`}
          />
          {/* Value */}
          <circle
            cx="75"
            cy="75"
            r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={`${ARC_LENGTH} ${CIRCUMFERENCE}`}
            className="animate-draw-arc"
            style={
              {
                "--arc-length": `${ARC_LENGTH}`,
                "--arc-offset": `${offset}`,
                strokeDashoffset: offset,
                filter: hasPath ? `drop-shadow(0 0 6px ${color}66)` : undefined,
              } as React.CSSProperties
            }
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            data-testid="exposure-value"
            className="font-sans text-4xl font-semibold tabular-nums leading-none"
            style={{ color }}
          >
            {hasPath ? animated : "—"}
          </span>
          <span className="mt-1 font-mono text-[10px] uppercase tracking-wider text-text-tertiary">
            exposure
          </span>
        </div>
      </div>

      <div className="min-w-0">
        <h2 className="font-sans text-sm font-medium" style={{ color }}>
          {hasPath ? band.label : "No reachable path"}
        </h2>
        <p className="mt-1 max-w-xs font-sans text-xs leading-relaxed text-text-secondary">
          {hasPath
            ? band.note
            : entryPointCount === 0 || crownJewelCount === 0
              ? "Tag at least one entry point and one crown jewel to measure exposure."
              : "No chain connects an entry point to a crown jewel yet."}
        </p>

        <dl className="mt-4 flex gap-6 font-mono text-xs">
          <div>
            <dt className="text-text-tertiary">paths</dt>
            <dd className="mt-0.5 tabular-nums text-text-primary">{pathCount}</dd>
          </div>
          <div>
            <dt className="text-text-tertiary">entry points</dt>
            <dd className="mt-0.5 tabular-nums text-accent">{entryPointCount}</dd>
          </div>
          <div>
            <dt className="text-text-tertiary">crown jewels</dt>
            <dd className="mt-0.5 tabular-nums text-severity-critical">{crownJewelCount}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
