import { apiRequest } from "@/services/api/apiClient";
import type {
  ExternalProviderStatusListResponse,
  MarketIndicator,
  MarketIndicatorListResponse,
  MarketIndicatorProviderMappingListResponse,
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
  providerStatuses: () => apiRequest<ExternalProviderStatusListResponse>("/market-indicators-data/providers/status"),
};
