export type BriefingSourceType = "channel" | "playlist";
export type BriefingSourceStatus = "all" | "active" | "inactive";

export type BriefingSource = {
  id: number;
  source_type: BriefingSourceType;
  source_name: string;
  source_url: string;
  channel_id: string | null;
  playlist_id: string | null;
  is_default: number;
  is_active: number;
  last_checked_at: string | null;
  deleted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BriefingSourceCreateRequest = {
  source_type: BriefingSourceType;
  source_name: string;
  source_url: string;
  channel_id?: string | null;
  playlist_id?: string | null;
  is_default?: number;
  is_active?: number;
};

export type BriefingSourceUpdateRequest = Partial<BriefingSourceCreateRequest>;

export type BriefingVideo = {
  id: number;
  source_id: number | null;
  video_id: string;
  video_url: string;
  title: string;
  channel_name: string | null;
  published_at: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  description_summary: string | null;
  transcript_status: string;
  transcript_language: string | null;
  transcript_source: string | null;
  transcript_checked_at: string | null;
  transcript_text_length: number | null;
  transcript_chunk_count: number | null;
  analysis_status: string;
  summary_exists?: boolean;
  summary_has_content?: boolean;
  summary_id?: number | null;
  topic_count?: number;
  last_analyzed_at: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BriefingVideoManualCreateRequest = {
  video_url: string;
  source_id?: number | null;
};

export type BriefingSummary = {
  id: number;
  video_id: number;
  summary_type: string;
  model_name: string | null;
  summary_text: string | null;
  key_points_json: string | null;
  topic_json: string | null;
  stock_mentions_json: string | null;
  theme_mentions_json: string | null;
  risk_points_json: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BriefingTopicItem = {
  id: number;
  video_id: number;
  topic_name: string;
  summary: string | null;
  importance_score: number | null;
  related_themes_json: string | null;
  related_stocks_json: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BriefingListResponse<T> = {
  success: boolean;
  count: number;
  items: T[];
};

export type BriefingMutationResponse<T = undefined> = {
  success: boolean;
  message: string;
  fetched_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  source_id?: number | null;
  source_name?: string | null;
  playlist_id?: string | null;
  item?: T;
};

export type BriefingTranscriptChunkPreview = {
  index: number;
  text_length: number;
  preview: string;
};

export type BriefingTranscriptCheckResponse = {
  success: boolean;
  video_id: string;
  transcript_status: string;
  transcript_language: string | null;
  transcript_source: string | null;
  text_length: number;
  chunk_count: number;
  chunk_previews: BriefingTranscriptChunkPreview[];
  message: string;
  error: string | null;
  failure_reason?: string | null;
  error_type?: string | null;
  attempts?: Array<{ method: string; success: boolean; error_type?: string }>;
};

export type BriefingVideoSummarizeResponse = {
  success: boolean;
  video_id: string;
  analysis_status: string;
  summary_id: number | null;
  topic_count: number;
  theme_mentions: string[];
  stock_mentions: string[];
  message: string;
  error: string | null;
};

export type BriefingSummaryDetail = {
  id: number;
  summary_type: string;
  model_name: string | null;
  summary_text: string | null;
  elapsed_seconds?: number | null;
  chunk_count?: number | null;
  key_points: string[];
  topics: Array<{ topic_name: string; summary: string }>;
  stock_mentions: string[];
  theme_mentions: string[];
  risk_points: string[];
  created_at: string | null;
  updated_at: string | null;
};

export type BriefingSummaryDetailResponse = {
  success: boolean;
  video_id: string;
  has_content?: boolean;
  summary: BriefingSummaryDetail | null;
  topics: BriefingTopicItem[];
};
