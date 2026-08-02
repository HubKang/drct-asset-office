import { apiRequest } from "@/services/api/apiClient";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeCandidateApproveResult,
  MarketThemeCandidateGenerateInput,
  MarketThemeCandidateGenerateResult,
  MarketThemeCandidateReviewInput,
  MarketThemeCreateInput,
  MarketThemeByStockResponse,
  MarketThemeLatestReturnDetail,
  MarketThemeListParams,
  MarketThemeMonthlyReturnParams,
  MarketThemeMonthlyReturnResponse,
  MarketThemePriceFlowJobStartResponse,
  MarketThemePriceFlowJobStatusResponse,
  MarketThemePriceFlowChartParams,
  MarketThemePriceFlowChartResponse,
  MarketThemeFlowChartResponse,
  MarketThemeFlowTrendParams,
  MarketThemeFlowTrendResponse,
  MarketThemeRangeReturnParams,
  MarketThemeReturnRefreshRequest,
  MarketThemeReturnRefreshResponse,
  MarketThemeStock,
  MarketThemeStockCreateInput,
  MarketThemeStockMemoResponse,
  MarketThemeStockSupplySummary,
  MarketThemeStockUpdateInput,
  MarketThemeUpdateInput,
} from "@/types/marketTheme";

export const marketThemeApiRepository = {
  list: (params?: MarketThemeListParams) => {
    const search = new URLSearchParams();
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.theme_type) search.set("theme_type", params.theme_type);
    if (params?.theme_level) search.set("theme_level", params.theme_level);
    if (params?.parent_theme_id !== undefined) search.set("parent_theme_id", String(params.parent_theme_id));
    if (params?.is_supply_theme !== undefined) search.set("is_supply_theme", String(params.is_supply_theme));
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<MarketTheme[]>(`/market-themes${query ? `?${query}` : ""}`);
  },
  get: (themeId: number) => apiRequest<MarketTheme>(`/market-themes/${themeId}`),
  create: (payload: MarketThemeCreateInput) =>
    apiRequest<MarketTheme>("/market-themes", { method: "POST", body: JSON.stringify(payload) }),
  update: (themeId: number, payload: MarketThemeUpdateInput) =>
    apiRequest<MarketTheme>(`/market-themes/${themeId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deactivate: (themeId: number) =>
    apiRequest<MarketTheme>(`/market-themes/${themeId}/deactivate`, { method: "PATCH" }),
  refreshReturns: (payload: MarketThemeReturnRefreshRequest = { scope: "all_active" }) =>
    apiRequest<MarketThemeReturnRefreshResponse>("/external/kiwoom/market-themes/returns-and-flows/refresh", { method: "POST", body: JSON.stringify(payload) }),
  startPriceFlowRefresh: (payload: MarketThemeReturnRefreshRequest = { scope: "all_active" }) =>
    apiRequest<MarketThemePriceFlowJobStartResponse>("/external/kiwoom/market-themes/returns-and-flows/jobs", { method: "POST", body: JSON.stringify(payload) }),
  getPriceFlowRefreshJob: (jobId: string) =>
    apiRequest<MarketThemePriceFlowJobStatusResponse>(`/external/kiwoom/market-themes/returns-and-flows/jobs/${encodeURIComponent(jobId)}`),
  getStockPriceFlowChart: (stockId: number, params: MarketThemePriceFlowChartParams) => {
    const search = new URLSearchParams();
    search.set("period", params.period);
    search.set("unit", params.unit);
    search.set("view", params.view);
    if (params.theme_id !== undefined) search.set("theme_id", String(params.theme_id));
    return apiRequest<MarketThemePriceFlowChartResponse>(
      `/external/kiwoom/market-themes/stocks/${stockId}/price-flow-chart?${search.toString()}`,
    );
  },
  getThemePriceFlowChart: (themeId: number, params: { period: "1M" | "3M" | "6M"; focus_date?: string }) => {
    const search = new URLSearchParams({ period: params.period });
    if (params.focus_date) search.set("focus_date", params.focus_date);
    return apiRequest<MarketThemeFlowChartResponse>(
      `/external/kiwoom/market-themes/${themeId}/price-flow-chart?${search.toString()}`,
    );
  },
  getThemeFlowTrend: (params: MarketThemeFlowTrendParams) => {
    const search = new URLSearchParams({
      end_date: params.end_date,
      recent_days: String(params.recent_days ?? 30),
      actor: params.actor,
      metric: params.metric,
      attribution: params.attribution,
    });
    if (params.theme_group_id !== undefined) search.set("theme_group_id", String(params.theme_group_id));
    if (params.search) search.set("search", params.search);
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.refresh) search.set("refresh", "true");
    return apiRequest<MarketThemeFlowTrendResponse>(
      `/external/kiwoom/market-themes/flow-trend?${search.toString()}`,
      { signal: params.signal },
    );
  },
  getLatestReturn: (themeId: number) => apiRequest<MarketThemeLatestReturnDetail>(`/external/kiwoom/market-themes/${themeId}/returns/latest`),
  getDailyReturn: (themeId: number, date: string) => apiRequest<MarketThemeLatestReturnDetail>(`/external/kiwoom/market-themes/${themeId}/returns/daily?date=${encodeURIComponent(date)}`),
  listMonthlyReturns: (params: MarketThemeMonthlyReturnParams) => {
    const search = new URLSearchParams();
    search.set("month", params.month);
    if (params.active_only !== undefined) search.set("active_only", String(params.active_only));
    if (params.theme_group_id !== undefined) search.set("theme_group_id", String(params.theme_group_id));
    if (params.keyword) search.set("keyword", params.keyword);
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.lookback_days !== undefined) search.set("lookback_days", String(params.lookback_days));
    return apiRequest<MarketThemeMonthlyReturnResponse>(`/external/kiwoom/market-themes/returns/monthly?${search.toString()}`);
  },
  listRangeReturns: (params: MarketThemeRangeReturnParams) => {
    const search = new URLSearchParams();
    search.set("end_date", params.end_date);
    if (params.days !== undefined) search.set("days", String(params.days));
    if (params.active_only !== undefined) search.set("active_only", String(params.active_only));
    if (params.theme_group_id !== undefined) search.set("theme_group_id", String(params.theme_group_id));
    if (params.keyword) search.set("keyword", params.keyword);
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.sort_by) search.set("sort_by", params.sort_by);
    return apiRequest<MarketThemeMonthlyReturnResponse>(`/external/kiwoom/market-themes/returns/range?${search.toString()}`);
  },
  listThemeStocks: (themeId: number) => apiRequest<MarketThemeStock[]>(`/market-themes/${themeId}/stocks`),
  getThemeStockSupplySummary: (themeId: number, stockId: number) =>
    apiRequest<MarketThemeStockSupplySummary>(`/market-themes/${themeId}/stocks/${stockId}/supply-summary`),
  createThemeStock: (themeId: number, payload: MarketThemeStockCreateInput) =>
    apiRequest<MarketThemeStock>(`/market-themes/${themeId}/stocks`, { method: "POST", body: JSON.stringify(payload) }),
  updateThemeStock: (mappingId: number, payload: MarketThemeStockUpdateInput) =>
    apiRequest<MarketThemeStock>(`/market-theme-stocks/${mappingId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deactivateThemeStock: (mappingId: number) =>
    apiRequest<MarketThemeStock>(`/market-theme-stocks/${mappingId}/deactivate`, { method: "PATCH" }),
  listThemesByStockCode: (stockCode: string) =>
    apiRequest<MarketThemeByStockResponse>(`/market-themes/by-stock/${encodeURIComponent(stockCode)}`),
  listStockMemos: (stockCode: string) =>
    apiRequest<MarketThemeStockMemoResponse>(`/market-themes/stocks/${encodeURIComponent(stockCode)}/memos`),
  listCandidates: (params?: { status?: string; theme_id?: number; stock_id?: number; candidate_source?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.theme_id !== undefined) search.set("theme_id", String(params.theme_id));
    if (params?.stock_id !== undefined) search.set("stock_id", String(params.stock_id));
    if (params?.candidate_source) search.set("candidate_source", params.candidate_source);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<MarketThemeCandidate[]>(`/market-theme-stock-candidates${query ? `?${query}` : ""}`);
  },
  generateCandidates: (payload: MarketThemeCandidateGenerateInput) =>
    apiRequest<MarketThemeCandidateGenerateResult>("/market-theme-stock-candidates/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approveCandidate: (candidateId: number) =>
    apiRequest<MarketThemeCandidateApproveResult>(`/market-theme-stock-candidates/${candidateId}/approve`, { method: "POST", body: JSON.stringify({}) }),
  rejectCandidate: (candidateId: number, payload: MarketThemeCandidateReviewInput) =>
    apiRequest<MarketThemeCandidate>(`/market-theme-stock-candidates/${candidateId}/reject`, { method: "POST", body: JSON.stringify(payload) }),
  ignoreCandidate: (candidateId: number, payload: MarketThemeCandidateReviewInput) =>
    apiRequest<MarketThemeCandidate>(`/market-theme-stock-candidates/${candidateId}/ignore`, { method: "POST", body: JSON.stringify(payload) }),
};
