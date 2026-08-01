import { NODE_TYPE_COLOR, NODE_TYPE_LABELS, type GraphFilters, type NodeType } from "../types/graph";

interface FilterBarProps {
  filters: GraphFilters;
  onChange: (filters: GraphFilters) => void;
}

const NODE_TYPES = Object.keys(NODE_TYPE_LABELS) as NodeType[];

export default function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface-1/50 px-4 py-2 font-mono text-xs">
      <select
        data-shortcut-filter
        value={filters.node_type ?? ""}
        onChange={(e) => onChange({ ...filters, node_type: (e.target.value || undefined) as NodeType | undefined })}
        className="rounded border border-border bg-surface-0 px-2 py-1 text-text-secondary focus:border-accent focus:outline-none"
      >
        <option value="">all node types</option>
        {NODE_TYPES.map((t) => (
          <option key={t} value={t}>
            {NODE_TYPE_LABELS[t]}
          </option>
        ))}
      </select>

      <label className="flex items-center gap-1.5 text-text-tertiary">
        <input
          type="checkbox"
          checked={filters.in_scope_only ?? false}
          onChange={(e) => onChange({ ...filters, in_scope_only: e.target.checked || undefined })}
          className="accent-accent"
        />
        in-scope only
      </label>

      <label className="flex items-center gap-1.5 text-text-tertiary">
        min CVSS
        <input
          type="number"
          min={0}
          max={10}
          step={0.1}
          value={filters.min_cvss ?? ""}
          onChange={(e) =>
            onChange({ ...filters, min_cvss: e.target.value === "" ? undefined : Number(e.target.value) })
          }
          className="w-16 rounded border border-border bg-surface-0 px-1.5 py-1 text-text-secondary focus:border-accent focus:outline-none"
        />
      </label>

      <div className="ml-auto flex flex-wrap items-center gap-3">
        {NODE_TYPES.map((t) => (
          <span key={t} className="flex items-center gap-1 text-text-tertiary">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: NODE_TYPE_COLOR[t] }}
            />
            {NODE_TYPE_LABELS[t]}
          </span>
        ))}
      </div>
    </div>
  );
}
