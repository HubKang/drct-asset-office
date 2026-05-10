import { apiRequest } from "@/services/api/apiClient";
import type { Watchlist, WatchlistCreateInput, WatchlistUpdateInput } from "@/types/watchlist";

export const watchlistApiRepository = {
  list: (params?: { status?: string; keyword?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.keyword) search.set("keyword", params.keyword);
    const query = search.toString();
    return apiRequest<Watchlist[]>(`/watchlist${query ? `?${query}` : ""}`);
  },
  create: (payload: WatchlistCreateInput) =>
    apiRequest<Watchlist>("/watchlist", { method: "POST", body: JSON.stringify(payload) }),
  update: (watchlistId: number, payload: WatchlistUpdateInput) =>
    apiRequest<Watchlist>(`/watchlist/${watchlistId}`, { method: "PUT", body: JSON.stringify(payload) }),
  remove: (watchlistId: number) => apiRequest<void>(`/watchlist/${watchlistId}`, { method: "DELETE" }),
};
