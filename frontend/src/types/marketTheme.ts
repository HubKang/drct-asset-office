export type MarketThemeType = "industry" | "theme" | "custom" | "telegram";
export type MarketThemeLevel = "THEME_GROUP" | "THEME";

export type MarketTheme = {
  id: number;
  theme_name: string;
  theme_code: string;
  theme_type: MarketThemeType;
  theme_level: MarketThemeLevel;
  description: string | null;
  keywords: string[];
  parent_theme_id: number | null;
  parent_theme_name?: string | null;
  is_supply_theme: number;
  is_active: number;
  sort_order: number;
  stock_count: number;
  linked_stock_count?: number;
  keyword_count?: number;
  child_theme_count?: number;
  supply_child_theme_count?: number;
  created_at: string;
  updated_at: string;
};

export type MarketThemeCreateInput = {
  theme_name: string;
  theme_code?: string;
  theme_type: MarketThemeType;
  theme_level?: MarketThemeLevel;
  description?: string | null;
  keywords: string[];
  parent_theme_id?: number | null;
  is_supply_theme?: number;
  sort_order?: number;
  is_active?: number;
};

export type MarketThemeUpdateInput = {
  theme_name: string;
  theme_type: MarketThemeType;
  theme_level?: MarketThemeLevel;
  description?: string | null;
  keywords: string[];
  parent_theme_id?: number | null;
  is_supply_theme?: number;
  sort_order?: number;
  is_active?: number;
};

export type MarketThemeListParams = {
  is_active?: number;
  theme_type?: string;
  theme_level?: MarketThemeLevel;
  parent_theme_id?: number;
  is_supply_theme?: number;
  keyword?: string;
  limit?: number;
  offset?: number;
};

export type MarketThemeStock = {
  mapping_id: number;
  theme_id: number;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  market: string | null;
  mapping_source: string;
  confidence_score: number | null;
  is_primary: number;
  is_active: number;
  created_at: string;
  updated_at: string;
};

export type MarketThemeStockCreateInput = {
  stock_id: number;
  is_primary?: boolean;
};

export type MarketThemeStockUpdateInput = {
  is_primary?: boolean;
  is_active?: number;
  confidence_score?: number | null;
};

export type MarketThemeByStockItem = {
  theme_id: number;
  theme_name: string;
  is_primary: boolean;
};

export type MarketThemeByStockResponse = {
  stock_code: string;
  stock_name: string | null;
  themes: MarketThemeByStockItem[];
};

export type MarketThemeCandidateStatus = "pending" | "approved" | "rejected" | "ignored";
export type MarketThemeCandidateSource = "news" | "disclosure" | "keyword" | "telegram" | "system";

export type MarketThemeCandidate = {
  id: number;
  theme_id: number;
  theme_name: string;
  stock_id: number;
  stock_code: string;
  stock_name: string;
  candidate_source: MarketThemeCandidateSource;
  confidence_score: number | null;
  matched_keywords: string[];
  evidence_count: number;
  evidence_summary: string | null;
  status: MarketThemeCandidateStatus;
  review_memo: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MarketThemeCandidateGenerateInput = {
  lookback_days?: number;
  source?: "all" | "news" | "disclosure";
  limit?: number;
  force?: boolean;
};

export type MarketThemeCandidateGenerateResult = {
  generated_count: number;
  updated_count: number;
  skipped_existing_mapping_count: number;
  skipped_rejected_count: number;
  source: string;
  lookback_days: number;
};

export type MarketThemeCandidateApproveResult = {
  candidate: MarketThemeCandidate;
  mapping_id: number;
  message: string;
};

export type MarketThemeCandidateReviewInput = {
  review_memo?: string | null;
};
