import { useEffect, useRef } from "react";

export interface ContextMenuAction {
  id: string;
  label: string;
  destructive?: boolean;
  onSelect: () => void;
}

interface NodeContextMenuProps {
  x: number;
  y: number;
  title: string;
  actions: ContextMenuAction[];
  onClose: () => void;
}

/**
 * Right-click menu for graph nodes.
 *
 * Everything here is reachable elsewhere (detail panel, toolbar), but on a
 * graph the node *is* the object you're thinking about — making the
 * common actions available where the pointer already is saves a trip to
 * the panel for every small change.
 *
 * Closes on outside click, Escape, or scroll: a menu anchored to a
 * viewport coordinate goes stale the moment the canvas pans.
 */
export default function NodeContextMenu({ x, y, title, actions, onClose }: NodeContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("wheel", onClose, { passive: true });
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("wheel", onClose);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      role="menu"
      style={{
        left: x,
        top: y,
        // Keep the menu on screen when the node sits near an edge.
        transform: `translate(${x > window.innerWidth - 200 ? "-100%" : "0"}, ${
          y > window.innerHeight - 220 ? "-100%" : "0"
        })`,
      }}
      className="absolute z-[130] w-44 animate-fade-in-scale overflow-hidden rounded-md border border-border bg-surface-1 shadow-elevated"
    >
      <div className="truncate border-b border-border-subtle px-3 py-2 font-mono text-[11px] text-text-tertiary">
        {title}
      </div>
      {actions.map((a) => (
        <button
          key={a.id}
          role="menuitem"
          onClick={() => {
            a.onSelect();
            onClose();
          }}
          className={`block w-full px-3 py-2 text-left font-mono text-xs transition-colors ${
            a.destructive
              ? "text-severity-critical hover:bg-severity-critical/10"
              : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
          }`}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
