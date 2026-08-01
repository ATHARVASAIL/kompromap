interface ErrorBannerProps {
  message: string;
  className?: string;
}

export default function ErrorBanner({ message, className = "" }: ErrorBannerProps) {
  return (
    <div
      className={`flex items-start gap-2 rounded border border-severity-critical/40 bg-severity-critical/10 px-3 py-2 font-mono text-xs text-severity-critical ${className}`}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" aria-hidden="true">
        <path
          d="M12 3.5 21.5 20h-19L12 3.5Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M12 10v4.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none" />
      </svg>
      <span>{message}</span>
    </div>
  );
}
