import { apiRequest } from "@/services/api/apiClient";
import type {
  AssignThemeToTrendEventRequest,
  CollectMarketTrendEventsRequest,
  CollectMarketTrendEventsResponse,
  DailyThemeFlowResponse,
  MarketTrendEvent,
  MarketScope,
  ThemeStatus,
  TrendDetectionSetting,
  UpdateTrendDetectionSettingRequest,
} from "@/types/marketTrend";

export const marketTrendApiRepository = {
  getTrendDetectionSettings: () => apiRequest<TrendDetectionSetting>("/market-trends/detection-settings"),
  updateTrendDetectionSettings: (payload: UpdateTrendDetectionSettingRequest) =>
    apiRequest<TrendDetectionSetting>("/market-trends/detection-settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  collectMarketTrendEvents: (payload: CollectMarketTrendEventsRequest) =>
    apiRequest<CollectMarketTrendEventsResponse>("/market-trends/events/collect", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getMarketTrendEvents: (params?: {
    trade_date?: string;
    theme_status?: ThemeStatus;
    theme_id?: number;
    market_scope?: MarketScope;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.trade_date) search.set("trade_date", params.trade_date);
    if (params?.theme_status) search.set("theme_status", params.theme_status);
    if (params?.theme_id !== undefined) search.set("theme_id", String(params.theme_id));
    if (params?.market_scope) search.set("market_scope", params.market_scope);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<MarketTrendEvent[]>(`/market-trends/events${query ? `?${query}` : ""}`);
  },
  assignThemeToTrendEvent: (eventId: number, payload: AssignThemeToTrendEventRequest) =>
    apiRequest<MarketTrendEvent>(`/market-trends/events/${eventId}/theme`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getDailyThemeFlow: (params?: { trade_date?: string; only_supply_theme?: boolean; market_scope?: MarketScope }) => {
    const search = new URLSearchParams();
    if (params?.trade_date) search.set("trade_date", params.trade_date);
    if (params?.only_supply_theme !== undefined) search.set("only_supply_theme", String(params.only_supply_theme));
    if (params?.market_scope) search.set("market_scope", params.market_scope);
    const query = search.toString();
    return apiRequest<DailyThemeFlowResponse>(`/market-trends/daily-theme-flow${query ? `?${query}` : ""}`);
  },
};

