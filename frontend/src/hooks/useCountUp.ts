import { useEffect, useRef, useState } from "react";

/**
 * Animate a number from 0 up to `value` on mount / when it changes.
 *
 * Uses requestAnimationFrame with an ease-out curve rather than a fixed
 * step count, so the duration is honest regardless of the magnitude —
 * counting to 4 and counting to 4000 both take the same wall-clock time.
 *
 * Returns the target immediately when the user prefers reduced motion:
 * a number ticking upward is exactly the kind of thing that setting exists
 * to suppress.
 */
export function useCountUp(value: number, durationMs = 700): number {
  const [display, setDisplay] = useState(value);
  const frame = useRef<number>();

  useEffect(() => {
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced || value === 0) {
      setDisplay(value);
      return;
    }

    const start = performance.now();
    const from = 0;

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(elapsed / durationMs, 1);
      // easeOutCubic — fast start, gentle settle.
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };

    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [value, durationMs]);

  return display;
}
