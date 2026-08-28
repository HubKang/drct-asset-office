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

const sample: NewsItem[] = [
  {
    id: 1,
    stock_id: 1,
    title: "삼성전자 관련 샘플 뉴스",
    url: "https://news.naver.com/",
    published_at: "2026-05-09T09:00:00+09:00",
    collected_at: "2026-05-09T09:10:00+09:00",
    summary: "샘플 요약 데이터입니다.",
    created_at: "2026-05-09T09:10:00+09:00",
  },
];

export const newsMockRepository = {
  async listNews(params?: NewsListParams): Promise<NewsItem[]> {
    let result = [...sample];
    if (params?.stock_id !== undefined) result = result.filter((n) => n.stock_id === params.stock_id);
    if (params?.stock_ids?.length) result = result.filter((n) => n.stock_id !== null && params.stock_ids?.includes(n.stock_id));
    if (params?.keyword) {
      const keyword = params.keyword;
      result = result.filter((n) => n.title.includes(keyword) || (n.summary || "").includes(keyword));
    }
    if (params?.summary_status === "summarized") result = result.filter((n) => Boolean(n.summary));
    if (params?.summary_status === "unsummarized") result = result.filter((n) => !n.summary);
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 50;
    return result.slice(offset, offset + limit);
  },
  async listCollectionTargets(): Promise<NewsCollectionTarget[]> {
    return [
      {
        stock_id: 1,
        stock_code: "005930",
        stock_name: "삼성전자",
        news_count: 1,
        summarized_count: 1,
        latest_collected_at: "2026-05-09T09:10:00+09:00",
      },
    ];
  },
  async listNewsPage(params?: NewsListParams): Promise<NewsListPageResponse> {
    const items = await this.listNews(params);
    const all = await this.listNews({ ...params, limit: 99999, offset: 0 });
    return {
      items,
      total_count: all.length,
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    };
  },
  async deleteNewsBulk(newsIds: number[]): Promise<NewsBulkDeleteResponse> {
    return { deleted: newsIds.length, failed: 0 };
  },
  async getNews(newsId: number): Promise<NewsItem> {
    const found = sample.find((n) => n.id === newsId);
    if (!found) throw new Error("news not found");
    return found;
  },
  async collectNewsForStock(payload: NewsCollectRequest): Promise<NewsCollectResponse> {
    return {
      collector_name: "naver_news_collector",
      status: "success",
      target: "MOCK",
      collected_count: payload.display,
      saved_count: 0,
      skipped_count: payload.display,
      message: "mock mode: collection not executed",
    };
  },
  async collectNewsForWatchlist(payload: NewsCollectWatchlistRequest): Promise<NewsCollectResponse> {
    return {
      collector_name: "naver_news_collector",
      status: "success",
      target: "watchlist",
      collected_count: payload.display,
      saved_count: 0,
      skipped_count: payload.display,
      message: "mock mode: watchlist collection not executed",
    };
  },
  async collectNewsForSelectedWatchlist(payload: NewsCollectSelectedWatchlistRequest): Promise<NewsCollectSelectedResponse> {
    return {
      requested_count: payload.stock_ids.length,
      success_count: payload.stock_ids.length,
      failed_count: 0,
      message: "mock mode: selected watchlist news collection not executed",
      results: payload.stock_ids.map((stockId) => ({
        stock_id: stockId,
        stock_code: `MOCK-${stockId}`,
        stock_name: `Mock Stock ${stockId}`,
        status: "success",
        collected_count: payload.display,
        saved_count: 0,
        skipped_count: payload.display,
        message: "mock success",
      })),
    };
  },
  async summarizeSelectedNews(newsIds: number[]): Promise<NewsSummarizeResponse> {
    return {
      requested: newsIds.length,
      summarized: newsIds.length,
      skipped_existing: 0,
      missing_url: 0,
      fetch_failed: 0,
      extraction_failed: 0,
      processing_failed: 0,
    };
  },
};
