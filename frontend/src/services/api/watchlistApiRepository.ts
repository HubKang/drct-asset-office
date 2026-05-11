import { apiRequest } from "@/services/api/apiClient";
import type {
  Watchlist,
  WatchlistBulkCreateInput,
  WatchlistBulkCreateResponse,
  WatchlistCreateInput,
  WatchlistListParams,
  WatchlistUpdateInput,
} from "@/types/watchlist";

export const watchlistApiRepository = {
  list: (params?: WatchlistListParams) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.market) search.set("market", params.market);
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<Watchlist[]>(`/watchlist${query ? `?${query}` : ""}`);
  },
  listStockIds: async () => {
    const result = await apiRequest<{ stock_ids: number[] }>("/watchlist/stock-ids");
    return result.stock_ids;
  },
  bulkAdd: (payload: WatchlistBulkCreateInput) =>
    apiRequest<WatchlistBulkCreateResponse>("/watchlist/bulk", { method: "POST", body: JSON.stringify(payload) }),
  create: (payload: WatchlistCreateInput) =>
    apiRequest<Watchlist>("/watchlist", { method: "POST", body: JSON.stringify(payload) }),
  update: (watchlistId: number, payload: WatchlistUpdateInput) =>
    apiRequest<Watchlist>(`/watchlist/${watchlistId}`, { method: "PUT", body: JSON.stringify(payload) }),
  remove: (watchlistId: number) => apiRequest<void>(`/watchlist/${watchlistId}`, { method: "DELETE" }),
};
