import type { AiSummarizeResponse } from "@/types/analysis";
import type { NewsCollectRequest, NewsCollectResponse, NewsItem, NewsListParams } from "@/types/news";

const sample: NewsItem[] = [
  {
    id: 1,
    stock_id: 1,
    title: "삼성전자 관련 샘플 뉴스",
    source: "naver_news",
    url: "https://news.naver.com/",
    published_at: "2026-05-09T09:00:00+09:00",
    collected_at: "2026-05-09T09:10:00+09:00",
    raw_text_path: "data/raw/news/naver/005930_20260509_response.json",
    summary: "샘플 요약 데이터입니다.",
    sentiment: null,
    importance_score: 0,
    created_at: "2026-05-09T09:10:00+09:00",
  },
];

export const newsMockRepository = {
  async listNews(params?: NewsListParams): Promise<NewsItem[]> {
    let result = [...sample];
    if (params?.stock_id !== undefined) result = result.filter((n) => n.stock_id === params.stock_id);
    if (params?.keyword) result = result.filter((n) => n.title.includes(params.keyword as string) || (n.summary || "").includes(params.keyword as string));
    if (params?.source) result = result.filter((n) => (n.source || "") === params.source);
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 50;
    return result.slice(offset, offset + limit);
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
  async summarizeSelectedNews(newsIds: number[]): Promise<AiSummarizeResponse> {
    return {
      status: "success",
      target: "news",
      processed_count: newsIds.length,
      success_count: newsIds.length,
      failed_count: 0,
      skipped_count: 0,
      message: "mock mode: selected news summarize completed",
    };
  },
};
