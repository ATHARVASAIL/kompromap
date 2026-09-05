import { useState } from "react";
import Spinner from "./Spinner";
import Tooltip from "./Tooltip";
import { colors, severityColor } from "../styles/tokens";
import { VERIFICATION_LABELS, type VerificationStatus } from "../types/graph";

interface VerificationControlProps {
  status: VerificationStatus;
  note: string | null;
  onChange: (status: VerificationStatus, note: string | null) => Promise<void>;
}

const OPTIONS: { id: VerificationStatus; color: string; hint: string }[] = [
  {
    id: "unverified",
    color: colors.text.tertiary,
    hint: "Straight from scanner output — nobody has checked whether it's real yet.",
  },
  {
    id: "confirmed",
    color: severityColor("critical"),
    hint: "Manually reproduced. This is really there.",
  },
  {
    id: "false-positive",
    color: colors.text.disabled,
    hint: "Verified as not real. Excluded from attack chains — a chain routed through a false positive would be a fabricated attack path.",
  },
  {
    id: "needs-retest",
    color: severityColor("medium"),
    hint: "Inconclusive, or a fix was applied and needs re-checking.",
  },
];

/**
 * Records the analyst's triage judgement on a finding.
 *
 * Deliberately not automated. Deciding something is a false positive means
 * actually verifying the vulnerability — Kompromap never touches the
 * target, it only reads files. A heuristic guess shown as a verdict would
 * be worse than nothing: someone skips verifying because the tool sounded
 * confident, and a live vulnerability ships unreported.
 */
export default function VerificationControl({
  status,
  note,
  onChange,
}: VerificationControlProps) {
  const [saving, setSaving] = useState(false);
  const [draftNote, setDraftNote] = useState(note ?? "");
  const [noteOpen, setNoteOpen] = useState(false);

  async function set(next: VerificationStatus) {
    if (next === status) return;
    setSaving(true);
    try {
      await onChange(next, draftNote.trim() || null);
    } finally {
      setSaving(false);
    }
  }

  async function saveNote() {
    setSaving(true);
    try {
      await onChange(status, draftNote.trim() || null);
      setNoteOpen(false);
    } finally {
      setSaving(false);
    }
  }

  const active = OPTIONS.find((o) => o.id === status) ?? OPTIONS[0];

  return (
    <div className="border-t border-border pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-text-tertiary">verification</span>
        {saving && <Spinner className="text-text-tertiary" />}
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {OPTIONS.map((o) => (
          <Tooltip key={o.id} label={o.hint}>
            <button
              onClick={() => set(o.id)}
              disabled={saving}
              aria-pressed={status === o.id}
              className="w-full rounded border px-2 py-1.5 text-[11px] transition-colors disabled:opacity-50"
              style={
                status === o.id
                  ? { color: o.color, borderColor: `${o.color}66`, backgroundColor: `${o.color}1A` }
                  : { color: colors.text.tertiary, borderColor: colors.border.subtle }
              }
            >
              {VERIFICATION_LABELS[o.id]}
            </button>
          </Tooltip>
        ))}
      </div>

      {status === "false-positive" && (
        <p className="mt-2 text-[11px] leading-relaxed text-text-tertiary">
          Excluded from attack chains — a path routed through a finding that isn't real would
          be a fabricated attack path.
        </p>
      )}

      {!noteOpen ? (
        <button
          onClick={() => setNoteOpen(true)}
          className="mt-2 text-[11px] text-text-tertiary underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          {note ? "edit reasoning" : "add reasoning"}
        </button>
      ) : (
        <div className="mt-2">
          <textarea
            value={draftNote}
            onChange={(e) => setDraftNote(e.target.value)}
            rows={2}
            placeholder="Why? e.g. WAF blocks the payload; 403 on every attempt."
            className="w-full resize-none rounded border border-border bg-surface-0 px-2 py-1.5 text-xs text-text-primary focus:border-accent focus:outline-none"
          />
          <div className="mt-1.5 flex gap-2">
            <button
              onClick={() => {
                setDraftNote(note ?? "");
                setNoteOpen(false);
              }}
              className="flex-1 rounded border border-border py-1 text-[11px] text-text-secondary hover:border-border-strong"
            >
              cancel
            </button>
            <button
              onClick={saveNote}
              disabled={saving}
              className="flex-1 rounded border border-accent/60 bg-accent/10 py-1 text-[11px] text-accent hover:bg-accent/20 disabled:opacity-50"
            >
              save
            </button>
          </div>
        </div>
      )}

      {note && !noteOpen && (
        <p className="mt-1.5 border-l-2 border-border-subtle pl-2 text-[11px] italic leading-relaxed text-text-tertiary">
          {note}
        </p>
      )}

      {status === "unverified" && (
        <p className="mt-2 text-[11px] leading-relaxed text-text-disabled">
          Kompromap can't determine this — it never touches the target. Verify manually, then
          record what you found.
        </p>
      )}

      <span className="sr-only">Current verification status: {VERIFICATION_LABELS[active.id]}</span>
    </div>
  );
}
