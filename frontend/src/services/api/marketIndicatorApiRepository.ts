import { apiRequest } from "@/services/api/apiClient";
import type {
  EcosDiscoverCandidatesRequest,
  EcosDiscoverCandidatesResponse,
  EcosDiscoverMappingCandidatesRequest,
  EcosDiscoverMappingCandidatesResponse,
  EcosItemListResponse,
  EcosMappingCandidateTestRequest,
  EcosTableListResponse,
  EcosTableSearchResponse,
  ExternalProviderStatusListResponse,
  MarketIndicator,
  MarketIndicatorCollectRequest,
  MarketIndicatorCollectResponse,
  MarketIndicatorListResponse,
  MarketIndicatorProviderMapping,
  MarketIndicatorProviderMappingListResponse,
  MarketIndicatorReadinessListResponse,
  MarketIndicatorProviderMappingTestRequest,
  MarketIndicatorProviderMappingTestResponse,
  MarketIndicatorProviderMappingUpsertRequest,
  MarketIndicatorValueResponse,
} from "@/types/marketIndicator";

export const marketIndicatorApiRepository = {
  list: (params?: { category?: string; active_only?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.category) search.set("category", params.category);
    if (params?.active_only !== undefined) search.set("active_only", String(params.active_only));
    const query = search.toString();
    return apiRequest<MarketIndicatorListResponse>(`/market-indicators-data${query ? `?${query}` : ""}`);
  },
  get: (indicatorCode: string) => apiRequest<MarketIndicator>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}`),
  values: (indicatorCode: string, params?: { start_date?: string; end_date?: string }) => {
    const search = new URLSearchParams();
    if (params?.start_date) search.set("start_date", params.start_date);
    if (params?.end_date) search.set("end_date", params.end_date);
    const query = search.toString();
    return apiRequest<MarketIndicatorValueResponse>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}/values${query ? `?${query}` : ""}`);
  },
  providerMappings: () => apiRequest<MarketIndicatorProviderMappingListResponse>("/market-indicators-data/provider-mappings"),
  readiness: (indicatorCodes?: string[]) => {
    const search = new URLSearchParams();
    indicatorCodes?.forEach((code) => search.append("indicator_codes", code));
    const query = search.toString();
    return apiRequest<MarketIndicatorReadinessListResponse>(`/market-indicators-data/readiness${query ? `?${query}` : ""}`);
  },
  providerStatuses: () => apiRequest<ExternalProviderStatusListResponse>("/market-indicators-data/providers/status"),
  ecosTableList: (params?: { parent_stat_code?: string; start_index?: number; end_index?: number }) => {
    const search = new URLSearchParams();
    if (params?.parent_stat_code) search.set("parent_stat_code", params.parent_stat_code);
    if (params?.start_index !== undefined) search.set("start_index", String(params.start_index));
    if (params?.end_index !== undefined) search.set("end_index", String(params.end_index));
    const query = search.toString();
    return apiRequest<EcosTableListResponse>(`/market-indicators-data/ecos/table-list${query ? `?${query}` : ""}`);
  },
  ecosTableSearch: (params: { keyword: string; parent_stat_code?: string; cycle?: string; only_searchable?: boolean; max_depth?: number }) => {
    const search = new URLSearchParams();
    search.set("keyword", params.keyword);
    if (params.parent_stat_code) search.set("parent_stat_code", params.parent_stat_code);
    if (params.cycle) search.set("cycle", params.cycle);
    if (params.only_searchable !== undefined) search.set("only_searchable", String(params.only_searchable));
    if (params.max_depth !== undefined) search.set("max_depth", String(params.max_depth));
    return apiRequest<EcosTableSearchResponse>(`/market-indicators-data/ecos/table-search?${search.toString()}`);
  },
  discoverCandidates: (payload: EcosDiscoverCandidatesRequest = {}) =>
    apiRequest<EcosDiscoverCandidatesResponse>("/market-indicators-data/ecos/discover-candidates", { method: "POST", body: JSON.stringify(payload) }),
  discoverMappingCandidates: (payload: EcosDiscoverMappingCandidatesRequest = {}) =>
    apiRequest<EcosDiscoverMappingCandidatesResponse>("/market-indicators-data/ecos/discover-mapping-candidates", { method: "POST", body: JSON.stringify(payload) }),
  ecosItemList: (params: { stat_code: string; start_index?: number; end_index?: number }) => {
    const search = new URLSearchParams();
    search.set("stat_code", params.stat_code);
    if (params.start_index !== undefined) search.set("start_index", String(params.start_index));
    if (params.end_index !== undefined) search.set("end_index", String(params.end_index));
    return apiRequest<EcosItemListResponse>(`/market-indicators-data/ecos/item-list?${search.toString()}`);
  },
  upsertProviderMapping: (indicatorCode: string, payload: MarketIndicatorProviderMappingUpsertRequest) =>
    apiRequest<MarketIndicatorProviderMapping>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}/provider-mapping`, { method: "PUT", body: JSON.stringify(payload) }),
  testProviderMapping: (indicatorCode: string, payload: MarketIndicatorProviderMappingTestRequest) =>
    apiRequest<MarketIndicatorProviderMappingTestResponse>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}/provider-mapping/test`, { method: "POST", body: JSON.stringify(payload) }),
  testCandidate: (indicatorCode: string, payload: EcosMappingCandidateTestRequest) =>
    apiRequest<MarketIndicatorProviderMappingTestResponse>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}/provider-mapping/test-candidate`, { method: "POST", body: JSON.stringify(payload) }),
  activateProviderMapping: (indicatorCode: string) =>
    apiRequest<MarketIndicatorProviderMapping>(`/market-indicators-data/${encodeURIComponent(indicatorCode)}/provider-mapping/activate`, { method: "POST" }),
  collect: (payload: MarketIndicatorCollectRequest = {}) =>
    apiRequest<MarketIndicatorCollectResponse>("/market-indicators-data/collect", { method: "POST", body: JSON.stringify(payload) }),
};
