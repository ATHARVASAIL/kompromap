/**
 * Toast context + hook, kept separate from the provider *component* so
 * React Fast Refresh works properly — it can only hot-reload a module
 * whose exports are all components, and a file mixing a component with a
 * hook/context silently degrades to a full page reload on every edit.
 */
import { createContext, useContext } from "react";

export type ToastKind = "success" | "error" | "info";

export interface ToastContextValue {
  toast: (message: string, kind?: ToastKind) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
