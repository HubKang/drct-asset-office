import { apiRequest } from "@/services/api/apiClient";
import type { DrctInsightPerformance, DrctInsightPerformanceFilters, DrctInsightPerformanceRefresh, DrctInsightToday } from "@/types/drctInsight";

const TODAY_MEMORY_TTL_MS = 5 * 60 * 1000;
let todayMemory: { value: DrctInsightToday; cachedAt: number } | null = null;

function rememberToday(value: DrctInsightToday) {
  todayMemory = { value, cachedAt: Date.now() };
  return value;
}

function performanceQuery(filters: DrctInsightPerformanceFilters) {
  const params = new URLSearchParams({ period: filters.period, page: String(filters.page), page_size: String(filters.page_size) });
  if (filters.candidate_level) params.set("candidate_level", filters.candidate_level);
  if (filters.theme_id) params.set("theme_id", String(filters.theme_id));
  if (filters.pattern_status) params.set("pattern_status", filters.pattern_status);
  if (filters.outcome_status) params.set("outcome_status", filters.outcome_status);
  return params.toString();
}

export const drctInsightApiRepository = {
  peekToday: () => todayMemory && Date.now() - todayMemory.cachedAt <= TODAY_MEMORY_TTL_MS ? todayMemory.value : null,
  today: (signal?: AbortSignal, force=false) => apiRequest<DrctInsightToday>(`/api/drct-insight/today${force ? "?force=true" : ""}`, { signal, timeoutMs: 120000 }).then(rememberToday),
  captureTodayEvaluation: (signal?: AbortSignal) => apiRequest<DrctInsightToday>("/api/drct-insight/today/evaluate", { method: "POST", signal, timeoutMs: 120000 }).then(rememberToday),
  evaluations: (filters: DrctInsightPerformanceFilters, signal?: AbortSignal) => apiRequest<DrctInsightPerformance>(`/api/drct-insight/evaluations?${performanceQuery(filters)}`, { signal, timeoutMs: 120000 }),
  refreshEvaluations: (force=false) => apiRequest<DrctInsightPerformanceRefresh>(`/api/drct-insight/evaluations/refresh?force=${force}`, { method: "POST", timeoutMs: 120000 }),
};
