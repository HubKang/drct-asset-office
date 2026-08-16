import { apiRequest } from "@/services/api/apiClient";
import { appConfig } from "@/services/config/appConfig";
import type {
  KmsCategory,
  KmsCategoryPayload,
  KmsCategorySortOrderItem,
  KmsCategorySortOrderResponse,
  KmsHomeSummary,
  KmsKnowledgeItem,
  KmsKnowledgeItemPage,
  KmsKnowledgeItemPayload,
  KmsKnowledgeItemUpdatePayload,
  KmsLocalImageSelectResponse,
  KmsPost,
  KmsPostListParams,
  KmsPostPayload,
  KmsPostUpdatePayload,
  KmsSettingGroup,
  KmsSettingItem,
  KmsSettingItemPayload,
  KmsSettingItemSortOrderItem,
  KmsSettingItemUpdatePayload,
  KmsSummaryHelpApplyPayload,
  KmsSummaryHelpResponse,
  KmsTag,
  KmsTagSearchParams,
} from "@/types/kms";

const appendOptional = (search: URLSearchParams, key: string, value: unknown) => {
  if (value === undefined || value === null || value === "") return;
  search.set(key, String(value));
};

export const kmsApiRepository = {
  getHomeSummary: () => apiRequest<KmsHomeSummary>("/kms/home/summary"),

  listSettingGroups: (includeInactive = false, includeItems = true) =>
    apiRequest<KmsSettingGroup[]>(`/kms/settings/groups?include_inactive=${String(includeInactive)}&include_items=${String(includeItems)}`),

  listSettingItems: (params?: { group_code?: string; include_inactive?: boolean }) => {
    const search = new URLSearchParams();
    appendOptional(search, "group_code", params?.group_code);
    appendOptional(search, "include_inactive", params?.include_inactive ?? false);
    return apiRequest<KmsSettingItem[]>(`/kms/settings/items?${search.toString()}`);
  },

  createSettingItem: (payload: KmsSettingItemPayload) =>
    apiRequest<KmsSettingItem>("/kms/settings/items", { method: "POST", body: JSON.stringify(payload) }),

  updateSettingItem: (itemId: number, payload: KmsSettingItemUpdatePayload) =>
    apiRequest<KmsSettingItem>(`/kms/settings/items/${itemId}`, { method: "PUT", body: JSON.stringify(payload) }),

  updateSettingItemActive: (itemId: number, isActive: boolean) =>
    apiRequest<KmsSettingItem>(`/kms/settings/items/${itemId}/active`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),

  updateSettingItemDefault: (itemId: number) =>
    apiRequest<KmsSettingItem>(`/kms/settings/items/${itemId}/default`, { method: "PATCH" }),

  reorderSettingItems: (items: KmsSettingItemSortOrderItem[]) =>
    apiRequest<{ success: boolean; updated_count: number }>("/kms/settings/items/reorder", { method: "PATCH", body: JSON.stringify({ items }) }),

  listKnowledgeItems: (params?: {
    keyword?: string;
    para_type_id?: number;
    category_id?: number;
    status_id?: number;
    importance_id?: number;
    usage_context_id?: number;
    source_type_id?: number;
    tag?: string;
    tag_id?: number;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    appendOptional(search, "keyword", params?.keyword);
    appendOptional(search, "para_type_id", params?.para_type_id);
    appendOptional(search, "category_id", params?.category_id);
    appendOptional(search, "status_id", params?.status_id);
    appendOptional(search, "importance_id", params?.importance_id);
    appendOptional(search, "usage_context_id", params?.usage_context_id);
    appendOptional(search, "source_type_id", params?.source_type_id);
    appendOptional(search, "tag", params?.tag);
    appendOptional(search, "tag_id", params?.tag_id);
    appendOptional(search, "is_active", params?.is_active ?? true);
    appendOptional(search, "limit", params?.limit ?? 100);
    appendOptional(search, "offset", params?.offset ?? 0);
    return apiRequest<KmsKnowledgeItem[]>(`/kms/knowledge-items?${search.toString()}`);
  },

  listKnowledgeItemsPage: (params?: {
    keyword?: string;
    para_type_id?: number;
    category_id?: number;
    status_id?: number;
    importance_id?: number;
    usage_context_id?: number;
    source_type_id?: number;
    tag_names?: string[];
    tag_match_mode?: "AND" | "OR";
    recent_days?: number;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    appendOptional(search, "keyword", params?.keyword);
    appendOptional(search, "para_type_id", params?.para_type_id);
    appendOptional(search, "category_id", params?.category_id);
    appendOptional(search, "status_id", params?.status_id);
    appendOptional(search, "importance_id", params?.importance_id);
    appendOptional(search, "usage_context_id", params?.usage_context_id);
    appendOptional(search, "source_type_id", params?.source_type_id);
    params?.tag_names?.forEach((tag) => search.append("tag_names", tag));
    appendOptional(search, "tag_match_mode", params?.tag_match_mode ?? "AND");
    appendOptional(search, "recent_days", params?.recent_days);
    appendOptional(search, "is_active", params?.is_active ?? true);
    appendOptional(search, "limit", params?.limit ?? 20);
    appendOptional(search, "offset", params?.offset ?? 0);
    return apiRequest<KmsKnowledgeItemPage>(`/kms/knowledge-items/page?${search.toString()}`);
  },

  getKnowledgeItem: (itemId: number) => apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}`),

  createKnowledgeItem: (payload: KmsKnowledgeItemPayload) =>
    apiRequest<KmsKnowledgeItem>("/kms/knowledge-items", { method: "POST", body: JSON.stringify(payload) }),

  updateKnowledgeItem: (itemId: number, payload: KmsKnowledgeItemUpdatePayload) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}`, { method: "PUT", body: JSON.stringify(payload) }),

  updateKnowledgeItemActive: (itemId: number, isActive: boolean) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}/active`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),

  deleteKnowledgeItem: (itemId: number) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}`, { method: "DELETE" }),

  generateKnowledgeItemSummaryHelp: (itemId: number) =>
    apiRequest<KmsSummaryHelpResponse>(`/kms/knowledge-items/${itemId}/ai/summary`, { method: "POST" }),

  applyKnowledgeItemSummaryHelp: (itemId: number, payload: KmsSummaryHelpApplyPayload) =>
    apiRequest<KmsSummaryHelpResponse>(`/kms/knowledge-items/${itemId}/ai/summary/apply`, { method: "POST", body: JSON.stringify(payload) }),

  replaceKnowledgeItemTags: (itemId: number, tagNames: string[] | string) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}/tags`, { method: "POST", body: JSON.stringify({ tag_names: tagNames }) }),

  syncKnowledgeItemTags: (itemId: number, tagNames: string[] | string) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}/tags/sync`, { method: "POST", body: JSON.stringify({ tag_names: tagNames }) }),

  removeKnowledgeItemTag: (itemId: number, tagId: number) =>
    apiRequest<KmsKnowledgeItem>(`/kms/knowledge-items/${itemId}/tags/${tagId}`, { method: "DELETE" }),

  listCategories: (includeInactive = false) =>
    apiRequest<KmsCategory[]>(`/kms/categories?include_inactive=${String(includeInactive)}`),

  createCategory: (payload: KmsCategoryPayload) =>
    apiRequest<KmsCategory>("/kms/categories", { method: "POST", body: JSON.stringify(payload) }),

  updateCategory: (categoryId: number, payload: Partial<KmsCategoryPayload>) =>
    apiRequest<KmsCategory>(`/kms/categories/${categoryId}`, { method: "PUT", body: JSON.stringify(payload) }),

  updateCategoryActive: (categoryId: number, isActive: boolean) =>
    apiRequest<KmsCategory>(`/kms/categories/${categoryId}/active`, { method: "PATCH", body: JSON.stringify({ is_active: isActive }) }),

  deactivateCategory: (categoryId: number) =>
    apiRequest<KmsCategory>(`/kms/categories/${categoryId}/active`, { method: "PATCH", body: JSON.stringify({ is_active: false }) }),

  deleteCategory: (categoryId: number) =>
    apiRequest<{ success: boolean }>(`/kms/categories/${categoryId}`, { method: "DELETE" }),

  updateCategorySortOrders: (items: KmsCategorySortOrderItem[]) =>
    apiRequest<KmsCategorySortOrderResponse>("/kms/categories/sort-orders", { method: "PUT", body: JSON.stringify({ items }) }),

  listTags: (params?: { keyword?: string; sort?: "popular" | "name"; limit?: number }) => {
    const search = new URLSearchParams();
    appendOptional(search, "keyword", params?.keyword);
    appendOptional(search, "sort", params?.sort ?? "popular");
    appendOptional(search, "limit", params?.limit ?? 100);
    return apiRequest<KmsTag[]>(`/kms/tags?${search.toString()}`);
  },

  listPosts: (params?: KmsPostListParams) => {
    const search = new URLSearchParams();
    appendOptional(search, "keyword", params?.keyword);
    appendOptional(search, "category_id", params?.category_id);
    appendOptional(search, "learning_status", params?.learning_status);
    appendOptional(search, "importance", params?.importance);
    appendOptional(search, "is_active", params?.is_active ?? true);
    appendOptional(search, "limit", params?.limit ?? 100);
    appendOptional(search, "offset", params?.offset ?? 0);
    return apiRequest<KmsPost[]>(`/kms/posts?${search.toString()}`);
  },

  getPost: (postId: number) => apiRequest<KmsPost>(`/kms/posts/${postId}`),

  localImageUrl: (localPath: string) =>
    `${appConfig.apiBaseUrl}/kms/local-image?path=${encodeURIComponent(localPath)}`,

  selectLocalImage: async () => {
    const result = await apiRequest<KmsLocalImageSelectResponse>("/kms/local-image/select");
    return {
      ...result,
      url: result.url && !result.url.startsWith("http") ? `${appConfig.apiBaseUrl}${result.url}` : result.url,
    };
  },
  createPost: (payload: KmsPostPayload) =>
    apiRequest<KmsPost>("/kms/posts", { method: "POST", body: JSON.stringify(payload) }),

  updatePost: (postId: number, payload: KmsPostUpdatePayload) =>
    apiRequest<KmsPost>(`/kms/posts/${postId}`, { method: "PUT", body: JSON.stringify(payload) }),

  deactivatePost: (postId: number) =>
    apiRequest<KmsPost>(`/kms/posts/${postId}`, { method: "DELETE" }),

  searchPostsByTags: (params: KmsTagSearchParams) => {
    const search = new URLSearchParams();
    params.tag_names.forEach((tag) => search.append("tag_names", tag));
    appendOptional(search, "match_mode", params.match_mode);
    appendOptional(search, "category_id", params.category_id);
    appendOptional(search, "learning_status", params.learning_status);
    appendOptional(search, "importance", params.importance);
    appendOptional(search, "limit", params.limit ?? 100);
    appendOptional(search, "offset", params.offset ?? 0);
    return apiRequest<KmsPost[]>(`/kms/posts/search-by-tags?${search.toString()}`);
  },
};
