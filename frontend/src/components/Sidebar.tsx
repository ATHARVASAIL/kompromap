import type { Engagement } from "../types/graph";
import EngagementSwitcher from "./EngagementSwitcher";

export type Section = "graph" | "findings" | "pathfind" | "report" | "dashboard" | "import";

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
    id: "report",
    label: "Report",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <path d="M6.5 2.5h8L19 7v14.5H6.5z" />
        <path d="M14 2.5V7h5" />
        <path d="M9.5 12h7M9.5 15.5h7M9.5 19h4" />
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

// The sliding indicator is absolutely positioned, so it needs to know the
// item geometry rather than inferring it from the DOM.
const ITEM_HEIGHT = 36;
const ITEM_GAP = 2;

export default function Sidebar({
  active,
  onSelect,
  engagement,
  onEngagementChanged,
  nodeCount,
  edgeCount,
  onShowShortcuts,
}: SidebarProps) {
  const activeIndex = ITEMS.findIndex((i) => i.id === active);

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

      <nav className="relative flex-1 p-2 font-mono text-xs">
        {/* Sliding indicator — one element that moves, rather than each
            item toggling its own background. Reads as a single continuous
            object tracking your position instead of a blink. */}
        <span
          aria-hidden
          className="pointer-events-none absolute left-2 right-2 rounded bg-accent/10 ring-1 ring-inset ring-accent/25 transition-transform duration-300 ease-snap"
          style={{
            height: ITEM_HEIGHT,
            transform: `translateY(${activeIndex * (ITEM_HEIGHT + ITEM_GAP)}px)`,
            opacity: activeIndex < 0 ? 0 : 1,
          }}
        />
        <div className="relative" style={{ display: "grid", gap: ITEM_GAP }}>
          {ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              aria-current={active === item.id ? "page" : undefined}
              style={{ height: ITEM_HEIGHT }}
              className={`group flex w-full items-center gap-2.5 rounded px-2.5 text-left transition-colors duration-200 ${
                active === item.id
                  ? "text-accent"
                  : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
              }`}
            >
              <span
                className={`transition-transform duration-200 ease-snap group-hover:scale-110 ${
                  active === item.id ? "text-accent" : "text-text-tertiary"
                }`}
              >
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </div>
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
