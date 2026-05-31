export type NewsItem = {
  id: number;
  stock_id: number | null;
  stock_code?: string | null;
  stock_name?: string | null;
  title: string;
  source: string | null;
  url: string | null;
  published_at: string | null;
  collected_at: string;
  raw_text_path: string | null;
  summary: string | null;
  sentiment: string | null;
  importance_score: number;
  ai_summary?: string | null;
  ai_sentiment?: string | null;
  ai_importance_score?: number | null;
  ai_tags?: string | null;
  ai_processed_at?: string | null;
  ai_summary_error?: string | null;
  created_at: string;
};

export type NewsListParams = {
  stock_id?: number;
  stock_ids?: number[];
  keyword?: string;
  source?: string;
  limit?: number;
  offset?: number;
};

export type NewsListPageResponse = {
  items: NewsItem[];
  total_count: number;
  limit: number;
  offset: number;
};

export type NewsCollectionTarget = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  news_count: number;
  ai_processed_count: number;
  latest_collected_at: string | null;
};

export type NewsCollectRequest = {
  stock_id: number;
  providers: string[];
  display: number;
  sort: string;
};

export type NewsCollectWatchlistRequest = {
  providers: string[];
  display: number;
  sort: string;
};

export type NewsCollectSelectedWatchlistRequest = {
  stock_ids: number[];
  providers: string[];
  display: number;
  sort: string;
};

export type NewsCollectResponse = {
  collector_name: string;
  status: string;
  target: string;
  collected_count: number;
  saved_count: number;
  skipped_count: number;
  message: string;
};

export type NewsCollectSelectedItemResult = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  status: string;
  collected_count: number;
  saved_count: number;
  skipped_count: number;
  message: string | null;
};

export type NewsCollectSelectedResponse = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  skipped_count?: number;
  message: string;
  results: NewsCollectSelectedItemResult[];
};

export type NewsBulkDeleteResponse = {
  deleted: number;
  failed: number;
};
