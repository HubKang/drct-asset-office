import clsx from "clsx";

type Tone = "emerald" | "amber" | "rose" | "blue" | "slate";
type Variant = "positive" | "neutral" | "negative" | "risk-high" | "risk-medium" | "risk-low" | "risk-unknown" | "importance-high" | "importance-medium" | "importance-low" | "event";

type Props = {
  label: string;
  tone?: Tone;
  variant?: Variant;
};

const toneMap: Record<Tone, string> = {
  emerald: "badge-emerald",
  amber: "badge-amber",
  rose: "badge-rose",
  blue: "badge-blue",
  slate: "badge-slate",
};

const variantMap: Record<Variant, string> = {
  positive: "badge-positive",
  neutral: "badge-neutral",
  negative: "badge-negative",
  "risk-high": "badge-risk-high",
  "risk-medium": "badge-risk-medium",
  "risk-low": "badge-risk-low",
  "risk-unknown": "badge-risk-unknown",
  "importance-high": "badge-importance-high",
  "importance-medium": "badge-importance-medium",
  "importance-low": "badge-importance-low",
  event: "badge-event",
};

function StatusBadge({ label, tone = "slate", variant }: Props) {
  return <span className={clsx("badge", variant ? variantMap[variant] : toneMap[tone])}>{label}</span>;
}

export default StatusBadge;
