interface EmptyStateProps {
  message: string;
  className?: string;
}

export default function EmptyState({ message, className = "" }: EmptyStateProps) {
  return (
    <div
      className={`rounded border border-dashed border-border px-3 py-4 text-center font-mono text-xs text-text-tertiary ${className}`}
    >
      {message}
    </div>
  );
}
