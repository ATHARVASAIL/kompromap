interface EmptyGraphStateProps {
  onImport: () => void;
  onCreateNode: () => void;
}

export default function EmptyGraphState({ onImport, onCreateNode }: EmptyGraphStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 px-6 text-center">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" className="text-text-tertiary">
        <circle cx="6" cy="18" r="2.2" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="12" cy="7" r="2.2" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="18" cy="18" r="2.2" stroke="currentColor" strokeWidth="1.4" />
        <path d="M7.6 16.7 10.6 9M13.4 9l2.9 7.7" stroke="currentColor" strokeWidth="1.4" strokeDasharray="3 2.5" />
      </svg>

      <div className="space-y-1.5">
        <h2 className="font-sans text-sm font-medium text-text-primary">No graph yet</h2>
        <p className="max-w-sm font-sans text-xs leading-relaxed text-text-tertiary">
          Import recon or scan output to build the attack-chain graph automatically, or add the
          first node by hand.
        </p>
      </div>

      <div className="flex gap-2 font-mono text-xs">
        <button
          onClick={onImport}
          className="rounded border border-accent/50 bg-accent/10 px-3.5 py-1.5 text-accent hover:bg-accent/20"
        >
          Import scan data
        </button>
        <button
          onClick={onCreateNode}
          className="rounded border border-border px-3.5 py-1.5 text-text-secondary hover:border-border-strong hover:text-text-primary"
        >
          Add manually
        </button>
      </div>
    </div>
  );
}
