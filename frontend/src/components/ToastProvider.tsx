import { useCallback, useRef, useState } from "react";
import { ToastContext, type ToastKind } from "./toastContext";

interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

const KIND_STYLE: Record<ToastKind, string> = {
  success: "border-accent/40 bg-accent/10 text-accent",
  error: "border-severity-critical/40 bg-severity-critical/10 text-severity-critical",
  info: "border-border bg-surface-2 text-text-secondary",
};

const DURATION_MS = 3200;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const toast = useCallback((message: string, kind: ToastKind = "success") => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, DURATION_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 left-1/2 z-[200] flex -translate-x-1/2 flex-col items-center gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto animate-toast-in rounded border px-3.5 py-2 font-mono text-xs shadow-elevated ${KIND_STYLE[t.kind]}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
