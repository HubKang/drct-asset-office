export type MarketDataItemType = "INDEX" | "INDICATOR";

export type MarketDataCollectRequest = {
  mode: "SELECTED" | "INCREMENTAL_ALL";
  items?: Array<{ item_type: MarketDataItemType; item_code: string }> | null;
  triggered_by?: string | null;
};

export type MarketDataCollectResult = {
  item_type: MarketDataItemType;
  item_code: string;
  provider_code?: string | null;
  status: string;
  requested_from?: string | null;
  requested_to?: string | null;
  received_count: number;
  inserted_count: number;
  updated_count: number;
  unchanged_count: number;
  skipped_count: number;
  failed_count: number;
  error_type?: string | null;
  error_message?: string | null;
  elapsed_ms: number;
};

export type MarketDataCollectResponse = {
  run_id: number;
  run_type: string;
  status: string;
  target_count: number;
  success_count: number;
  waiting_count: number;
  inserted_count: number;
  updated_count: number;
  unchanged_count: number;
  skipped_count: number;
  failed_count: number;
  elapsed_ms: number;
  message: string;
  results: MarketDataCollectResult[];
};

export type MarketDataCollectionRun = {
  id: number;
  run_type: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  target_count: number;
  success_count: number;
  inserted_count: number;
  updated_count: number;
  unchanged_count: number;
  skipped_count: number;
  failed_count: number;
  elapsed_ms: number;
  triggered_by?: string | null;
  error_summary?: string | null;
};

export type MarketDataCollectionRunListResponse = {
  items: MarketDataCollectionRun[];
};

