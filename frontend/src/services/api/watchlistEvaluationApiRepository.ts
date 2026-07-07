import { apiRequest } from "@/services/api/apiClient";
import type {
  WatchlistEvaluateResponse,
  WatchlistEvaluationHistoryItem,
  WatchlistEvaluationListResponse,
  WatchlistGptPromptResponse,
} from "@/types/watchlistEvaluation";

export const watchlistEvaluationApiRepository = {
  list: () => apiRequest<WatchlistEvaluationListResponse>("/watchlist/sije-sucha-jae"),
  evaluate: (watchlistIds: number[]) =>
    apiRequest<WatchlistEvaluateResponse>("/watchlist/sije-sucha-jae/evaluate", {
      method: "POST",
      body: JSON.stringify({ watchlist_ids: watchlistIds, run_type: "MANUAL" }),
    }),
  evaluateAll: (includeInactive = true) =>
    apiRequest<WatchlistEvaluateResponse>("/watchlist/sije-sucha-jae/evaluate-all", {
      method: "POST",
      body: JSON.stringify({ include_inactive: includeInactive, run_type: "MANUAL" }),
    }),
  history: (watchlistId: number) =>
    apiRequest<WatchlistEvaluationHistoryItem[]>(`/watchlist/${watchlistId}/sije-sucha-jae/history`),
  createGptPrompt: (watchlistId: number) =>
    apiRequest<WatchlistGptPromptResponse>(`/watchlist/sije-sucha-jae/${watchlistId}/gpt-prompt`, {
      method: "POST",
    }),
};
