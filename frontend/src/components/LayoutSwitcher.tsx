import Tooltip from "./Tooltip";
import { LAYOUTS, type LayoutName } from "../graph/layouts";

interface LayoutSwitcherProps {
  value: LayoutName;
  onChange: (layout: LayoutName) => void;
}

/**
 * Segmented control rather than a dropdown: there are only five options,
 * switching is exploratory (you try them to see which reads best for the
 * graph you have), and a dropdown hides the alternatives behind a click.
 */
export default function LayoutSwitcher({ value, onChange }: LayoutSwitcherProps) {
  return (
    <div
      role="group"
      aria-label="Graph layout"
      className="flex overflow-hidden rounded border border-border bg-surface-0 font-mono text-[11px]"
    >
      {LAYOUTS.map((l) => (
        <Tooltip key={l.id} label={l.hint}>
          <button
            onClick={() => onChange(l.id)}
            aria-pressed={value === l.id}
            className={`px-2.5 py-1.5 transition-colors duration-150 ${
              value === l.id
                ? "bg-accent/15 text-accent"
                : "text-text-tertiary hover:bg-surface-2 hover:text-text-secondary"
            }`}
          >
            {l.label}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}
