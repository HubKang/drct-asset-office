import { apiRequest } from "@/services/api/apiClient";
import type {
  AssignThemeToTrendEventResponse,
  AssignThemeToTrendEventRequest,
  CollectMarketPriceSnapshotsRequest,
  CollectMarketPriceSnapshotsResponse,
  CollectMarketTrendEventsRequest,
  CollectMarketTrendEventsResponse,
  DailyThemeFlowResponse,
  DailyThemeFlowSummaryResponse,
  DailyThemeFlowStocksResponse,
  DetectEventsFromSnapshotRequest,
  DetectEventsFromSnapshotResponse,
  KiwoomConditionItem,
  KiwoomConditionPreviewRequest,
  KiwoomConditionPreviewResponse,
  KiwoomConditionResultItem,
  MarketPriceSnapshot,
  MarketTrendEvent,
  MarketScope,
  MonthlyThemeFlowCalendarResponse,
  MonthlyThemeFlowTrendResponse,
  SaveKiwoomConditionResultsRequest,
  SaveKiwoomConditionResultsResponse,
  KiwoomMarketEventListResponse,
  SaveKiwoomMarketEventsRequest,
  SaveKiwoomMarketEventsResponse,
  SyncKiwoomConditionsRequest,
  SyncKiwoomConditionsResponse,
  RefreshKiwoomConditionsResponse,
  ThemeStatus,
  MarketEventThemeLinkListResponse,
  ManualSupplyEventCandidateRequest,
  ManualSupplyEventCandidateResponse,
  AddMarketEventThemeLinkRequest,
  AddMarketEventThemeLinkResponse,
  RemoveMarketEventThemeLinkResponse,
  DeleteKiwoomMarketEventResponse,
  TrendDetectionSetting,
  UpdateKiwoomMarketEventRequest,
  UpdateKiwoomMarketEventResponse,
  UpdateDailyThemeRanksRequest,
  UpdateDailyThemeRanksResponse,
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
  collectMarketPriceSnapshots: (payload: CollectMarketPriceSnapshotsRequest) =>
    apiRequest<CollectMarketPriceSnapshotsResponse>("/market-trends/snapshots/collect", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getMarketPriceSnapshots: (params?: {
    market_scope?: MarketScope;
    keyword?: string;
    sort_by?: string;
    sort_order?: "ASC" | "DESC";
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.market_scope) search.set("market_scope", params.market_scope);
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.sort_by) search.set("sort_by", params.sort_by);
    if (params?.sort_order) search.set("sort_order", params.sort_order);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<MarketPriceSnapshot[]>(`/market-trends/snapshots${query ? `?${query}` : ""}`);
  },
  detectEventsFromSnapshot: (payload: DetectEventsFromSnapshotRequest) =>
    apiRequest<DetectEventsFromSnapshotResponse>("/market-trends/events/detect-from-snapshot", {
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
    apiRequest<AssignThemeToTrendEventResponse>(`/market-trends/events/${eventId}/theme`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createManualSupplyEventCandidate: (payload: ManualSupplyEventCandidateRequest) =>
    apiRequest<ManualSupplyEventCandidateResponse>("/market-trends/supply-event-candidates/manual", {
      method: "POST",
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
  syncKiwoomConditions: (payload: SyncKiwoomConditionsRequest) =>
    apiRequest<SyncKiwoomConditionsResponse>("/external/kiwoom/conditions/sync", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refreshKiwoomConditions: () =>
    apiRequest<RefreshKiwoomConditionsResponse>("/external/kiwoom/conditions/refresh", {
      method: "POST",
    }),
  getKiwoomConditions: () =>
    apiRequest<{ items: KiwoomConditionItem[] }>(`/external/kiwoom/conditions?_ts=${Date.now()}`),
  saveKiwoomConditionResults: (conditionSeq: string, payload: SaveKiwoomConditionResultsRequest) =>
    apiRequest<SaveKiwoomConditionResultsResponse>(`/external/kiwoom/conditions/${conditionSeq}/results`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getKiwoomConditionResults: (conditionSeq: string, limit = 200) =>
    apiRequest<{ items: KiwoomConditionResultItem[] }>(`/external/kiwoom/conditions/${conditionSeq}/results?limit=${limit}`),
  previewKiwoomConditionResults: (conditionSeq: string, payload: KiwoomConditionPreviewRequest) =>
    apiRequest<KiwoomConditionPreviewResponse>(`/external/kiwoom/conditions/${conditionSeq}/preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveKiwoomMarketEvents: (payload: SaveKiwoomMarketEventsRequest) =>
    apiRequest<SaveKiwoomMarketEventsResponse>("/external/kiwoom/market-events", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getKiwoomMarketEvents: (tradeDate: string, limit = 200) =>
    apiRequest<KiwoomMarketEventListResponse>(`/external/kiwoom/market-events?trade_date=${tradeDate}&limit=${limit}`),
  updateKiwoomMarketEvent: (eventId: number, payload: UpdateKiwoomMarketEventRequest) =>
    apiRequest<UpdateKiwoomMarketEventResponse>(`/external/kiwoom/market-events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteKiwoomMarketEvent: (eventId: number) =>
    apiRequest<DeleteKiwoomMarketEventResponse>(`/external/kiwoom/market-events/${eventId}`, {
      method: "DELETE",
    }),
  getKiwoomMarketEventThemes: (eventId: number) =>
    apiRequest<MarketEventThemeLinkListResponse>(`/external/kiwoom/market-events/${eventId}/themes`),
  addKiwoomMarketEventTheme: (eventId: number, payload: AddMarketEventThemeLinkRequest) =>
    apiRequest<AddMarketEventThemeLinkResponse>(`/external/kiwoom/market-events/${eventId}/themes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  removeKiwoomMarketEventTheme: (eventId: number, linkId: number) =>
    apiRequest<RemoveMarketEventThemeLinkResponse>(`/external/kiwoom/market-events/${eventId}/themes/${linkId}`, {
      method: "DELETE",
    }),
  getExternalDailyThemeFlow: (tradeDate: string) =>
    apiRequest<DailyThemeFlowSummaryResponse>(`/external/kiwoom/theme-flow/daily?trade_date=${tradeDate}`),
  updateDailyThemeRanks: (payload: UpdateDailyThemeRanksRequest) =>
    apiRequest<UpdateDailyThemeRanksResponse>("/external/kiwoom/theme-flow/daily/ranks", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  getExternalDailyThemeFlowStocks: (tradeDate: string, marketThemeId: number) =>
    apiRequest<DailyThemeFlowStocksResponse>(
      `/external/kiwoom/theme-flow/daily/${marketThemeId}/stocks?trade_date=${tradeDate}`,
    ),
  getExternalMonthlyThemeFlowCalendar: (month: string) =>
    apiRequest<MonthlyThemeFlowCalendarResponse>(`/external/kiwoom/theme-flow/monthly/calendar?month=${month}`),
  getExternalMonthlyThemeFlowTrend: (month: string, params?: { view_mode?: "THEME_GROUP" | "THEME"; theme_group_id?: number }) => {
    const search = new URLSearchParams({ month });
    if (params?.view_mode) search.set("view_mode", params.view_mode);
    if (params?.theme_group_id !== undefined) search.set("theme_group_id", String(params.theme_group_id));
    return apiRequest<MonthlyThemeFlowTrendResponse>(`/external/kiwoom/theme-flow/monthly/trend?${search.toString()}`);
  },
};
