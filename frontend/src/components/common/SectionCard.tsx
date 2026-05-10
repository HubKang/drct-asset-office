import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  title?: string;
  children: ReactNode;
  theme?: "light" | "dark";
  className?: string;
};

function SectionCard({ title, children, theme = "light", className }: Props) {
  return (
    <section className={clsx("card", theme === "dark" && "card-dark", className)}>
      {title ? <h3 className="section-title">{title}</h3> : null}
      {children}
    </section>
  );
}

export default SectionCard;
