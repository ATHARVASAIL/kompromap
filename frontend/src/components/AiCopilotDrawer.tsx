import { useEffect, useState } from "react";
import Spinner from "./Spinner";
import AiAssessment from "./AiAssessment";

/** Right-drawer panel that surfaces AI triage for the currently selected
 *  finding. Slides in from the right edge of the screen.
 *
 *  Design choices:
 *  - The drawer is advisory only — same `AiAssessment` component used
 *    in the DetailPanel, just surfaced in a dedicated channel so the
 *    analyst can have it open while working elsewhere.
 *  - No button in the drawer modifies the finding. Confirming or
 *    dismissing stays in the verification control.
 *  - Keyboard: `Esc` closes it (handled in AppShell). */
export default function AiCopilotDrawer({
  findingId,
  open,
  onClose,
}: {
  findingId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const [assessment, setAssessment] = useState<string | null>(null);

  useEffect(() => {
    if (!findingId) return;
    let cancelled = false;
    setAssessment(null);
    fetch(`/api/triage/findings/${findingId}`)
      .then((r) => r.ok ? r.json() : Promise.resolve(null))
      .then((data) => {
        if (cancelled) return;
        if (data?.assessment) setAssessment(data.assessment.assessment);
      })
      .catch(() => { if (!cancelled) setAssessment(null); });
    return () => { cancelled = true; };
  }, [findingId]);

  if (!open) return null;

  return (
    <div className="flex h-full w-80 flex-col border-l border-border bg-surface-1">
      <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
        <span className="font-sans text-xs font-medium text-text-primary">AI Copilot</span>
        <button
          onClick={onClose}
          className="rounded border border-border px-1.5 font-mono text-[11px] text-text-tertiary hover:text-text-primary hover:border-border-strong"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {!findingId && (
          <p className="text-[11px] leading-relaxed text-text-tertiary">
            Select a finding to get AI-assisted triage advice.
          </p>
        )}

        {findingId && !assessment && (
          <div className="mt-4 flex flex-col items-center gap-3">
            <Spinner />
            <span className="font-mono text-[11px] text-text-tertiary">Loading assessment…</span>
          </div>
        )}

        {findingId && assessment === "insufficient_evidence" && (
          <div className="mt-3 rounded border border-severity-medium/30 bg-severity-medium/5 px-3 py-2">
            <span className="font-mono text-[11px] text-severity-medium">
              Not enough evidence to triage. Re-run with more context.
            </span>
          </div>
        )}

        {findingId && assessment && assessment !== "insufficient_evidence" && (
          <AiAssessment findingId={findingId} />
        )}
      </div>

      <div className="border-t border-border px-3 py-2">
        <span className="font-mono text-[10px] text-text-disabled">
          Advisory only — the analyst decides.
        </span>
      </div>
    </div>
  );
}
