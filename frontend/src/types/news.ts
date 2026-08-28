export type NewsItem = {
  id: number;
  stock_id: number | null;
  stock_code?: string | null;
  stock_name?: string | null;
  title: string;
  url: string | null;
  published_at: string | null;
  collected_at: string;
  summary: string | null;
  created_at: string;
};

export type NewsListParams = {
  stock_id?: number;
  stock_ids?: number[];
  keyword?: string;
  summary_status?: "summarized" | "unsummarized";
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
  summarized_count: number;
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
  mode?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  scanned_count?: number;
  matched_count?: number;
  name_mismatch_skipped?: number;
  duplicate_skipped?: number;
  excluded_skipped?: number;
  invalid_skipped?: number;
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
  mode?: string | null;
  from_date?: string | null;
  to_date?: string | null;
  scanned_count?: number;
  matched_count?: number;
  name_mismatch_skipped?: number;
  duplicate_skipped?: number;
  excluded_skipped?: number;
  invalid_skipped?: number;
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

export type NewsSummarizeResponse = {
  requested: number;
  summarized: number;
  skipped_existing: number;
  missing_url: number;
  fetch_failed: number;
  processing_failed: number;
};
