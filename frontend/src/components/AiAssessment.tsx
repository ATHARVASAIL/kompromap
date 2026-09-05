import { useEffect, useState } from "react";
import {
  analyzeFinding,
  getFindingAssessment,
  getTriageStatus,
  type AITriageResult,
  type TriageAssessment,
} from "../api/client";
import ErrorBanner from "./ErrorBanner";
import Spinner from "./Spinner";
import Tooltip from "./Tooltip";
import { useToast } from "./toastContext";
import { colors, severityColor, type Severity } from "../styles/tokens";

interface AiAssessmentProps {
  findingId: string;
}

/**
 * AI triage, presented as an analyst would want it.
 *
 * Three deliberate choices, all of them about not overstating what this
 * is:
 *
 * 1. **"Assessment", never "verdict".** The AI has no network access and
 *    never touched the target. It read the same evidence you can see.
 * 2. **Evidence, assumptions and missing evidence are separate blocks.**
 *    Collapsing them into one paragraph is how a hedged answer starts
 *    reading like a confident one.
 * 3. **Recommended validation is labelled as not-yet-done.** These are
 *    steps *for you*, and the wording never implies a test was performed.
 *
 * There is also no button here that changes the finding. Confirming or
 * dismissing stays in the verification control, where a human does it.
 */

const ASSESSMENT_META: Record<
  TriageAssessment,
  { label: string; color: string; note: string }
> = {
  likely_valid: {
    label: "Likely valid",
    color: severityColor("high"),
    note: "The evidence appears to support this finding — verify before reporting.",
  },
  likely_false_positive: {
    label: "Likely false positive",
    color: colors.text.tertiary,
    note: "The evidence suggests this may not be real — confirm before dismissing it.",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    color: severityColor("medium"),
    note: "Not enough in the captured evidence to judge either way.",
  },
};

function Section({
  title,
  items,
  hint,
  ordered = false,
  tone,
}: {
  title: string;
  items: string[];
  hint?: string;
  ordered?: boolean;
  tone?: string;
}) {
  if (!items.length) return null;
  const List = ordered ? "ol" : "ul";
  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="font-mono text-[11px] uppercase tracking-wide" style={{ color: tone ?? colors.text.tertiary }}>
          {title}
        </span>
        {hint && (
          <Tooltip label={hint}>
            <span className="cursor-help text-[10px] text-text-disabled">ⓘ</span>
          </Tooltip>
        )}
      </div>
      <List
        className={`space-y-1 pl-4 text-xs leading-relaxed text-text-secondary ${
          ordered ? "list-decimal" : "list-disc"
        }`}
      >
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </List>
    </div>
  );
}

export default function AiAssessment({ findingId }: AiAssessmentProps) {
  const { toast } = useToast();
  const [assessment, setAssessment] = useState<AITriageResult | null>(null);
  const [meta, setMeta] = useState<{ model?: string | null; at?: string | null }>({});
  const [available, setAvailable] = useState<boolean | null>(null);
  const [providerReason, setProviderReason] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAssessment(null);
    setError(null);

    getTriageStatus()
      .then((s) => {
        if (cancelled) return;
        setAvailable(s.available);
        setProviderReason(s.reason ?? null);
      })
      .catch(() => !cancelled && setAvailable(false));

    getFindingAssessment(findingId)
      .then((r) => {
        if (cancelled) return;
        if (r.available && r.assessment) {
          setAssessment(r.assessment);
          setMeta({ model: r.model, at: r.analyzed_at });
        }
      })
      .catch(() => {
        /* no stored assessment is a normal state, not an error */
      });

    return () => {
      cancelled = true;
    };
  }, [findingId]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await analyzeFinding(findingId);
      if (r.available && r.assessment) {
        setAssessment(r.assessment);
        setMeta({ model: r.model, at: r.analyzed_at });
        toast("Assessment generated");
      } else {
        setError(r.error ?? "AI analysis is unavailable.");
      }
    } catch (e) {
      setError(String(e));
      toast("Analysis failed", "error");
    } finally {
      setRunning(false);
    }
  }

  if (available === false && !assessment) {
    return (
      <div className="border-t border-border pt-4">
        <span className="font-mono text-xs text-text-tertiary">ai assessment</span>
        <p className="mt-1.5 text-[11px] leading-relaxed text-text-disabled">
          {providerReason ?? "AI triage is not configured."}
        </p>
      </div>
    );
  }

  const m = assessment ? ASSESSMENT_META[assessment.assessment] : null;
  const lowConfidence = assessment ? assessment.confidence < 0.5 : false;

  return (
    <div className="border-t border-border pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-xs text-text-tertiary">ai assessment</span>
        <button
          onClick={run}
          disabled={running}
          className="flex items-center gap-1.5 rounded border border-border px-2 py-1 font-mono text-[11px] text-text-secondary transition-colors hover:border-accent/60 hover:text-accent disabled:opacity-40"
        >
          {running && <Spinner />}
          {running ? "analyzing…" : assessment ? "re-analyze" : "analyze"}
        </button>
      </div>

      {error && <ErrorBanner message={error} className="mb-2" />}

      {!assessment && !error && !running && (
        <p className="text-[11px] leading-relaxed text-text-tertiary">
          Run an assessment to get a second read on this finding's evidence. Advisory only —
          it never changes the finding.
        </p>
      )}

      {assessment && m && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-sm border px-1.5 py-0.5 font-mono text-[11px]"
              style={{ color: m.color, borderColor: `${m.color}55`, backgroundColor: `${m.color}18` }}
            >
              {m.label}
            </span>
            <Tooltip label="How confident the model is in its own reading. Low confidence means the caveats below matter more than the conclusion.">
              <span className="cursor-help font-mono text-[11px] tabular-nums text-text-tertiary">
                {Math.round(assessment.confidence * 100)}% confidence
              </span>
            </Tooltip>
            <Tooltip label="The AI's suggested severity. It does not change the finding's recorded severity — only you can do that.">
              <span
                className="cursor-help font-mono text-[11px]"
                style={{ color: severityColor(assessment.severity as Severity) }}
              >
                suggests {assessment.severity}
              </span>
            </Tooltip>
          </div>

          <p className="mt-1.5 text-[11px] italic leading-relaxed text-text-tertiary">{m.note}</p>

          {lowConfidence && (
            <p className="mt-2 rounded border border-severity-medium/30 bg-severity-medium/5 px-2 py-1.5 text-[11px] leading-relaxed text-severity-medium">
              Low confidence — treat the missing-evidence list below as the useful output here,
              not the conclusion.
            </p>
          )}

          <p className="mt-2.5 text-xs leading-relaxed text-text-secondary">
            {assessment.reasoning_summary}
          </p>

          <Section
            title="Evidence supporting"
            items={assessment.evidence_supporting}
            hint="What in the captured evidence points toward this finding being real."
            tone={severityColor("high")}
          />
          <Section
            title="Evidence missing"
            items={assessment.evidence_missing}
            hint="What isn't in the evidence yet. Usually the most actionable part."
            tone={severityColor("medium")}
          />
          <Section
            title="Assumptions"
            items={assessment.assumptions}
            hint="What the model assumed because the evidence didn't say. Check these — a wrong assumption invalidates the assessment."
          />
          <Section
            title="Recommended validation — not yet performed"
            items={assessment.recommended_validation}
            hint="Steps for you to run. Kompromap has no network access and has not executed any of these."
            ordered
            tone={colors.accent}
          />
          <Section
            title="Potential impact if confirmed"
            items={assessment.potential_impact}
            hint="What an attacker could achieve — conditional on the finding actually being valid."
          />
          <Section
            title="Worth checking nearby"
            items={assessment.related_vulnerability_types}
            hint="Related vulnerability classes that often occur alongside this one."
          />

          <p className="mt-3 border-t border-border-subtle pt-2 text-[10px] leading-relaxed text-text-disabled">
            Advisory analysis of the evidence above — not a test result. The model has no
            network access and did not interact with the target.
            {meta.model && ` · ${meta.model}`}
            {meta.at && ` · ${new Date(meta.at).toLocaleString()}`}
          </p>
        </>
      )}
    </div>
  );
}
