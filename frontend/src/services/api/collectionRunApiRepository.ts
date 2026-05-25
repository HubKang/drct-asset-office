import { apiRequest } from "@/services/api/apiClient";
import type {
  CollectionRun,
  CollectionRunCleanupPreviewResponse,
  CollectionRunCleanupResponse,
  CollectionRunListParams,
  CollectionRunListResponse,
} from "@/types/collectionRun";

export const collectionRunApiRepository = {
  listCollectionRuns: (params?: CollectionRunListParams) => {
    const search = new URLSearchParams();
    if (params?.collector_name) search.set("collector_name", params.collector_name);
    if (params?.status) search.set("status", params.status);
    if (params?.target) search.set("target", params.target);
    search.set("limit", String(params?.limit ?? 20));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<CollectionRunListResponse>(`/collection-runs?${search.toString()}`);
  },
  getCollectionRun: (runId: number) => apiRequest<CollectionRun>(`/collection-runs/${runId}`),
  previewCleanupOlderThanOneMonth: () =>
    apiRequest<CollectionRunCleanupPreviewResponse>("/collection-runs/cleanup/older-than-one-month/preview"),
  cleanupOlderThanOneMonth: () =>
    apiRequest<CollectionRunCleanupResponse>("/collection-runs/cleanup/older-than-one-month", { method: "DELETE" }),
};
