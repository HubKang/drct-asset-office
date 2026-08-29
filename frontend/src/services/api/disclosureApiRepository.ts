import { apiRequest } from "@/services/api/apiClient";
import type { AiSummarizeResponse } from "@/types/analysis";
import type {
  Disclosure,
  DisclosureBulkDeleteResponse,
  DisclosureCollectRequest,
  DisclosureCollectResponse,
  DisclosureCollectionTarget,
  DisclosureCollectSelectedResponse,
  DisclosureCollectSelectedWatchlistRequest,
  DisclosureCollectWatchlistRequest,
  DisclosureListParams,
} from "@/types/disclosure";

export const disclosureApiRepository = {
  listCollectionTargets: () => apiRequest<DisclosureCollectionTarget[]>("/disclosures/collection-targets"),
  listDisclosures: (params?: DisclosureListParams) => {
    const search = new URLSearchParams();
    if (params?.stock_id !== undefined) search.set("stock_id", String(params.stock_id));
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.disclosure_type) search.set("disclosure_type", params.disclosure_type);
    search.set("limit", String(params?.limit ?? 50));
    search.set("offset", String(params?.offset ?? 0));
    return apiRequest<Disclosure[]>(`/disclosures?${search.toString()}`);
  },
  getDisclosure: (disclosureId: number) => apiRequest<Disclosure>(`/disclosures/${disclosureId}`),
  collectDisclosuresForStock: (payload: DisclosureCollectRequest) =>
    apiRequest<DisclosureCollectResponse>("/collectors/disclosures", { method: "POST", body: JSON.stringify(payload) }),
  collectDisclosuresForWatchlist: (payload: DisclosureCollectWatchlistRequest) =>
    apiRequest<DisclosureCollectResponse>("/collectors/disclosures/watchlist", { method: "POST", body: JSON.stringify(payload) }),
  collectDisclosuresForSelectedWatchlist: (payload: DisclosureCollectSelectedWatchlistRequest) =>
    apiRequest<DisclosureCollectSelectedResponse>("/collectors/disclosures/watchlist/selected", { method: "POST", body: JSON.stringify(payload) }),
  summarizeSelectedDisclosures: (disclosureIds: number[]) =>
    apiRequest<AiSummarizeResponse>("/analysis/disclosures/ai-summarize", {
      method: "POST",
      body: JSON.stringify({
        disclosure_ids: disclosureIds,
        only_unprocessed: false,
        overwrite: true,
        limit: disclosureIds.length || 1,
      }),
    }),
  deleteDisclosuresBulk: (disclosureIds: number[]) =>
    apiRequest<DisclosureBulkDeleteResponse>("/disclosures/bulk-delete", {
      method: "POST",
      body: JSON.stringify({ disclosure_ids: disclosureIds }),
    }),
};
