import { apiRequest } from "@/services/api/apiClient";
import type {
  BriefingListResponse,
  BriefingMutationResponse,
  BriefingSource,
  BriefingSourceStatus,
  BriefingSourceCreateRequest,
  BriefingSourceUpdateRequest,
  BriefingSummary,
  BriefingSummaryDetailResponse,
  BriefingTranscriptCheckResponse,
  BriefingVideoSummarizeResponse,
  BriefingVideo,
  BriefingVideoManualCreateRequest,
} from "@/types/economicBriefing";

export const economicBriefingApiRepository = {
  getBriefingSources: (params?: { status?: BriefingSourceStatus }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    const query = search.toString();
    return apiRequest<BriefingListResponse<BriefingSource>>(`/economic-briefing/sources${query ? `?${query}` : ""}`);
  },
  createBriefingSource: (payload: BriefingSourceCreateRequest) =>
    apiRequest<BriefingMutationResponse<BriefingSource>>("/economic-briefing/sources", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateBriefingSource: (sourceId: number, payload: BriefingSourceUpdateRequest) =>
    apiRequest<BriefingMutationResponse<BriefingSource>>(`/economic-briefing/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  activateBriefingSource: (sourceId: number) =>
    apiRequest<BriefingMutationResponse<BriefingSource>>(`/economic-briefing/sources/${sourceId}/activate`, {
      method: "PATCH",
    }),
  deactivateBriefingSource: (sourceId: number) =>
    apiRequest<BriefingMutationResponse<BriefingSource>>(`/economic-briefing/sources/${sourceId}/deactivate`, {
      method: "PATCH",
    }),
  deleteBriefingSource: (sourceId: number) =>
    apiRequest<BriefingMutationResponse>(`/economic-briefing/sources/${sourceId}`, {
      method: "DELETE",
    }),
  refreshBriefingSourceVideos: (sourceId: number, payload?: { max_results?: number }) =>
    apiRequest<BriefingMutationResponse>(`/economic-briefing/sources/${sourceId}/refresh-videos`, {
      method: "POST",
      body: JSON.stringify({ max_results: payload?.max_results ?? 20 }),
    }),
  getBriefingVideos: (params?: {
    source_id?: number;
    manual_only?: boolean;
    analysis_status?: string;
    transcript_status?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.source_id !== undefined) search.set("source_id", String(params.source_id));
    if (params?.manual_only !== undefined) search.set("manual_only", String(params.manual_only));
    if (params?.analysis_status) search.set("analysis_status", params.analysis_status);
    if (params?.transcript_status) search.set("transcript_status", params.transcript_status);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<BriefingListResponse<BriefingVideo>>(`/economic-briefing/videos${query ? `?${query}` : ""}`);
  },
  createManualBriefingVideo: (payload: BriefingVideoManualCreateRequest) =>
    apiRequest<BriefingMutationResponse<BriefingVideo>>("/economic-briefing/videos/manual", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getBriefingVideoSummaries: (videoId: string) =>
    apiRequest<BriefingSummaryDetailResponse>(`/economic-briefing/videos/${videoId}/summaries`),
  checkBriefingVideoTranscript: (videoId: string) =>
    apiRequest<BriefingTranscriptCheckResponse>(`/economic-briefing/videos/${videoId}/transcript-check`, {
      method: "POST",
    }),
  summarizeBriefingVideo: (videoId: string, force = false) =>
    apiRequest<BriefingVideoSummarizeResponse>(`/economic-briefing/videos/${videoId}/summarize?force=${String(force)}`, {
      method: "POST",
    }),
  refreshBriefingVideoMetadata: (videoId: string) =>
    apiRequest<BriefingMutationResponse<BriefingVideo>>(`/economic-briefing/videos/${videoId}/refresh-metadata`, {
      method: "POST",
    }),
};
