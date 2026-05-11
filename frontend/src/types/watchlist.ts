export type Watchlist = {
  id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  security_type: string | null;
  status: string;
  interest_reason: string | null;
  entry_condition: string | null;
  exit_condition: string | null;
  risk_note: string | null;
  is_active: number;
  registered_at: string;
  updated_at: string;
};

export type WatchlistListParams = {
  status?: string;
  keyword?: string;
  market?: string;
  is_active?: number;
  limit?: number;
  offset?: number;
};

export type WatchlistCreateInput = {
  stock_id: number;
  status: string;
  interest_reason?: string;
  entry_condition?: string;
  exit_condition?: string;
  risk_note?: string;
};

export type WatchlistUpdateInput = {
  status?: string;
  interest_reason?: string;
  entry_condition?: string;
  exit_condition?: string;
  risk_note?: string;
  is_active?: number;
};

export type WatchlistBulkCreateInput = {
  stock_ids: number[];
  memo?: string;
};

export type WatchlistBulkCreateResponse = {
  requested_count: number;
  inserted_count: number;
  reactivated_count: number;
  skipped_count: number;
  message: string;
};
