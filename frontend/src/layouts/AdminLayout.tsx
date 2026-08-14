import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, matchPath, useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import clsx from "clsx";
import topMenus from "@/data/json/topMenus.json";
import sideMenus from "@/data/json/sideMenus.json";
import { routeRegistryMap } from "@/router/routeRegistry";

type SideMenuChild = {
  title: string;
  routeKey: string;
};

type SideMenuItem = {
  menuKey: string;
  title: string;
  routeKey: string;
  children?: SideMenuChild[];
};

type TopMenuItem = {
  menuKey: string;
  title: string;
};

const menus = sideMenus as SideMenuItem[];
const SIDEBAR_COLLAPSED_KEY = "drct-app-sidebar-collapsed";

const MENU_DISPLAY: Record<string, { label: string; short: string }> = {
  home: { label: "\uD22C\uC790 \uC804\uB7B5", short: "\uC804" },
  market: { label: "\uC2DC\uC7A5 \uD2B8\uB80C\uB4DC \uBD84\uC11D", short: "\uC2DC" },
  stocks: { label: "\uC885\uBAA9 \uAD00\uB9AC", short: "\uC885" },
  collection: { label: "\uC815\uBCF4 \uC218\uC9D1", short: "\uC815" },
  trade: { label: "\uB9E4\uB9E4 \uAD00\uB9AC", short: "\uB9E4" },
  kms: { label: "DrCT KMS", short: "K" },
  system: { label: "\uC2DC\uC2A4\uD15C", short: "\uC124" },
  warehouse: { label: "\uCC3D\uACE0", short: "\uCC3D" },
};

const getMenuDisplay = (menuKey: string, fallback: string) => MENU_DISPLAY[menuKey] ?? { label: fallback, short: fallback.slice(0, 1) || "-" };

const readSidebarCollapsed = () => {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
};

const writeSidebarCollapsed = (value: boolean) => {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(value));
  } catch {
    // localStorage may be unavailable in restricted browser contexts.
  }
};

const isRoutePathActive = (routePath: string, currentPath: string) =>
  Boolean(matchPath({ path: routePath, end: true }, currentPath));

const isKmsMenuRouteActive = (routeKey: string, currentPath: string) => {
  if (routeKey === "kms-home") return currentPath === "/kms" || currentPath === "/kms/";
  if (routeKey === "kms-posts") return currentPath === "/kms/posts" || currentPath.startsWith("/kms/posts/");
  if (routeKey === "kms-settings") return currentPath === "/kms/settings" || currentPath.startsWith("/kms/settings/");
  return false;
};

function AdminLayout() {
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(readSidebarCollapsed);

  const grouped = useMemo(() => {
    return (topMenus as TopMenuItem[]).map((top) => ({
      ...top,
      items: menus.filter((menu) => menu.menuKey === top.menuKey),
    }));
  }, []);

  const currentRoute = useMemo(() => {
    const found = menus.find((menu) => {
      const route = routeRegistryMap[menu.routeKey];
      if (menu.menuKey === "kms" && isKmsMenuRouteActive(menu.routeKey, location.pathname)) return true;
      if (route && isRoutePathActive(route.path, location.pathname)) return true;
      return (menu.children ?? []).some((child) => {
        const childRoute = routeRegistryMap[child.routeKey];
        return childRoute && isRoutePathActive(childRoute.path, location.pathname);
      });
    });
    return found ?? null;
  }, [location.pathname]);

  const isMenuActive = (menu: SideMenuItem) => {
    const route = routeRegistryMap[menu.routeKey];
    if (menu.menuKey === "kms" && isKmsMenuRouteActive(menu.routeKey, location.pathname)) return true;
    if (route && isRoutePathActive(route.path, location.pathname)) return true;
    return (menu.children ?? []).some((child) => {
      const childRoute = routeRegistryMap[child.routeKey];
      return childRoute && isRoutePathActive(childRoute.path, location.pathname);
    });
  };

  const activeGroupKey = currentRoute?.menuKey ?? null;

  useEffect(() => {
    if (!activeGroupKey) return;
    setOpenGroups((prev) => {
      if (Object.prototype.hasOwnProperty.call(prev, activeGroupKey)) {
        return prev;
      }
      return { ...prev, [activeGroupKey]: true };
    });
  }, [activeGroupKey]);

  const toggleGroup = (groupKey: string) => {
    if (isSidebarCollapsed) return;
    setOpenGroups((prev) => ({
      ...prev,
      [groupKey]: !prev[groupKey],
    }));
  };

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      writeSidebarCollapsed(next);
      return next;
    });
  };

  return (
    <div className={clsx("app-shell", isSidebarCollapsed && "app-shell--sidebar-collapsed")}>
      <aside className={clsx("side-nav", isSidebarCollapsed && "side-nav--collapsed")}>
        <div className="side-brand">
          <div className="side-brand-copy">
            <p className="side-brand-title">{isSidebarCollapsed ? "DrCT" : "DrCT\uC5D0\uC14B"}</p>
            <p className="side-brand-subtitle">AI Investment Research Office</p>
          </div>
          <button
            type="button"
            className="side-nav-toggle"
            aria-label={isSidebarCollapsed ? "\uBA54\uB274 \uD3BC\uCE58\uAE30" : "\uBA54\uB274 \uC811\uAE30"}
            title={isSidebarCollapsed ? "\uBA54\uB274 \uD3BC\uCE58\uAE30" : "\uBA54\uB274 \uC811\uAE30"}
            onClick={toggleSidebar}
          >
            {isSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {grouped.map((group) => {
          const display = getMenuDisplay(group.menuKey, group.title);
          const isExpanded = Object.prototype.hasOwnProperty.call(openGroups, group.menuKey)
            ? !!openGroups[group.menuKey]
            : activeGroupKey === group.menuKey;
          const isGroupActive = activeGroupKey === group.menuKey;
          const groupMenuId = `side-group-${group.menuKey}`;

          return (
            <div className={clsx("side-menu-group", isGroupActive && "side-menu-group-active")} key={group.menuKey} title={isSidebarCollapsed ? display.label : undefined}>
              <button
                type="button"
                className={clsx("side-menu-title-button", isExpanded && "side-menu-title-button-expanded", isGroupActive && "side-menu-title-button-active")}
                onClick={() => toggleGroup(group.menuKey)}
                aria-expanded={!isSidebarCollapsed && isExpanded}
                aria-controls={groupMenuId}
                title={isSidebarCollapsed ? display.label : `${display.label} \uBA54\uB274 ${isExpanded ? "\uC811\uAE30" : "\uD3BC\uCE58\uAE30"}`}
              >
                <span className="side-menu-title-short" aria-hidden="true">{display.short}</span>
                <span className="side-menu-title-text">{display.label}</span>
                <span className="side-menu-title-caret" aria-hidden="true">
                  {isExpanded ? "\u25BE" : "\u25B8"}
                </span>
              </button>

              <ul id={groupMenuId} className={clsx("side-menu-list", (!isExpanded || isSidebarCollapsed) && "side-menu-list-collapsed")}>
                {group.items.map((menu) => {
                  const route = routeRegistryMap[menu.routeKey];
                  if (!route) return null;
                  const children = menu.children ?? [];
                  const hasChildren = children.length > 0;
                  const parentActive = isMenuActive(menu);

                  return (
                    <li key={menu.routeKey}>
                      <NavLink
                        to={route.path}
                        title={menu.title}
                        className={({ isActive }) =>
                          clsx("side-menu-link", (menu.menuKey === "kms" ? parentActive : isActive || parentActive) && "side-menu-link-active")
                        }
                      >
                        <span>{menu.title}</span>
                      </NavLink>
                      {hasChildren ? (
                        <ul className="side-sub-menu-list">
                          {children.map((child) => {
                            const childRoute = routeRegistryMap[child.routeKey];
                            if (!childRoute) return null;
                            return (
                              <li key={child.routeKey}>
                                <NavLink
                                  to={childRoute.path}
                                  title={child.title}
                                  className={({ isActive }) => clsx("side-sub-menu-link", isActive && "side-sub-menu-link-active")}
                                >
                                  <span>{child.title}</span>
                                </NavLink>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
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
