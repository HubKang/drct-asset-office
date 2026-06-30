import { apiRequest } from "@/services/api/apiClient";
import type {
  MarketIndexCollectRequest,
  MarketIndexCollectResponse,
  MarketIndexCompareResponse,
  MarketIndexDailyPriceListResponse,
  MarketIndexListResponse,
  MarketIndexProviderMapping,
  MarketIndexProviderMappingListResponse,
  MarketIndexProviderCodeListResponse,
  ProviderCodeCollectRequest,
  ProviderCodeCollectResponse,
  ProviderMappingTestRequest,
  ProviderMappingTestResult,
  ProviderMappingUpsertRequest,
  SectorCodeAutoMatchResponse,
} from "@/types/marketIndex";

export const marketIndexApiRepository = {
  list: (params?: { active_only?: boolean; category?: string }) => {
    const search = new URLSearchParams();
    if (params?.active_only !== undefined) search.set("active_only", String(params.active_only));
    if (params?.category) search.set("category", params.category);
    const query = search.toString();
    return apiRequest<MarketIndexListResponse>(`/market-indexes${query ? `?${query}` : ""}`);
  },
  collect: (payload: MarketIndexCollectRequest) =>
    apiRequest<MarketIndexCollectResponse>("/market-indexes/collect", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 120000,
    }),
  listDailyPrices: (indexCode: string, params?: { start_date?: string; end_date?: string }) => {
    const search = new URLSearchParams();
    if (params?.start_date) search.set("start_date", params.start_date);
    if (params?.end_date) search.set("end_date", params.end_date);
    const query = search.toString();
    return apiRequest<MarketIndexDailyPriceListResponse>(
      `/market-indexes/${encodeURIComponent(indexCode)}/daily-prices${query ? `?${query}` : ""}`,
    );
  },
  collectProviderCodes: (payload: ProviderCodeCollectRequest = {}) =>
    apiRequest<ProviderCodeCollectResponse>("/market-indexes/provider-codes/collect", {
      method: "POST",
      body: JSON.stringify({ provider: payload.provider || "KIWOOM_REST", market_types: payload.market_types || ["0", "1", "2"] }),
      timeoutMs: 120000,
    }),
  listProviderCodes: (params?: { provider?: string; market_type?: string; keyword?: string }) => {
    const search = new URLSearchParams();
    if (params?.provider) search.set("provider", params.provider);
    if (params?.market_type) search.set("market_type", params.market_type);
    if (params?.keyword) search.set("keyword", params.keyword);
    const query = search.toString();
    return apiRequest<MarketIndexProviderCodeListResponse>(`/market-indexes/provider-codes${query ? `?${query}` : ""}`);
  },
  autoMatchSectorCodes: () =>
    apiRequest<SectorCodeAutoMatchResponse>("/market-indexes/provider-mappings/auto-match-sector-codes", { method: "POST" }),
  listProviderMappings: () => apiRequest<MarketIndexProviderMappingListResponse>("/market-indexes/provider-mappings"),
  upsertProviderMapping: (indexCode: string, payload: ProviderMappingUpsertRequest) =>
    apiRequest<MarketIndexProviderMapping>(`/market-indexes/${encodeURIComponent(indexCode)}/provider-mapping`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  testProviderMapping: (indexCode: string, payload: ProviderMappingTestRequest) =>
    apiRequest<ProviderMappingTestResult>(`/market-indexes/${encodeURIComponent(indexCode)}/provider-mapping/test`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 120000,
    }),
  activateProviderMapping: (indexCode: string) =>
    apiRequest<MarketIndexProviderMapping>(`/market-indexes/${encodeURIComponent(indexCode)}/provider-mapping/activate`, { method: "POST" }),
  compare: (params?: { index_codes?: string[]; start_date?: string; end_date?: string; normalize?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.index_codes?.length) search.set("index_codes", params.index_codes.join(","));
    if (params?.start_date) search.set("start_date", params.start_date);
    if (params?.end_date) search.set("end_date", params.end_date);
    if (params?.normalize !== undefined) search.set("normalize", String(params.normalize));
    const query = search.toString();
    return apiRequest<MarketIndexCompareResponse>(`/market-indexes/compare${query ? `?${query}` : ""}`);
  },
};
