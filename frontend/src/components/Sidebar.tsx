import type { Engagement } from "../types/graph";
import EngagementSwitcher from "./EngagementSwitcher";

export type Section = "graph" | "findings" | "pathfind" | "dashboard" | "import";

interface SidebarProps {
  active: Section;
  onSelect: (section: Section) => void;
  engagement: Engagement | null;
  onEngagementChanged: () => void;
  nodeCount: number;
  edgeCount: number;
  onShowShortcuts: () => void;
}

const ITEMS: { id: Section; label: string; icon: JSX.Element }[] = [
  {
    id: "graph",
    label: "Graph",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="6" cy="7" r="2.2" />
        <circle cx="18" cy="7" r="2.2" />
        <circle cx="12" cy="18" r="2.2" />
        <path d="M7.7 8.6 10.5 16.3M16.3 8.6 13.5 16.3M8.2 7h7.6" />
      </svg>
    ),
  },
  {
    id: "findings",
    label: "Findings",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M12 3.5 21 19H3L12 3.5Z" />
        <path d="M12 9.5v4.5" />
        <circle cx="12" cy="16.3" r="0.7" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    id: "pathfind",
    label: "Path Analysis",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="5" cy="18" r="2" />
        <circle cx="19" cy="6" r="2" />
        <path d="M6.6 16.7 16 8.5" strokeDasharray="2.5 2.5" />
      </svg>
    ),
  },
  {
    id: "dashboard",
    label: "Dashboard",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="3.5" y="3.5" width="7" height="9" rx="1" />
        <rect x="13.5" y="3.5" width="7" height="5" rx="1" />
        <rect x="13.5" y="11.5" width="7" height="9" rx="1" />
        <rect x="3.5" y="15.5" width="7" height="5" rx="1" />
      </svg>
    ),
  },
  {
    id: "import",
    label: "Import",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M12 3v12.5" />
        <path d="M7.5 11 12 15.5 16.5 11" />
        <path d="M4.5 18.5h15" />
      </svg>
    ),
  },
];

export default function Sidebar({
  active,
  onSelect,
  engagement,
  onEngagementChanged,
  nodeCount,
  edgeCount,
  onShowShortcuts,
}: SidebarProps) {
  return (
    <aside className="flex h-full w-52 flex-col border-r border-border bg-surface-1">
      <div className="border-b border-border px-3 py-3">
        <div className="mb-2.5 flex items-center gap-1.5 px-1">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-accent">
            <circle cx="5" cy="19" r="2.3" stroke="currentColor" strokeWidth="1.6" />
            <circle cx="12" cy="8" r="2.3" stroke="currentColor" strokeWidth="1.6" />
            <circle cx="19" cy="19" r="2.3" stroke="currentColor" strokeWidth="1.6" />
            <path d="M6.6 17.5 10.6 10M13.4 10l3.9 7.5" stroke="currentColor" strokeWidth="1.6" />
          </svg>
          <span className="font-sans text-sm font-semibold tracking-tight text-text-primary">Kompromap</span>
        </div>
        <EngagementSwitcher active={engagement} onChanged={onEngagementChanged} />
      </div>

      <nav className="flex-1 space-y-0.5 p-2 font-mono text-xs">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-left transition-colors ${
              active === item.id
                ? "bg-accent/10 text-accent"
                : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
            }`}
          >
            <span className={active === item.id ? "text-accent" : "text-text-tertiary"}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="flex items-center justify-between border-t border-border px-3 py-2.5 font-mono text-[11px] text-text-tertiary">
        <span>
          {nodeCount} nodes · {edgeCount} edges
        </span>
        <button onClick={onShowShortcuts} className="rounded border border-border px-1.5 hover:border-border-strong hover:text-text-secondary" title="Keyboard shortcuts">
          ?
        </button>
      </div>
    </aside>
  );
}
