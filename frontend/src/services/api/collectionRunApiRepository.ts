import { apiRequest } from "@/services/api/apiClient";
import type { CollectionRun, CollectionRunListParams } from "@/types/collectionRun";

export const collectionRunApiRepository = {
  listCollectionRuns: (params?: CollectionRunListParams) => {
    const search = new URLSearchParams();
    if (params?.collector_name) search.set("collector_name", params.collector_name);
    if (params?.status) search.set("status", params.status);
    if (params?.target) search.set("target", params.target);
    search.set("limit", String(params?.limit ?? 50));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<CollectionRun[]>(`/collection-runs?${search.toString()}`);
  },
  getCollectionRun: (runId: number) => apiRequest<CollectionRun>(`/collection-runs/${runId}`),
};
