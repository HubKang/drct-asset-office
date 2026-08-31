import { apiRequest } from "@/services/api/apiClient";
import type { UsMarketRefreshResponse, UsTheme, UsThemeDashboardSummary, UsThemeGroup, UsThemeGroupInput, UsThemeInput, UsThemeReturnDetail, UsThemeReturnList, UsThemeStock, UsThemeStockInput, UsThemeSummary, UsThemeTreemap, UsThemeTrend, UsStockCharts } from "@/types/usMarketTheme";

export const usMarketThemeApiRepository = {
  summary: () => apiRequest<UsThemeSummary>("/us-market-themes/summary"),
  dashboardSummary: () => apiRequest<UsThemeDashboardSummary>("/us-market-themes/dashboard-summary", { cache: "no-store" }),
  listGroups: () => apiRequest<UsThemeGroup[]>("/us-market-themes/groups"),
  createGroup: (payload: UsThemeGroupInput) => apiRequest<UsThemeGroup>("/us-market-themes/groups", { method: "POST", body: JSON.stringify(payload) }),
  updateGroup: (id: number, payload: Partial<UsThemeGroupInput>) => apiRequest<UsThemeGroup>(`/us-market-themes/groups/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listThemes: (params: { group_id?: number; active?: number; keyword?: string } = {}) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => { if (value !== undefined && value !== "") search.set(key, String(value)); });
    const query = search.toString();
    return apiRequest<UsTheme[]>(`/us-market-themes/themes${query ? `?${query}` : ""}`);
  },
  createTheme: (payload: UsThemeInput) => apiRequest<UsTheme>("/us-market-themes/themes", { method: "POST", body: JSON.stringify(payload) }),
  updateTheme: (id: number, payload: Partial<UsThemeInput>) => apiRequest<UsTheme>(`/us-market-themes/themes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  listThemeStocks: (themeId: number) => apiRequest<UsThemeStock[]>(`/us-market-themes/themes/${themeId}/stocks`),
  linkStock: (themeId: number, payload: UsThemeStockInput) => apiRequest<UsThemeStock>(`/us-market-themes/themes/${themeId}/stocks`, { method: "POST", body: JSON.stringify(payload) }),
  updateMapping: (mappingId: number, payload: Partial<Omit<UsThemeStockInput, "us_stock_id"> & { active: number }>) => apiRequest<UsThemeStock>(`/us-market-themes/mappings/${mappingId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  unlinkMapping: (mappingId: number) => apiRequest<UsThemeStock>(`/us-market-themes/mappings/${mappingId}`, { method: "DELETE" }),
  charts: (stockId: number) => apiRequest<UsStockCharts>(`/us-stocks/${stockId}/naver-charts`, { timeoutMs: 8000, cache: "no-store" }),
  latestReturns: () => apiRequest<UsThemeReturnList>("/us-market-themes/returns/latest"),
  treemap: (signal?: AbortSignal) => apiRequest<UsThemeTreemap>("/us-market-themes/treemap", { signal, cache: "no-store" }),
  trend: (period: 20 | 30 | 60, options: { end_date?: string; active?: number | null } = {}) => {
    const search = new URLSearchParams({ period: String(period) });
    if (options.end_date) search.set("end_date", options.end_date);
    if (options.active !== null && options.active !== undefined) search.set("active", String(options.active));
    return apiRequest<UsThemeTrend>(`/us-market-themes/returns/trend?${search.toString()}`);
  },
  returnDetail: (themeId: number, tradeDate: string) => apiRequest<UsThemeReturnDetail>(`/us-market-themes/themes/${themeId}/returns/${tradeDate}`),
  detail: (themeId: number, tradeDate?: string | null) => {
    const query = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : "";
    return apiRequest<UsThemeReturnDetail>(`/us-market-themes/themes/${themeId}/detail${query}`);
  },
  refresh: (mode: "INCREMENTAL" | "BACKFILL" = "INCREMENTAL") => apiRequest<UsMarketRefreshResponse>("/us-market-themes/refresh", { method: "POST", body: JSON.stringify({ mode, trading_days: 260 }), timeoutMs: 300000 }),
  refreshGroup: (groupId: number) => apiRequest<UsMarketRefreshResponse>(`/us-market-themes/groups/${groupId}/refresh`, { method: "POST", body: JSON.stringify({ mode: "INCREMENTAL", trading_days: 260 }), timeoutMs: 300000 }),
  refreshTheme: (themeId: number) => apiRequest<UsMarketRefreshResponse>(`/us-market-themes/themes/${themeId}/refresh`, { method: "POST", body: JSON.stringify({ mode: "INCREMENTAL", trading_days: 260 }), timeoutMs: 300000 }),
};
