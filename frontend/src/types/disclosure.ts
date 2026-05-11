export type Disclosure = {
  id: number;
  stock_id: number;
  stock_code?: string | null;
  stock_name?: string | null;
  dart_receipt_no: string | null;
  disclosure_title: string;
  disclosure_type: string | null;
  disclosed_at: string | null;
  url: string | null;
  raw_text_path: string | null;
  summary: string | null;
  importance_score: number;
  ai_summary?: string | null;
  ai_importance_score?: number | null;
  ai_tags?: string | null;
  ai_risk_level?: string | null;
  ai_event_type?: string | null;
  ai_processed_at?: string | null;
  ai_summary_error?: string | null;
  created_at: string;
};

export type DisclosureListParams = {
  stock_id?: number;
  keyword?: string;
  disclosure_type?: string;
  limit?: number;
  offset?: number;
};

export type DisclosureCollectRequest = {
  stock_id: number;
  days: number;
  page_count: number;
};

export type DisclosureCollectWatchlistRequest = {
  days: number;
  page_count: number;
};

export type DisclosureCollectSelectedWatchlistRequest = {
  stock_ids: number[];
  days: number;
  page_count: number;
};

export type DisclosureCollectResponse = {
  collector_name: string;
  status: string;
  target: string;
  collected_count: number;
  saved_count: number;
  skipped_count: number;
  message: string;
};

export type DisclosureCollectSelectedItemResult = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  status: string;
  collected_count: number;
  saved_count: number;
  skipped_count: number;
  message: string | null;
};

export type DisclosureCollectSelectedResponse = {
  requested_count: number;
  success_count: number;
  failed_count: number;
  skipped_count?: number;
  message: string;
  results: DisclosureCollectSelectedItemResult[];
};
