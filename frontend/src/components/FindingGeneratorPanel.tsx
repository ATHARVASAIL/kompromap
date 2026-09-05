import { useCallback, useEffect, useState } from "react";
import { generateFindingDescription, getFindingGenStatus, type GeneratedFinding, type FindingGenResponse } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Tooltip from "../components/Tooltip";

interface FindingGeneratorPanelProps {
  findingId: string;
  findingTitle: string;
  /** Called when the analyst accepts the generated description */
  onApply?: (generated: GeneratedFinding) => void;
}

export default function FindingGeneratorPanel({ findingId, findingTitle, onApply }: FindingGeneratorPanelProps) {
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FindingGenResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState<GeneratedFinding | null>(null);

  useEffect(() => {
    getFindingGenStatus().then((s) => setAvailable(s.available)).catch(() => setAvailable(false));
  }, []);

  const handleGenerate = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setEdited(null);
    setEditing(false);
    try {
      const res = await generateFindingDescription(findingId);
      setResult(res);
      if (res.error) setError(res.error);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [findingId]);

  const handleApply = useCallback(() => {
    const toApply = editing ? edited : result?.generated;
    if (toApply && onApply) onApply(toApply);
  }, [editing, edited, result, onApply]);

  if (!available) return null;

  const generated = editing ? edited : result?.generated;

  return (
    <div className="mt-3 rounded-lg border border-border bg-surface-1 p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-wide text-text-tertiary">
          AI description
        </span>
        {!result && !loading && (
          <Tooltip label="Generate a structured finding description for the report. Advisory only — the analyst decides.">
            <button
              onClick={handleGenerate}
              className="flex items-center gap-1.5 rounded border border-accent/40 bg-accent/8 px-2.5 py-1 font-mono text-[11px] text-accent transition-colors hover:bg-accent/15"
            >
              Generate
            </button>
          </Tooltip>
        )}
      </div>

      {error && <ErrorBanner message={error} className="mt-2" />}

      {loading && (
        <div className="mt-2 flex items-center gap-2 text-xs text-text-tertiary">
          <Spinner />
          Generating description for &ldquo;{findingTitle}&rdquo;…
        </div>
      )}

      {generated && !error && (
        <div className="mt-2 space-y-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-text-tertiary">
              Confidence: {Math.round((generated.confidence ?? 0) * 100)}%
            </span>
            {result?.model && (
              <span className="font-mono text-[10px] text-text-disabled">via {result.model}</span>
            )}
            <span className="ml-auto flex gap-1.5">
              {!editing ? (
                <button
                  onClick={() => { setEdited(generated); setEditing(true); }}
                  className="rounded border border-border px-2 py-0.5 font-mono text-[10px] text-text-secondary hover:border-accent/50 hover:text-accent"
                >
                  edit
                </button>
              ) : (
                <>
                  <button
                    onClick={handleApply}
                    className="rounded border border-accent/40 bg-accent/8 px-2 py-0.5 font-mono text-[10px] text-accent hover:bg-accent/15"
                  >
                    apply
                  </button>
                  <button
                    onClick={() => { setEditing(false); setEdited(null); }}
                    className="rounded border border-border px-2 py-0.5 font-mono text-[10px] text-text-secondary hover:border-severity-critical/40 hover:text-severity-critical"
                  >
                    cancel
                  </button>
                </>
              )}
            </span>
          </div>

          <FieldEditor
            label="Title"
            value={generated.title}
            editing={editing}
            onChange={(v) => setEdited((prev) => prev ? { ...prev, title: v } : null)}
          />
          <FieldEditor
            label="Description"
            value={generated.description}
            editing={editing}
            multiline
            onChange={(v) => setEdited((prev) => prev ? { ...prev, description: v } : null)}
          />
          {generated.remediation_steps?.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Remediation</span>
              <ol className="mt-0.5 list-decimal space-y-0.5 pl-4 font-mono text-xs text-text-secondary">
                {editing
                  ? generated.remediation_steps.map((step, i) => (
                      <li key={i}>
                        <input
                          value={step}
                          onChange={(e) => {
                            const next = [...(edited?.remediation_steps ?? generated.remediation_steps)];
                            next[i] = e.target.value;
                            setEdited((prev) => prev ? { ...prev, remediation_steps: next } : null);
                          }}
                          className="w-full bg-transparent font-mono text-xs text-text-secondary outline-none"
                        />
                      </li>
                    ))
                  : generated.remediation_steps.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
              </ol>
            </div>
          )}
          {generated.references?.length > 0 && (
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">References</span>
              <ul className="mt-0.5 space-y-0.5 font-mono text-[11px] text-accent">
                {generated.references.map((ref, i) => (
                  <li key={i}>
                    <a href={ref} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {ref}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FieldEditor({
  label,
  value,
  editing,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  editing: boolean;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  if (editing) {
    if (multiline) {
      return (
        <div>
          <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">{label}</span>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
            className="mt-0.5 w-full rounded border border-border bg-surface-2 p-2 font-mono text-xs text-text-primary outline-none focus:border-accent/60"
          />
        </div>
      );
    }
    return (
      <div>
        <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">{label}</span>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-0.5 w-full rounded border border-border bg-surface-2 px-2 py-1 font-mono text-xs text-text-primary outline-none focus:border-accent/60"
        />
      </div>
    );
  }
  return (
    <div>
      <span className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">{label}</span>
      <p className="mt-0.5 font-mono text-xs text-text-primary">{value}</p>
    </div>
  );
}
