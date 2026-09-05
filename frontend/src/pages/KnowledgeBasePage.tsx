import { useEffect, useMemo, useState } from "react";
import {
  type KnowledgeBaseEntryResponse,
  type SimilarSearchResponse,
  getKbEntries,
  searchKbSimilar,
  seedKb,
} from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Spinner from "../components/Spinner";
import Tooltip from "../components/Tooltip";

type View = "list" | "detail" | "search";

export default function KnowledgeBasePage() {
  const [entries, setEntries] = useState<KnowledgeBaseEntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("list");
  const [selected, setSelected] = useState<KnowledgeBaseEntryResponse | null>(null);
  const [searchCwe, setSearchCwe] = useState("");
  const [searchTag, setSearchTag] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [similarResults, setSimilarResults] = useState<SimilarSearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [seeded, setSeeded] = useState(false);

  function load() {
    setLoading(true);
    setError(null);
    getKbEntries()
      .then((data) => setEntries(data))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleSeed() {
    try {
      await seedKb();
      setSeeded(true);
      load();
    } catch (e) {
      setError(String(e));
    }
  }

  function handleSelect(entry: KnowledgeBaseEntryResponse) {
    setSelected(entry);
    setView("detail");
  }

  const filtered = useMemo(() => {
    let result = entries;
    if (searchCwe.trim()) {
      const q = searchCwe.trim().toUpperCase();
      result = result.filter((e) => e.cwe_id?.toUpperCase().includes(q));
    }
    if (searchTag.trim()) {
      const q = searchTag.trim().toLowerCase();
      result = result.filter((e) => (e.tags || []).some((t) => t.toLowerCase().includes(q)));
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.description.toLowerCase().includes(q)
      );
    }
    return result;
  }, [entries, searchCwe, searchTag, searchQuery]);

  async function handleSimilarSearch() {
    setSearching(true);
    setError(null);
    try {
      const result = await searchKbSimilar({
        cwe_id: searchCwe.trim() || undefined,
        tags: searchTag.trim() ? searchTag.trim().split(",").map((t) => t.trim()) : [],
        description: searchQuery.trim() || undefined,
        top_n: 5,
      });
      setSimilarResults(result);
      setView("search");
    } catch (e) {
      setError(String(e));
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-base font-medium text-text-primary">Knowledge Base</h1>
          <p className="mt-1 max-w-xl font-sans text-xs leading-relaxed text-text-tertiary">
            Reference library of vulnerability types, CWE entries, remediation guidance,
            and similarity search against current findings.
          </p>
        </div>
        <div className="flex gap-2">
          {!seeded && entries.length === 0 && (
            <Tooltip label="Load the built-in CWE reference library">
              <button
                onClick={handleSeed}
                className="flex items-center gap-2 rounded border border-accent/60 bg-accent/10 px-3.5 py-1.5 font-mono text-xs text-accent transition-colors hover:bg-accent/20"
              >
                Load reference library
              </button>
            </Tooltip>
          )}
          <button
            onClick={load}
            className="flex items-center gap-2 rounded border border-border px-3.5 py-1.5 font-mono text-xs text-text-secondary transition-colors hover:border-accent/60 hover:text-accent"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} className="mt-4" />}

      {/* Search / filter bar */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          value={searchCwe}
          onChange={(e) => setSearchCwe(e.target.value)}
          placeholder="filter by CWE…"
          className="w-40 rounded border border-border bg-surface-0 px-2.5 py-1.5 font-mono text-xs text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
        />
        <input
          value={searchTag}
          onChange={(e) => setSearchTag(e.target.value)}
          placeholder="filter by tag…"
          className="w-40 rounded border border-border bg-surface-0 px-2.5 py-1.5 font-mono text-xs text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
        />
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="search name or description…"
          className="w-56 rounded border border-border bg-surface-0 px-2.5 py-1.5 font-mono text-xs text-text-secondary placeholder-text-tertiary focus:border-accent/60 focus:outline-none"
        />
        <button
          onClick={handleSimilarSearch}
          disabled={searching}
          className="ml-auto flex items-center gap-1.5 rounded border border-accent/40 bg-accent/8 px-3 py-1.5 font-mono text-[11px] text-accent transition-colors hover:bg-accent/15 disabled:opacity-40"
        >
          {searching && <Spinner />}
          Similarity search
        </button>
      </div>

      {/* List view */}
      {view === "list" && (
        <div className="mt-4">
          {loading && entries.length === 0 ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-4 w-16 rounded bg-surface-2" />
                  <div className="h-4 w-48 rounded bg-surface-2" />
                  <div className="h-4 w-24 rounded bg-surface-2" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState message={entries.length === 0 ? "Load the reference library or add custom entries to get started." : "No entries match the current filters."} />
          ) : (
            <table className="w-full border-collapse font-mono text-xs">
              <thead className="sticky top-0 z-10 bg-surface-1 text-text-tertiary shadow-[0_1px_0_0_rgb(var(--border-subtle))]">
                <tr>
                  <th className="px-3 py-2 text-left font-normal">CWE</th>
                  <th className="px-3 py-2 text-left font-normal">Name</th>
                  <th className="px-3 py-2 text-left font-normal">OWASP</th>
                  <th className="px-3 py-2 text-left font-normal">Tags</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((entry, i) => (
                  <tr
                    key={entry.id}
                    onClick={() => handleSelect(entry)}
                    style={{ animationDelay: `${Math.min(i, 20) * 25}ms` }}
                    className="group animate-fade-in cursor-pointer border-t border-border-subtle transition-colors duration-150 hover:bg-surface-2"
                  >
                    <td className="px-3 py-2 text-text-secondary">{entry.cwe_id || "—"}</td>
                    <td className="px-3 py-2 text-text-primary">{entry.name}</td>
                    <td className="px-3 py-2 text-text-secondary">{entry.owasp_category || "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {(entry.tags || []).slice(0, 3).map((t) => (
                          <span key={t} className="rounded-full border border-border bg-surface-0 px-1.5 py-0.5 text-[10px] text-text-tertiary">
                            {t}
                          </span>
                        ))}
                        {(entry.tags || []).length > 3 && (
                          <span className="px-1.5 py-0.5 text-[10px] text-text-disabled">+{entry.tags.length - 3}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Detail view */}
      {view === "detail" && selected && (
        <div className="mt-4">
          <button
            onClick={() => setView("list")}
            className="mb-3 flex items-center gap-1 rounded border border-border px-2.5 py-1 font-mono text-[11px] text-text-secondary hover:border-accent/50 hover:text-accent"
          >
            ← back to list
          </button>
          <div className="rounded-lg border border-border bg-surface-1 p-5">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-sans text-sm font-medium text-text-primary">{selected.name}</h2>
                <div className="mt-1 flex gap-2 font-mono text-xs text-text-tertiary">
                  {selected.cwe_id && <span className="rounded-full border border-border bg-surface-0 px-2 py-0.5">{selected.cwe_id}</span>}
                  {selected.owasp_category && <span className="rounded-full border border-border bg-surface-0 px-2 py-0.5">{selected.owasp_category}</span>}
                  {selected.severity_guidance && (
                    <span className="rounded-full border border-severity-medium/30 bg-severity-medium/5 px-2 py-0.5 text-severity-medium">
                      {selected.severity_guidance}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-4">
              <h3 className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Description</h3>
              <p className="mt-1 font-sans text-xs leading-relaxed text-text-secondary">{selected.description}</p>
            </div>

            <div className="mt-4">
              <h3 className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Remediation</h3>
              <p className="mt-1 whitespace-pre-wrap font-sans text-xs leading-relaxed text-text-secondary">{selected.remediation}</p>
            </div>

            {selected.tags && selected.tags.length > 0 && (
              <div className="mt-4">
                <h3 className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">Tags</h3>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {selected.tags.map((t) => (
                    <span key={t} className="rounded-full border border-border bg-surface-0 px-2 py-0.5 font-mono text-[11px] text-text-secondary">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selected.references && selected.references.length > 0 && (
              <div className="mt-4">
                <h3 className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">References</h3>
                <ul className="mt-1 space-y-1">
                  {selected.references.map((ref, i) => (
                    <li key={i}>
                      <a href={ref} target="_blank" rel="noopener noreferrer" className="font-mono text-[11px] text-accent hover:underline">
                        {ref}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Similarity search results */}
      {view === "search" && (
        <div className="mt-4">
          <button
            onClick={() => setView("list")}
            className="mb-3 flex items-center gap-1 rounded border border-border px-2.5 py-1 font-mono text-[11px] text-text-secondary hover:border-accent/50 hover:text-accent"
          >
            ← back to list
          </button>
          {similarResults && similarResults.matches.length === 0 ? (
            <EmptyState message="No similar entries found. Try broadening the search." />
          ) : (
            <div className="space-y-2">
              {similarResults?.matches.map((match) => (
                <div
                  key={match.entry_id}
                  onClick={() => {
                    const entry = entries.find((e) => e.id === match.entry_id);
                    if (entry) handleSelect(entry);
                  }}
                  className="group cursor-pointer rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:border-accent/40 hover:bg-surface-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-sans text-sm text-text-primary">{match.name}</span>
                    <span className="font-mono text-xs text-accent">{Math.round(match.score * 100)}% match</span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 font-mono text-xs text-text-tertiary">
                    {match.cwe_id && <span>{match.cwe_id}</span>}
                    <span className="text-text-disabled">·</span>
                    <span>{match.match_reason}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
