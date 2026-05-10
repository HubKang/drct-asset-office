export type Watchlist = {
  id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  status: string;
  interest_reason: string | null;
  entry_condition: string | null;
  exit_condition: string | null;
  risk_note: string | null;
  registered_at: string;
  updated_at: string;
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
};
