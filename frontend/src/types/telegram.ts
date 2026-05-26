export type TelegramSource = {
  id: number;
  source_name: string;
  channel_username: string;
  channel_title: string | null;
  description: string | null;
  is_active: number;
  is_default: number;
  is_deleted: number;
  last_collected_message_id: number | null;
  last_collected_at: string | null;
  memo: string | null;
  created_at: string;
  updated_at: string | null;
};

export type TelegramItem = {
  id: number;
  source_id: number;
  source_name: string;
  telegram_message_id: number;
  message_date: string;
  message_text: string | null;
  item_title?: string | null;
  summary_text: string | null;
  key_points_json?: string | null;
  message_type: string;
  item_category: string;
  tag: string | null;
  score: number;
  sentiment: string;
  risk_level: string;
  event_type: string;
  related_stock_name: string | null;
  related_stock_code: string | null;
  related_theme: string | null;
  summary_status: string;
  summary_has_content: number;
  summary_error_message?: string | null;
  item_url: string | null;
  normalized_url?: string | null;
  updated_at?: string | null;
};

export type TelegramItemListResponse = {
  items: TelegramItem[];
  total_count: number;
  limit: number;
  offset: number;
};

export type TelegramCollectResult = {
  source_id: number;
  source_name: string;
  target_date: string;
  source_mode: string;
  success: boolean;
  telegram_connected: boolean;
  session_exists: boolean;
  channel_accessible: boolean;
  fetched_message_count: number;
  new_item_count: number;
  duplicate_count: number;
  summarized_count: number;
  failed_count: number;
  error_code?: string | null;
  error_message?: string | null;
  diagnostics?: Record<string, boolean>;
  collection_run_id: number;
};

export type TelegramCollectAllResult = {
  target_date: string;
  source_count: number;
  source_mode: string;
  success: boolean;
  telegram_connected: boolean;
  session_exists: boolean;
  channel_accessible: boolean;
  fetched_message_count: number;
  new_item_count: number;
  duplicate_count: number;
  summarized_count: number;
  failed_count: number;
  error_code?: string | null;
  error_message?: string | null;
  diagnostics?: Record<string, boolean>;
};

export type TelegramSourceConnectionTest = {
  source_id: number;
  source_name: string;
  channel_username: string;
  normalized_channel_username: string | null;
  telegram_connected: boolean;
  session_exists: boolean;
  channel_accessible: boolean;
  source_mode: string;
  latest_message_id: number | null;
  latest_message_date: string | null;
  message: string;
};

export type TelegramAuthStatus = {
  enabled: boolean;
  has_api_id: boolean;
  has_api_hash: boolean;
  has_phone: boolean;
  has_session: boolean;
  authorized: boolean;
  auth_required: boolean;
  source_mode: string;
  error_code?: string | null;
  error_message?: string | null;
};

export type TelegramAuthStartResult = {
  success: boolean;
  auth_stage: string;
  authorized: boolean;
  error_code?: string | null;
  message: string;
};

export type TelegramAuthVerifyResult = {
  success: boolean;
  auth_stage: string;
  authorized: boolean;
  error_code?: string | null;
  message: string;
};

export type TelegramDailySummary = {
  id: number;
  summary_date: string;
  source_id: number;
  item_count: number;
  summary_text: string | null;
  key_points: string[];
  top_tags: string[];
  top_event_types: string[];
  message_type_stats: Array<{ message_type: string; count: number }>;
  theme_mentions: string[];
  stock_mentions: string[];
  risk_points: string[];
  summary_has_content: number;
  llm_model: string | null;
};

export type TelegramItemSummarizeResult = {
  item_id: number;
  summary_status: string;
  summary_has_content: number;
  summary_text: string | null;
  summary_error_message?: string | null;
};
