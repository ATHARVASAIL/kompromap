import { NODE_TYPE_LABELS, type NodeType } from "../types/graph";
import { SEVERITY_LABELS, colors, nodeTypeColor, severityColor, type Severity } from "../styles/tokens";

type FindingStatus = "open" | "fixed" | "accepted-risk";

const STATUS_LABEL: Record<FindingStatus, string> = {
  open: "Open",
  fixed: "Fixed",
  "accepted-risk": "Accepted risk",
};

const STATUS_COLOR: Record<FindingStatus, string> = {
  open: colors.severity.high,
  fixed: colors.severity.low,
  "accepted-risk": colors.text.tertiary,
};

function Pill({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-[11px] leading-none"
      style={{ color, borderColor: `${color}4D`, backgroundColor: `${color}1A` }}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Pill label={SEVERITY_LABELS[severity]} color={severityColor(severity)} />;
}

export function StatusBadge({ status }: { status: FindingStatus }) {
  return <Pill label={STATUS_LABEL[status]} color={STATUS_COLOR[status]} />;
}

export function NodeTypeBadge({ nodeType }: { nodeType: NodeType }) {
  return <Pill label={NODE_TYPE_LABELS[nodeType]} color={nodeTypeColor[nodeType]} />;
}

export function ScopeBadge({ inScope }: { inScope: boolean }) {
  return (
    <Pill label={inScope ? "In scope" : "Out of scope"} color={inScope ? colors.accent : colors.text.tertiary} />
  );
}
