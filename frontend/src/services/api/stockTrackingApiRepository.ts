import { apiRequest } from "@/services/api/apiClient";
import type {
  CollectStockTrackingPricesPayload,
  CollectStockTrackingPricesResponse,
  CreateStockTrackingGroupPayload,
  CreateTrackingFromConditionResultsPayload,
  CreateTrackingFromConditionResultsResponse,
  RegisterTrackingItemsFromCandidatesPayload,
  RegisterTrackingItemsFromCandidatesResponse,
  StockTrackingGroup,
  StockTrackingGroupAnalysisListResponse,
  StockTrackingChartResponse,
  StockTrackingImage,
  StockTrackingImageListResponse,
  StockTrackingImageType,
  StockTrackingItem,
  StockTrackingItemListResponse,
  StockTrackingPriceStatus,
  StockTrackingStatus,
  UpdateStockTrackingGroupPayload,
  UpdateStockTrackingReviewPayload,
} from "@/types/stockTracking";

export const stockTrackingApiRepository = {
  listGroups: (params?: { active_only?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.active_only !== undefined) search.set("active_only", String(params.active_only));
    const query = search.toString();
    return apiRequest<StockTrackingGroup[]>(`/stock-tracking/groups${query ? `?${query}` : ""}`);
  },
  createGroup: (payload: CreateStockTrackingGroupPayload) =>
    apiRequest<StockTrackingGroup>("/stock-tracking/groups", { method: "POST", body: JSON.stringify(payload) }),
  updateGroup: (groupId: number, payload: UpdateStockTrackingGroupPayload) =>
    apiRequest<StockTrackingGroup>(`/stock-tracking/groups/${groupId}`, { method: "PUT", body: JSON.stringify(payload) }),
  setGroupActive: (groupId: number, isActive: boolean) =>
    apiRequest<StockTrackingGroup>(`/stock-tracking/groups/${groupId}/active`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive ? 1 : 0 }),
    }),
  deleteGroup: (groupId: number) => apiRequest<{ success: boolean; group_id: number }>(`/stock-tracking/groups/${groupId}`, { method: "DELETE" }),
  listGroupAnalysis: (params?: { active_only?: boolean; group_id?: number; from_date?: string; to_date?: string; min_completed_count?: number }) => {
    const search = new URLSearchParams();
    if (params?.active_only !== undefined) search.set("active_only", String(params.active_only));
    if (params?.group_id !== undefined) search.set("group_id", String(params.group_id));
    if (params?.from_date) search.set("from_date", params.from_date);
    if (params?.to_date) search.set("to_date", params.to_date);
    if (params?.min_completed_count !== undefined) search.set("min_completed_count", String(params.min_completed_count));
    const query = search.toString();
    return apiRequest<StockTrackingGroupAnalysisListResponse>(`/stock-tracking/analysis/groups${query ? `?${query}` : ""}`);
  },
  listItems: (params?: {
    group_id?: number;
    status?: StockTrackingStatus | "";
    price_status?: StockTrackingPriceStatus | "";
    from_date?: string;
    to_date?: string;
    keyword?: string;
    active_groups_only?: boolean;
    sort_by?: "tracking_base_date" | "stock_name" | "tracking_return_pct";
    sort_direction?: "asc" | "desc";
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.group_id !== undefined) search.set("group_id", String(params.group_id));
    if (params?.status) search.set("status", params.status);
    if (params?.price_status) search.set("price_status", params.price_status);
    if (params?.from_date) search.set("from_date", params.from_date);
    if (params?.to_date) search.set("to_date", params.to_date);
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.active_groups_only !== undefined) search.set("active_groups_only", String(params.active_groups_only));
    if (params?.sort_by) search.set("sort_by", params.sort_by);
    if (params?.sort_direction) search.set("sort_direction", params.sort_direction);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<StockTrackingItemListResponse>(`/stock-tracking/items${query ? `?${query}` : ""}`);
  },
  registerFromCandidates: (payload: RegisterTrackingItemsFromCandidatesPayload) =>
    apiRequest<RegisterTrackingItemsFromCandidatesResponse>("/stock-tracking/items/from-candidates", { method: "POST", body: JSON.stringify(payload) }),
  registerFromConditionResults: (payload: CreateTrackingFromConditionResultsPayload) =>
    apiRequest<CreateTrackingFromConditionResultsResponse>("/stock-tracking/items/from-condition-results", { method: "POST", body: JSON.stringify(payload) }),
  collectPrices: (payload: CollectStockTrackingPricesPayload) =>
    apiRequest<CollectStockTrackingPricesResponse>("/stock-tracking/items/collect-prices", { method: "POST", body: JSON.stringify(payload) }),
  getItem: (itemId: number) => apiRequest<StockTrackingItem>(`/stock-tracking/items/${itemId}`),
  getChart: (itemId: number) => apiRequest<StockTrackingChartResponse>(`/stock-tracking/items/${itemId}/chart`),
  listImages: (itemId: number) => apiRequest<StockTrackingImageListResponse>(`/stock-tracking/items/${itemId}/images`),
  uploadImage: (itemId: number, payload: { file: File; image_type: StockTrackingImageType; caption?: string }) => {
    const formData = new FormData();
    formData.set("file", payload.file);
    formData.set("image_type", payload.image_type);
    if (payload.caption) formData.set("caption", payload.caption);
    return apiRequest<StockTrackingImage>(`/stock-tracking/items/${itemId}/images`, { method: "POST", body: formData });
  },
  deleteImage: (imageId: number) => apiRequest<{ success: boolean; image_id: number }>(`/stock-tracking/images/${imageId}`, { method: "DELETE" }),
  updateReview: (itemId: number, payload: UpdateStockTrackingReviewPayload) =>
    apiRequest<StockTrackingItem>(`/stock-tracking/items/${itemId}/review`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteItem: (itemId: number) => apiRequest<{ success: boolean; item_id: number }>(`/stock-tracking/items/${itemId}`, { method: "DELETE" }),
};
