import { useState } from "react";
import Tooltip from "./Tooltip";
import { DEFAULT_WEIGHTS } from "./scoringDefaults";
import type { ScoringWeights } from "../types/graph";

interface ScoringWeightsPanelProps {
  weights: ScoringWeights;
  onChange: (w: ScoringWeights) => void;
  onApply: () => void;
  busy?: boolean;
}

/**
 * Per-engagement risk tuning.
 *
 * The spec called this out explicitly — "risk appetite differs bank vs.
 * ecommerce client" — and the API has supported it since Phase 4, but
 * there was never a UI, so in practice everyone got the defaults. A bank
 * might weight `auth_required` far higher than a marketing site would.
 *
 * Weights don't need to sum to 1: Dijkstra only cares about relative
 * ordering between edges. The normalized share is shown anyway, because
 * "0.4" means nothing on its own but "44% of the score" does.
 */

const TERMS: {
  key: keyof Omit<ScoringWeights, "default_complexity">;
  label: string;
  hint: string;
}[] = [
  {
    key: "cvss",
    label: "CVSS severity",
    hint: "How much raw CVSS score drives ease. Lower this if you care more about exploitability than severity.",
  },
  {
    key: "exploit_public",
    label: "Public exploit",
    hint: "Weight given to a public exploit existing — the difference between theoretical and weaponized.",
  },
  {
    key: "auth_required",
    label: "No auth needed",
    hint: "Weight for unauthenticated reachability. Raise this if pre-auth exposure is your main concern.",
  },
  {
    key: "complexity",
    label: "Attack complexity",
    hint: "Weight for how hard the exploit is. Derived from the CVSS vector when available, otherwise the fallback below.",
  },
];

export default function ScoringWeightsPanel({
  weights,
  onChange,
  onApply,
  busy,
}: ScoringWeightsPanelProps) {
  const [open, setOpen] = useState(false);

  const total =
    weights.cvss + weights.exploit_public + weights.auth_required + weights.complexity;
  const isDefault = TERMS.every((t) => weights[t.key] === DEFAULT_WEIGHTS[t.key]) &&
    weights.default_complexity === DEFAULT_WEIGHTS.default_complexity;

  function set(key: keyof ScoringWeights, value: number) {
    onChange({ ...weights, [key]: value });
  }

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left font-mono text-xs text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <span
            className={`inline-block transition-transform duration-200 ${open ? "rotate-90" : ""}`}
            aria-hidden
          >
            ▸
          </span>
          scoring weights
        </span>
        {!isDefault && (
          <span className="rounded-full border border-severity-medium/40 bg-severity-medium/10 px-1.5 py-0.5 text-[10px] text-severity-medium">
            tuned
          </span>
        )}
      </button>

      {open && (
        <div className="animate-fade-in space-y-3 px-4 pb-4 font-mono text-xs">
          <p className="text-[11px] leading-relaxed text-text-tertiary">
            Tune how the model ranks chains for this engagement. Values are relative — only
            their proportions matter.
          </p>

          {TERMS.map((term) => {
            const value = weights[term.key];
            const share = total > 0 ? Math.round((value / total) * 100) : 0;
            return (
              <div key={term.key}>
                <div className="mb-1 flex items-center justify-between">
                  <Tooltip label={term.hint}>
                    <label htmlFor={term.key} className="cursor-help text-text-secondary underline decoration-dotted decoration-text-tertiary underline-offset-2">
                      {term.label}
                    </label>
                  </Tooltip>
                  <span className="tabular-nums text-text-tertiary">
                    {value.toFixed(2)}
                    <span className="ml-1.5 text-accent">{share}%</span>
                  </span>
                </div>
                <input
                  id={term.key}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={value}
                  onChange={(e) => set(term.key, Number(e.target.value))}
                  className="w-full accent-accent"
                />
              </div>
            );
          })}

          <div className="border-t border-border-subtle pt-3">
            <div className="mb-1 flex items-center justify-between">
              <Tooltip label="Used only for findings with no CVSS vector to derive real complexity from. 0 = assume trivial, 1 = assume very hard.">
                <label
                  htmlFor="default_complexity"
                  className="cursor-help text-text-secondary underline decoration-dotted decoration-text-tertiary underline-offset-2"
                >
                  fallback complexity
                </label>
              </Tooltip>
              <span className="tabular-nums text-text-tertiary">
                {weights.default_complexity.toFixed(2)}
              </span>
            </div>
            <input
              id="default_complexity"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weights.default_complexity}
              onChange={(e) => set("default_complexity", Number(e.target.value))}
              className="w-full accent-accent"
            />
            <p className="mt-1 text-[10px] leading-relaxed text-text-tertiary">
              Only applies where no CVSS vector is available.
            </p>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={() => onChange(DEFAULT_WEIGHTS)}
              disabled={isDefault}
              className="flex-1 rounded border border-border py-1.5 text-text-secondary transition-colors hover:border-border-strong disabled:opacity-40"
            >
              reset
            </button>
            <button
              onClick={onApply}
              disabled={busy}
              className="flex-1 rounded border border-accent/60 bg-accent/10 py-1.5 text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
            >
              {busy ? "recomputing…" : "apply"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
