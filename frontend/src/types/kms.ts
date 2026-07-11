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

export type KmsSettingItem = {
  id: number;
  group_id: number;
  group_code?: string | null;
  item_code: string;
  item_name: string;
  description?: string | null;
  color?: string | null;
  icon?: string | null;
  sort_order: number;
  is_default: boolean;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type KmsSettingGroup = {
  id: number;
  group_code: string;
  group_name: string;
  description?: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  items: KmsSettingItem[];
};

export type KmsSettingItemPayload = {
  group_code: string;
  item_code: string;
  item_name: string;
  description?: string | null;
  color?: string | null;
  icon?: string | null;
  sort_order?: number;
  is_default?: boolean;
  is_system?: boolean;
  is_active?: boolean;
};

export type KmsSettingItemUpdatePayload = Partial<Omit<KmsSettingItemPayload, "group_code" | "is_system">>;

export type KmsSettingItemSortOrderItem = {
  id: number;
  sort_order: number;
};

export type KmsKnowledgeItemTag = {
  id: number;
  tag_id: number;
  tag_name: string;
  tag_type_id?: number | null;
  tag_type_name?: string | null;
  weight: number;
  source: "USER" | "AI" | "SYSTEM" | string;
  is_confirmed: boolean;
};

export type KmsSettingItemSummary = {
  id: number;
  item_code: string;
  item_name: string;
  color?: string | null;
  icon?: string | null;
};

export type KmsKnowledgeExtraction = {
  id: number;
  extraction_type: string;
  extraction_text: string;
  source: string;
  model_name?: string | null;
  confidence_score?: number | null;
  created_at: string;
  updated_at: string;
};

export type KmsKnowledgeItem = {
  id: number;
  legacy_post_id?: number | null;
  legacy_source_type?: string | null;
  legacy_source_id?: number | null;
  title: string;
  content: string;
  content_format?: string | null;
  plain_text_snippet?: string | null;
  one_line_conclusion?: string | null;
  summary?: string | null;
  para_type_id?: number | null;
  category_id?: number | null;
  status_id?: number | null;
  importance_id?: number | null;
  usage_context_id?: number | null;
  source_type_id?: number | null;
  source_url?: string | null;
  source_title?: string | null;
  ai_extract_status: string;
  embedding_status: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  para_type?: KmsSettingItemSummary | null;
  category?: KmsSettingItemSummary | null;
  status?: KmsSettingItemSummary | null;
  importance?: KmsSettingItemSummary | null;
  usage_context?: KmsSettingItemSummary | null;
  source_type?: KmsSettingItemSummary | null;
  tags: KmsKnowledgeItemTag[];
  extractions?: KmsKnowledgeExtraction[];
};

export type KmsKnowledgeItemPayload = {
  title: string;
  content: string;
  content_format?: string | null;
  one_line_conclusion?: string | null;
  summary?: string | null;
  para_type_id?: number | null;
  category_id?: number | null;
  status_id?: number | null;
  importance_id?: number | null;
  usage_context_id?: number | null;
  source_type_id?: number | null;
  source_url?: string | null;
  source_title?: string | null;
  tags?: string[] | string | null;
};

export type KmsKnowledgeItemUpdatePayload = Partial<KmsKnowledgeItemPayload> & {
  is_active?: boolean;
};

export type KmsSummaryHelpApplyPayload = {
  apply_summary?: boolean;
  summary?: string | null;
  add_keywords_as_tags?: boolean;
  keywords?: string[];
};

export type KmsSummaryHelpResponse = {
  knowledge_item_id: number;
  status: string;
  summary?: string | null;
  keywords: string[];
  error_message?: string | null;
  item?: KmsKnowledgeItem | null;
};
