import { apiRequest } from "@/services/api/apiClient";
import type { DrctInsightToday } from "@/types/drctInsight";

export const drctInsightApiRepository = {
  today: (signal?: AbortSignal) => apiRequest<DrctInsightToday>("/api/drct-insight/today", { signal, timeoutMs: 120000 }),
  captureTodayEvaluation: (signal?: AbortSignal) => apiRequest<DrctInsightToday>("/api/drct-insight/today/evaluate", { method: "POST", signal, timeoutMs: 120000 }),
};
