export const KMS_IMPORTANCE_OPTIONS = ["낮음", "보통", "높음", "핵심"] as const;
export const KMS_LEARNING_STATUS_OPTIONS = [
  "미정리",
  "정리중",
  "1차 정리 완료",
  "복습 필요",
  "실전 적용 후보",
  "매매기법 반영 완료",
  "보류",
] as const;

export type KmsImportance = (typeof KMS_IMPORTANCE_OPTIONS)[number];
export type KmsLearningStatus = (typeof KMS_LEARNING_STATUS_OPTIONS)[number];
export type KmsTagMatchMode = "AND" | "OR";

export type KmsCategory = {
  id: number;
  parent_id: number | null;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  post_count?: number;
  total_post_count?: number;
  child_count?: number;
};

export type KmsTag = {
  id: number;
  name: string;
  description: string | null;
  use_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type KmsPost = {
  id: number;
  category_id: number;
  category_name: string | null;
  title: string;
  summary: string | null;
  content: string;
  content_format?: string | null;
  content_html?: string | null;
  content_json?: unknown;
  content_text?: string | null;
  source_url: string | null;
  importance: KmsImportance;
  learning_status: KmsLearningStatus;
  is_pinned: boolean;
  is_active: boolean;
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type KmsPostPayload = {
  category_id: number;
  title: string;
  summary?: string | null;
  content: string;
  content_format?: string | null;
  content_html?: string | null;
  content_json?: unknown;
  content_text?: string | null;
  source_url?: string | null;
  importance: KmsImportance;
  learning_status: KmsLearningStatus;
  is_pinned: boolean;
  is_active?: boolean;
  tags?: string[] | string | null;
};

export type KmsPostUpdatePayload = Partial<KmsPostPayload>;

export type KmsCategoryPayload = {
  parent_id?: number | null;
  name: string;
  description?: string | null;
  sort_order?: number;
  is_active?: boolean;
};

export type KmsCategorySortOrderItem = {
  id: number;
  sort_order: number;
};

export type KmsCategorySortOrderResponse = {
  success: boolean;
  updated_count: number;
};

export type KmsLocalImageSelectResponse = {
  selected: boolean;
  path?: string | null;
  url?: string | null;
};

export type KmsPostListParams = {
  keyword?: string;
  category_id?: number;
  learning_status?: string;
  importance?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
};

export type KmsTagSearchParams = {
  tag_names: string[];
  match_mode: KmsTagMatchMode;
  category_id?: number;
  learning_status?: string;
  importance?: string;
  limit?: number;
  offset?: number;
};

export type KmsOverallSummary = {
  total_posts: number;
  review_needed_count: number;
  practice_candidate_count: number;
  core_count: number;
  recent_7d_count: number;
};

export type KmsCategorySummary = {
  category_id: number;
  category_name: string;
  total_posts: number;
  core_count: number;
  review_needed_count: number;
  practice_candidate_count: number;
  recent_7d_count: number;
  top_tags: string[];
  last_updated_at: string | null;
};

export type KmsRecentPost = {
  post_id: number;
  title: string;
  category_name: string | null;
  learning_status: KmsLearningStatus;
  importance: KmsImportance;
  updated_at: string;
};

export type KmsHomeSummary = {
  overall: KmsOverallSummary;
  categories: KmsCategorySummary[];
  popular_tags: KmsTag[];
  recent_posts: KmsRecentPost[];
  review_needed_posts: KmsRecentPost[];
  practice_candidate_posts: KmsRecentPost[];
};
