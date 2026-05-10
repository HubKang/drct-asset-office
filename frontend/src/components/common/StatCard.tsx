import type { LucideIcon } from "lucide-react";
import clsx from "clsx";

type Props = {
  title: string;
  value: string;
  description?: string;
  icon: LucideIcon;
  badge?: string;
  theme?: "light" | "dark";
};

function StatCard({ title, value, description, icon: Icon, badge, theme = "light" }: Props) {
  return (
    <article className={clsx("card", theme === "dark" && "card-dark")}>
      <div className="flex items-start justify-between">
        <div className="rounded-xl border border-current/20 p-2 text-current">
          <Icon size={18} />
        </div>
        {badge ? <span className="badge badge-slate">{badge}</span> : null}
      </div>
      <p className="mt-4 text-sm text-muted">{title}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
    </article>
  );
}

export default StatCard;
