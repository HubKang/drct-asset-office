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
  MarketThemeListParams,
  MarketThemeStock,
  MarketThemeStockCreateInput,
  MarketThemeStockUpdateInput,
  MarketThemeUpdateInput,
} from "@/types/marketTheme";

export const marketThemeApiRepository = {
  list: (params?: MarketThemeListParams) => {
    const search = new URLSearchParams();
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.theme_type) search.set("theme_type", params.theme_type);
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
  listThemeStocks: (themeId: number) => apiRequest<MarketThemeStock[]>(`/market-themes/${themeId}/stocks`),
  createThemeStock: (themeId: number, payload: MarketThemeStockCreateInput) =>
    apiRequest<MarketThemeStock>(`/market-themes/${themeId}/stocks`, { method: "POST", body: JSON.stringify(payload) }),
  updateThemeStock: (mappingId: number, payload: MarketThemeStockUpdateInput) =>
    apiRequest<MarketThemeStock>(`/market-theme-stocks/${mappingId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deactivateThemeStock: (mappingId: number) =>
    apiRequest<MarketThemeStock>(`/market-theme-stocks/${mappingId}/deactivate`, { method: "PATCH" }),
  listThemesByStockCode: (stockCode: string) =>
    apiRequest<MarketThemeByStockResponse>(`/market-themes/by-stock/${encodeURIComponent(stockCode)}`),
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
