import { useId, useState } from "react";

interface TooltipProps {
  label: string;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}

const SIDE_CLASS: Record<NonNullable<TooltipProps["side"]>, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-1.5",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-1.5",
  left: "right-full top-1/2 -translate-y-1/2 mr-1.5",
  right: "left-full top-1/2 -translate-y-1/2 ml-1.5",
};

/**
 * Minimal tooltip. Shows on hover *and* keyboard focus — a hover-only
 * tooltip is invisible to anyone navigating by keyboard, which is most of
 * this app's power users given the shortcut system.
 *
 * Deliberately not a library: the whole behaviour is ~30 lines, and
 * Floating UI would add ~15kb for collision detection we don't need at
 * these anchor positions.
 */
export default function Tooltip({ label, children, side = "top" }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && (
        <span
          id={id}
          role="tooltip"
          className={`pointer-events-none absolute z-[120] whitespace-nowrap rounded border border-border bg-surface-2 px-2 py-1 font-mono text-[11px] leading-none text-text-primary shadow-card animate-fade-in ${SIDE_CLASS[side]}`}
        >
          {label}
        </span>
      )}
    </span>
  );
}
