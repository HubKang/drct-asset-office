import { apiRequest } from "@/services/api/apiClient";
import type {
  NewsCollectRequest,
  NewsCollectionTarget,
  NewsCollectResponse,
  NewsCollectSelectedResponse,
  NewsCollectSelectedWatchlistRequest,
  NewsCollectWatchlistRequest,
  NewsBulkDeleteResponse,
  NewsItem,
  NewsListPageResponse,
  NewsListParams,
  NewsSummarizeResponse,
} from "@/types/news";

export const newsApiRepository = {
  listNews: (params?: NewsListParams) => {
    const search = new URLSearchParams();
    if (params?.stock_id !== undefined) search.set("stock_id", String(params.stock_id));
    if (params?.stock_ids?.length) search.set("stock_ids", params.stock_ids.join(","));
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.summary_status) search.set("summary_status", params.summary_status);
    search.set("limit", String(params?.limit ?? 50));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<NewsItem[]>(`/news?${search.toString()}`);
  },
  listCollectionTargets: () => apiRequest<NewsCollectionTarget[]>("/news/collection-targets"),
  listNewsPage: (params?: NewsListParams) => {
    const search = new URLSearchParams();
    if (params?.stock_id !== undefined) search.set("stock_id", String(params.stock_id));
    if (params?.stock_ids?.length) search.set("stock_ids", params.stock_ids.join(","));
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.summary_status) search.set("summary_status", params.summary_status);
    search.set("limit", String(params?.limit ?? 20));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<NewsListPageResponse>(`/news/page?${search.toString()}`);
  },
  deleteNewsBulk: (newsIds: number[]) =>
    apiRequest<NewsBulkDeleteResponse>("/news/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ news_ids: newsIds }),
    }),
  getNews: (newsId: number) => apiRequest<NewsItem>(`/news/${newsId}`),
  collectNewsForStock: (payload: NewsCollectRequest) =>
    apiRequest<NewsCollectResponse>("/collectors/news", { method: "POST", body: JSON.stringify(payload) }),
  collectNewsForWatchlist: (payload: NewsCollectWatchlistRequest) =>
    apiRequest<NewsCollectResponse>("/collectors/news/watchlist", { method: "POST", body: JSON.stringify(payload) }),
  collectNewsForSelectedWatchlist: (payload: NewsCollectSelectedWatchlistRequest) =>
    apiRequest<NewsCollectSelectedResponse>("/collectors/news/watchlist/selected", { method: "POST", body: JSON.stringify(payload) }),
  summarizeSelectedNews: (newsIds: number[]) =>
    apiRequest<NewsSummarizeResponse>("/news/summarize", {
      method: "POST",
      body: JSON.stringify({ news_ids: newsIds }),
    }),
};
