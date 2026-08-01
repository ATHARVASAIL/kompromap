interface ShortcutsHelpProps {
  onClose: () => void;
}

const SHORTCUTS: { keys: string; description: string }[] = [
  { keys: "Ctrl/Cmd + K", description: "Open command palette" },
  { keys: "/", description: "Focus search (nodes on Graph, findings on Findings)" },
  { keys: "f", description: "Focus the node-type filter" },
  { keys: "Esc", description: "Close the topmost open panel or modal" },
  { keys: "?", description: "Show this help" },
];

export default function ShortcutsHelp({ onClose }: ShortcutsHelpProps) {
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 font-mono text-sm" onClick={onClose}>
      <div
        className="w-80 animate-fade-in-scale rounded-md border border-border bg-surface-1 p-5 shadow-elevated"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-sans text-sm font-medium text-text-primary">Keyboard shortcuts</h2>
          <button onClick={onClose} className="text-text-tertiary hover:text-text-primary" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="space-y-2 text-xs">
          {SHORTCUTS.map((s) => (
            <div key={s.keys} className="flex items-center justify-between gap-3">
              <span className="text-text-secondary">{s.description}</span>
              <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-primary">
                {s.keys}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
