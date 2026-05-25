export type Stock = {
  id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  sector: string | null;
  industry: string | null;
  isin_code: string | null;
  corp_name: string | null;
  corp_reg_no: string | null;
  last_synced_at: string | null;
  source: string | null;
  security_type: string | null;
  is_active: number;
  created_at: string;
  updated_at: string;
};

export type StockListParams = {
  keyword?: string;
  is_active?: number;
  market?: string;
  security_type?: string;
  limit?: number;
  offset?: number;
};

export type StockCreateInput = {
  stock_code: string;
  stock_name: string;
  market?: string;
  sector?: string;
  industry?: string;
  security_type?: string;
};

export type StockUpdateInput = {
  stock_code?: string;
  stock_name?: string;
  market?: string;
  sector?: string;
  industry?: string;
  security_type?: string;
  is_active?: number;
};

export type StockCodeNormalizeItem = {
  stock_id: number;
  stock_name: string;
  old_code: string;
  new_code: string;
  status: string;
};

export type StockCodeNormalizeResponse = {
  dry_run: boolean;
  target_count: number;
  updated_count: number;
  duplicate_conflict_count: number;
  items: StockCodeNormalizeItem[];
};
