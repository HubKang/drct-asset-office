import { useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import clsx from "clsx";
import topMenus from "@/data/json/topMenus.json";
import sideMenus from "@/data/json/sideMenus.json";
import { routeRegistryMap } from "@/router/routeRegistry";

function AdminLayout() {
  const location = useLocation();
  const [hoveredGroupKey, setHoveredGroupKey] = useState<string | null>(null);
  const [pinnedGroupKey, setPinnedGroupKey] = useState<string | null>(null);

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
    return found ?? null;
  }, [location.pathname]);

  const activeGroupKey = currentRoute?.menuKey ?? null;

  const handleTogglePinnedGroup = (groupKey: string) => {
    setPinnedGroupKey((prev) => (prev === groupKey ? null : groupKey));
  };

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="side-brand">
          <p className="side-brand-title">DrCT에셋</p>
          <p className="side-brand-subtitle">AI Investment Research Office</p>
        </div>

        {grouped.map((group) => {
          const isExpanded = pinnedGroupKey
            ? pinnedGroupKey === group.menuKey || hoveredGroupKey === group.menuKey
            : activeGroupKey === group.menuKey || hoveredGroupKey === group.menuKey;
          const groupMenuId = `side-group-${group.menuKey}`;

          return (
            <div
              className="side-menu-group"
              key={group.menuKey}
              onMouseEnter={() => setHoveredGroupKey(group.menuKey)}
              onMouseLeave={() => setHoveredGroupKey(null)}
            >
              <button
                type="button"
                className={clsx("side-menu-title-button", isExpanded && "side-menu-title-button-expanded")}
                onClick={() => handleTogglePinnedGroup(group.menuKey)}
                aria-expanded={isExpanded}
                aria-controls={groupMenuId}
                title={`${group.title} 메뉴 펼치기`}
              >
                <span className="side-menu-title-text">{group.title}</span>
                <span className="side-menu-title-caret" aria-hidden="true">
                  {isExpanded ? "▾" : "▸"}
                </span>
              </button>
              <ul id={groupMenuId} className={clsx("side-menu-list", !isExpanded && "side-menu-list-collapsed")}>
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
          );
        })}
      </aside>

      <div className="app-main">
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
