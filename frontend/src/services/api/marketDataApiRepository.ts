import { apiRequest } from "@/services/api/apiClient";
import type { MarketDataCollectRequest, MarketDataCollectResponse, MarketDataCollectionRunListResponse } from "@/types/marketData";

export const marketDataApiRepository = {
  collect: (payload: MarketDataCollectRequest) =>
    apiRequest<MarketDataCollectResponse>("/market-data/collect", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 120000,
    }),
  listRuns: (params?: { limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<MarketDataCollectionRunListResponse>(`/market-data/collection-runs${query ? `?${query}` : ""}`);
  },
};
