import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import clsx from "clsx";
import topMenus from "@/data/json/topMenus.json";
import sideMenus from "@/data/json/sideMenus.json";
import { routeRegistryMap } from "@/router/routeRegistry";
import { dataSourceLabel } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import StatusBadge from "@/components/common/StatusBadge";

const darkAnalysisRoutes = new Set(["/dashboard"]);

function AdminLayout() {
  const location = useLocation();
  const [apiStatus, setApiStatus] = useState<"확인중" | "정상" | "오프라인">("확인중");

  useEffect(() => {
    const run = async () => {
      if (dataSourceLabel !== "api") {
        setApiStatus("정상");
        return;
      }
      try {
        const res = await fetch(`${appConfig.apiBaseUrl}/health`);
        setApiStatus(res.ok ? "정상" : "오프라인");
      } catch {
        setApiStatus("오프라인");
      }
    };
    run();
  }, []);

  const grouped = useMemo(() => {
    return topMenus.map((top) => ({
      ...top,
      items: sideMenus.filter((s) => s.menuKey === top.menuKey),
    }));
  }, []);

  const currentRoute = useMemo(() => {
    const found = sideMenus.find((m) => {
      const route = routeRegistryMap[m.routeKey];
      return route && location.pathname === route.path;
    });
    return found;
  }, [location.pathname]);

  const isDarkPage = darkAnalysisRoutes.has(location.pathname);

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="side-brand">
          <p className="side-brand-title">DrCT에셋</p>
          <p className="side-brand-subtitle">AI Investment Research Office</p>
        </div>

        {grouped.map((group) => (
          <div className="side-menu-group" key={group.menuKey}>
            <p className="side-menu-title">{group.title}</p>
            <ul className="side-menu-list">
              {group.items.map((menu) => {
                const route = routeRegistryMap[menu.routeKey];
                if (!route) return null;
                return (
                  <li key={menu.routeKey}>
                    <NavLink
                      to={route.path}
                      className={({ isActive }) => clsx("side-menu-link", isActive && "side-menu-link-active")}
                    >
                      <span>{menu.title}</span>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </aside>

      <div className="app-main">
        <header className={clsx("top-status-bar", isDarkPage && "border-[var(--color-hairline-violet)] bg-[#1a1330]/92") }>
          <div className="top-status-inner">
            <div>
              <p className={clsx("top-status-title", isDarkPage && "text-white")}>{currentRoute?.title ?? "업무 화면"}</p>
              <p className={clsx("top-status-subtitle", isDarkPage && "text-white/70")}>{currentRoute ? `${currentRoute.title} 화면` : "투자 데이터 운영 상태"}</p>
            </div>

            <div className="top-status-actions">
              <StatusBadge label={`데이터 소스: ${dataSourceLabel.toUpperCase()}`} tone={dataSourceLabel === "api" ? "blue" : "slate"} />
              <StatusBadge label={`API: ${apiStatus}`} tone={apiStatus === "정상" ? "emerald" : apiStatus === "오프라인" ? "rose" : "amber"} />
            </div>
          </div>
        </header>

        <main className="page-content">
          <section className="space-y-4">
            <Outlet />
          </section>
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
