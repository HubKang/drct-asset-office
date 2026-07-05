import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, matchPath, useLocation } from "react-router-dom";
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

const menus = sideMenus as SideMenuItem[];

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

  const grouped = useMemo(() => {
    return topMenus.map((top) => ({
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
    setOpenGroups((prev) => ({
      ...prev,
      [groupKey]: !prev[groupKey],
    }));
  };

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="side-brand">
          <p className="side-brand-title">DrCT에셋</p>
          <p className="side-brand-subtitle">AI Investment Research Office</p>
        </div>

        {grouped.map((group) => {
          const isExpanded = Object.prototype.hasOwnProperty.call(openGroups, group.menuKey)
            ? !!openGroups[group.menuKey]
            : activeGroupKey === group.menuKey;
          const groupMenuId = `side-group-${group.menuKey}`;

          return (
            <div className="side-menu-group" key={group.menuKey}>
              <button
                type="button"
                className={clsx("side-menu-title-button", isExpanded && "side-menu-title-button-expanded")}
                onClick={() => toggleGroup(group.menuKey)}
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
                  const children = menu.children ?? [];
                  const hasChildren = children.length > 0;
                  const parentActive = isMenuActive(menu);

                  return (
                    <li key={menu.routeKey}>
                      <NavLink
                        to={route.path}
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
