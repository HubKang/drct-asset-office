import { apiRequest } from "@/services/api/apiClient";
import type { AiSummarizeResponse } from "@/types/analysis";
import type {
  NewsCollectRequest,
  NewsCollectionTarget,
  NewsCollectResponse,
  NewsCollectSelectedResponse,
  NewsCollectSelectedWatchlistRequest,
  NewsCollectWatchlistRequest,
  NewsItem,
  NewsListParams,
} from "@/types/news";

export const newsApiRepository = {
  listNews: (params?: NewsListParams) => {
    const search = new URLSearchParams();
    if (params?.stock_id !== undefined) search.set("stock_id", String(params.stock_id));
    if (params?.stock_ids?.length) search.set("stock_ids", params.stock_ids.join(","));
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.source) search.set("source", params.source);
    search.set("limit", String(params?.limit ?? 50));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<NewsItem[]>(`/news?${search.toString()}`);
  },
  listCollectionTargets: () => apiRequest<NewsCollectionTarget[]>("/news/collection-targets"),
  getNews: (newsId: number) => apiRequest<NewsItem>(`/news/${newsId}`),
  collectNewsForStock: (payload: NewsCollectRequest) =>
    apiRequest<NewsCollectResponse>("/collectors/news", { method: "POST", body: JSON.stringify(payload) }),
  collectNewsForWatchlist: (payload: NewsCollectWatchlistRequest) =>
    apiRequest<NewsCollectResponse>("/collectors/news/watchlist", { method: "POST", body: JSON.stringify(payload) }),
  collectNewsForSelectedWatchlist: (payload: NewsCollectSelectedWatchlistRequest) =>
    apiRequest<NewsCollectSelectedResponse>("/collectors/news/watchlist/selected", { method: "POST", body: JSON.stringify(payload) }),
  summarizeSelectedNews: (newsIds: number[]) =>
    apiRequest<AiSummarizeResponse>("/analysis/news/ai-summarize", {
      method: "POST",
      body: JSON.stringify({
        news_ids: newsIds,
        only_unprocessed: false,
        overwrite: true,
        limit: newsIds.length || 1,
      }),
    }),
};
