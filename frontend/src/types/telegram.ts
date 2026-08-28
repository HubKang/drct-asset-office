export type TelegramSource = {
  id: number; source_name: string; channel_username: string; channel_title: string | null;
  description: string | null; is_active: number; is_default: number; is_deleted: number;
  last_collected_message_id: number | null; last_collected_at: string | null; memo: string | null;
  created_at: string; updated_at: string | null;
};

export type TelegramItem = {
  id: number; collection_date: string; message_at: string; title: string;
  summary: string | null; source_url: string | null; created_at: string;
};

export type TelegramItemListResponse = {
  items: TelegramItem[]; total_count: number; with_summary_count: number;
  title_only_count: number; limit: number; offset: number;
};

export type TelegramCollectResult = {
  source_id: number; source_name: string; target_date: string; source_mode: string;
  success: boolean; telegram_connected: boolean; session_exists: boolean; channel_accessible: boolean;
  collected: number; inserted: number; duplicate_skipped: number; excluded_skipped: number;
  processing_failed: number;
  error_code?: string | null; error_message?: string | null;
  diagnostics?: Record<string, boolean>;
};

export type TelegramCollectAllResult = Omit<TelegramCollectResult, "source_id" | "source_name"> & { source_count: number };
export type TelegramSummarizeResult = {
  requested: number; summarized: number; skipped_existing: number; missing_url: number;
  fetch_failed: number; extraction_failed: number; processing_failed: number;
};
export type TelegramSourceConnectionTest = {
  source_id: number; source_name: string; channel_username: string; normalized_channel_username: string | null;
  telegram_connected: boolean; session_exists: boolean; channel_accessible: boolean; source_mode: string;
  latest_message_id: number | null; latest_message_date: string | null; message: string;
};
export type TelegramAuthStatus = {
  enabled: boolean; has_api_id: boolean; has_api_hash: boolean; has_phone: boolean; has_session: boolean;
  authorized: boolean; auth_required: boolean; source_mode: string; error_code?: string | null; error_message?: string | null;
};
export type TelegramAuthStartResult = { success: boolean; auth_stage: string; authorized: boolean; error_code?: string | null; message: string };
export type TelegramAuthVerifyResult = TelegramAuthStartResult;
