import { apiRequest } from "@/services/api/apiClient";
import type {
  Stock,
  StockCodeNormalizeResponse,
  StockCreateInput,
  StockListParams,
  StockUpdateInput,
} from "@/types/stock";
import type { StockSyncRequest, StockSyncResponse } from "@/types/stockSync";

export const stockApiRepository = {
  list: (params?: string | StockListParams) => {
    const search = new URLSearchParams();
    if (typeof params === "string") {
      if (params) search.set("keyword", params);
    } else if (params) {
      if (params.keyword) search.set("keyword", params.keyword);
      if (params.is_active !== undefined) search.set("is_active", String(params.is_active));
      if (params.market) search.set("market", params.market);
      if (params.security_type) search.set("security_type", params.security_type);
      if (params.limit !== undefined) search.set("limit", String(params.limit));
      if (params.offset !== undefined) search.set("offset", String(params.offset));
    }
    const query = search.toString();
    return apiRequest<Stock[]>(`/stocks${query ? `?${query}` : ""}`);
  },
  create: (payload: StockCreateInput) => apiRequest<Stock>("/stocks", { method: "POST", body: JSON.stringify(payload) }),
  update: (stockId: number, payload: StockUpdateInput) =>
    apiRequest<Stock>(`/stocks/${stockId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deactivate: (stockId: number) => apiRequest<Stock>(`/stocks/${stockId}`, { method: "DELETE" }),
  normalizeCodes: (dryRun = false) =>
    apiRequest<StockCodeNormalizeResponse>("/stocks/normalize-codes", {
      method: "POST",
      body: JSON.stringify({ dry_run: dryRun }),
    }),
  syncStocks: (payload: StockSyncRequest) =>
    apiRequest<StockSyncResponse>("/stocks/sync", { method: "POST", body: JSON.stringify(payload), timeoutMs: 120000 }),
};
