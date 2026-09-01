import type { LucideIcon } from "lucide-react";

type Props = {
  icon: LucideIcon;
  title: string;
  description: string;
  compact?: boolean;
};

function SignalEmptyState({ icon: Icon, title, description, compact = false }: Props) {
  return (
    <div className={`drct-signal-empty${compact ? " is-compact" : ""}`}>
      <span className="drct-signal-empty-icon" aria-hidden="true">
        <Icon size={22} strokeWidth={1.8} />
      </span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

export default SignalEmptyState;
