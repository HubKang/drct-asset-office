import type { ReactNode } from "react";
import clsx from "clsx";

type Props = {
  title: string;
  description?: string;
  action?: ReactNode;
  theme?: "light" | "dark";
};

function PageHeader({ title, description, action, theme = "light" }: Props) {
  return (
    <div className={clsx("page-header", theme === "dark" && "page-header-dark")}>
      <div>
        <h2 className="page-title">{title}</h2>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export default PageHeader;
