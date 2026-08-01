import { useEffect, useState } from "react";
import { activateEngagement, createEngagement, listEngagements } from "../api/client";
import ErrorBanner from "./ErrorBanner";
import Skeleton from "./Skeleton";
import type { Engagement } from "../types/graph";

interface EngagementSwitcherProps {
  active: Engagement | null;
  onChanged: () => void;
}

export default function EngagementSwitcher({ active, onChanged }: EngagementSwitcherProps) {
  const [open, setOpen] = useState(false);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newClient, setNewClient] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    listEngagements()
      .then(setEngagements)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [open]);

  async function handleActivate(id: string) {
    if (id === active?.id) {
      setOpen(false);
      return;
    }
    try {
      await activateEngagement(id);
      setOpen(false);
      onChanged();
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await createEngagement(newName.trim(), newClient.trim() || undefined, true);
      setNewName("");
      setNewClient("");
      setCreating(false);
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="relative font-mono text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded border border-border px-3 py-1.5 text-text-secondary hover:border-border-strong"
      >
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
        {active?.name ?? "loading…"}
        <span className="text-text-tertiary">▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 z-50 mt-1 w-72 rounded border border-border bg-surface-1 shadow-xl">
            <div className="border-b border-border px-3 py-2 text-text-tertiary">workspaces</div>

            {loading && (
              <div className="space-y-1.5 px-3 py-2.5">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
              </div>
            )}
            {error && <ErrorBanner message={error} className="mx-3 my-2" />}

            <div className="max-h-64 overflow-y-auto">
              {engagements.map((e) => (
                <button
                  key={e.id}
                  onClick={() => handleActivate(e.id)}
                  className={`flex w-full items-center justify-between px-3 py-2 text-left hover:bg-surface-2 ${
                    e.id === active?.id ? "text-accent" : "text-text-secondary"
                  }`}
                >
                  <span className="truncate">
                    {e.name}
                    {e.client_name && <span className="ml-1.5 text-text-tertiary">· {e.client_name}</span>}
                  </span>
                  {e.id === active?.id && <span>✓</span>}
                </button>
              ))}
            </div>

            <div className="border-t border-border p-2">
              {!creating ? (
                <button
                  onClick={() => setCreating(true)}
                  className="w-full rounded border border-border py-1.5 text-text-tertiary hover:border-accent hover:text-accent"
                >
                  + new workspace
                </button>
              ) : (
                <form onSubmit={handleCreate} className="space-y-2">
                  <input
                    autoFocus
                    placeholder="engagement name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
                  />
                  <input
                    placeholder="client name (optional)"
                    value={newClient}
                    onChange={(e) => setNewClient(e.target.value)}
                    className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setCreating(false)}
                      className="flex-1 rounded border border-border py-1.5 text-text-tertiary hover:border-border-strong"
                    >
                      cancel
                    </button>
                    <button
                      type="submit"
                      className="flex-1 rounded border border-accent bg-accent/10 py-1.5 text-accent hover:bg-accent/20"
                    >
                      create
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
