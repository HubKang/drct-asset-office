import { apiRequest } from "@/services/api/apiClient";
import { appConfig } from "@/services/config/appConfig";
import type {
  KmsCategory,
  KmsCategoryPayload,
  KmsCategorySortOrderItem,
  KmsCategorySortOrderResponse,
  KmsHomeSummary,
  KmsLocalImageSelectResponse,
  KmsPost,
  KmsPostListParams,
  KmsPostPayload,
  KmsPostUpdatePayload,
  KmsTag,
  KmsTagSearchParams,
} from "@/types/kms";

const appendOptional = (search: URLSearchParams, key: string, value: unknown) => {
  if (value === undefined || value === null || value === "") return;
  search.set(key, String(value));
};

export const kmsApiRepository = {
  getHomeSummary: () => apiRequest<KmsHomeSummary>("/kms/home/summary"),

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
