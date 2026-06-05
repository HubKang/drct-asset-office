import { apiRequest } from "@/services/api/apiClient";
import type {
  AnalysisConditionTemplate,
  AnalysisIndicatorCandidate,
  AnalysisIndicator,
  AnalysisIndicatorAlias,
  AnalysisLlmCatalog,
} from "@/types/analysisIndicator";

function queryString(params?: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const analysisIndicatorApiRepository = {
  fetchIndicators: (params?: { keyword?: string; source_type?: string; category?: string; active_only?: boolean; available_for_llm?: boolean }) =>
    apiRequest<{ items: AnalysisIndicator[] }>(`/analysis-indicators${queryString(params)}`),
  createIndicator: (payload: Partial<AnalysisIndicator>) =>
    apiRequest<AnalysisIndicator>("/analysis-indicators", { method: "POST", body: JSON.stringify(payload) }),
  updateIndicator: (id: number, payload: Partial<AnalysisIndicator>) =>
    apiRequest<AnalysisIndicator>(`/analysis-indicators/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteIndicator: (id: number) =>
    apiRequest<AnalysisIndicator>(`/analysis-indicators/${id}`, { method: "DELETE" }),

  fetchAliases: (params?: { keyword?: string; indicator_key?: string; active_only?: boolean }) =>
    apiRequest<{ items: AnalysisIndicatorAlias[] }>(`/analysis-indicator-aliases${queryString(params)}`),
  createAlias: (payload: Partial<AnalysisIndicatorAlias>) =>
    apiRequest<AnalysisIndicatorAlias>("/analysis-indicator-aliases", { method: "POST", body: JSON.stringify(payload) }),
  updateAlias: (id: number, payload: Partial<AnalysisIndicatorAlias>) =>
    apiRequest<AnalysisIndicatorAlias>(`/analysis-indicator-aliases/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAlias: (id: number) =>
    apiRequest<AnalysisIndicatorAlias>(`/analysis-indicator-aliases/${id}`, { method: "DELETE" }),

  fetchTemplates: (params?: { active_only?: boolean }) =>
    apiRequest<{ items: AnalysisConditionTemplate[] }>(`/analysis-condition-templates${queryString(params)}`),
  createTemplate: (payload: Partial<AnalysisConditionTemplate>) =>
    apiRequest<AnalysisConditionTemplate>("/analysis-condition-templates", { method: "POST", body: JSON.stringify(payload) }),
  updateTemplate: (id: number, payload: Partial<AnalysisConditionTemplate>) =>
    apiRequest<AnalysisConditionTemplate>(`/analysis-condition-templates/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTemplate: (id: number) =>
    apiRequest<AnalysisConditionTemplate>(`/analysis-condition-templates/${id}`, { method: "DELETE" }),

  fetchLlmCatalog: () => apiRequest<AnalysisLlmCatalog>("/analysis-indicators/llm-catalog"),

  fetchCandidates: (params?: { status?: string; keyword?: string; active_only?: boolean }) =>
    apiRequest<{ items: AnalysisIndicatorCandidate[] }>(`/analysis-indicator-candidates${queryString(params)}`),
  createCandidate: (payload: Partial<AnalysisIndicatorCandidate>) =>
    apiRequest<AnalysisIndicatorCandidate>("/analysis-indicator-candidates", { method: "POST", body: JSON.stringify(payload) }),
  updateCandidate: (id: number, payload: Partial<AnalysisIndicatorCandidate>) =>
    apiRequest<AnalysisIndicatorCandidate>(`/analysis-indicator-candidates/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  approveCandidateAsIndicator: (id: number) =>
    apiRequest<AnalysisIndicatorCandidate>(`/analysis-indicator-candidates/${id}/approve-as-indicator`, { method: "POST" }),
  approveCandidateReferenceOnly: (id: number) =>
    apiRequest<AnalysisIndicatorCandidate>(`/analysis-indicator-candidates/${id}/approve-reference-only`, { method: "POST" }),
  rejectCandidate: (id: number) =>
    apiRequest<AnalysisIndicatorCandidate>(`/analysis-indicator-candidates/${id}/reject`, { method: "POST" }),
  markCandidateNeedsEngine: (id: number) =>
    apiRequest<AnalysisIndicatorCandidate>(`/analysis-indicator-candidates/${id}/mark-needs-engine`, { method: "POST" }),
};
