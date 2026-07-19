import { apiRequest } from "@/services/api/apiClient";
import type {
  MarketSignalCondition,
  MarketSignalCatalogResponse,
  MarketSignalConditionPreviewResponse,
  MarketSignalDefinition,
  MarketSignalEvaluationResponse,
  MarketSignalEventListResponse,
  MarketSignalGenericItemResponse,
  MarketSignalGenericListResponse,
  MarketSignalGptDraftResponse,
  MarketSignalIndicatorCatalogResponse,
  MarketSignalListResponse,
  MarketSignalModelProfile,
  MarketSignalOverview,
  MarketSignalRuleTemplate,
  MarketSignalSimulationResponse,
  SingleIndicatorSignal,
  CompositeSignalItem,
  ObjectivePhenomenonItem,
} from "@/types/marketSignal";

export const marketSignalApiRepository = {
  list: (params?: { status?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    return apiRequest<MarketSignalListResponse>(`/market-signals${query.toString() ? `?${query.toString()}` : ""}`);
  },
  get: (id: number) => apiRequest<MarketSignalDefinition>(`/market-signals/${id}`),
  update: (id: number, payload: Partial<MarketSignalDefinition> & { conditions: MarketSignalCondition[]; change_reason?: string }) =>
    apiRequest<MarketSignalDefinition>(`/market-signals/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  activate: (id: number) => apiRequest<MarketSignalDefinition>(`/market-signals/${id}/activate`, { method: "POST" }),
  deactivate: (id: number) => apiRequest<MarketSignalDefinition>(`/market-signals/${id}/deactivate`, { method: "POST" }),
  activateWithApproval: (id: number, payload: { reason?: string; purpose?: string; memo?: string; tags?: string[] } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>(`/market-signals/${id}/activate-with-approval`, { method: "POST", body: JSON.stringify({ payload }) }),
  deactivateWithReason: (id: number, payload: { reason?: string } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<MarketSignalDefinition>>(`/market-signals/${id}/deactivate-with-reason`, { method: "POST", body: JSON.stringify({ payload }) }),
  markValidationComplete: (id: number, payload: { validation_period_years?: number; validation_summary?: Record<string, unknown> } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<MarketSignalDefinition>>(`/market-signals/${id}/mark-validation-complete`, { method: "POST", body: JSON.stringify({ payload }) }),
  cloneVersion: (id: number, payload: { reason?: string } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>(`/market-signals/${id}/clone-version`, { method: "POST", body: JSON.stringify({ payload }) }),
  catalog: () => apiRequest<MarketSignalIndicatorCatalogResponse>("/market-signals/indicator-catalog"),
  signalCatalog: (params?: { category?: string; country?: string; readiness?: string; signal_readiness?: string; profile_code?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.country) query.set("country", params.country);
    if (params?.readiness) query.set("readiness", params.readiness);
    if (params?.signal_readiness) query.set("signal_readiness", params.signal_readiness);
    if (params?.profile_code) query.set("profile_code", params.profile_code);
    if (params?.search) query.set("search", params.search);
    return apiRequest<MarketSignalCatalogResponse>(`/market-signals/catalog${query.toString() ? `?${query.toString()}` : ""}`);
  },
  modelProfiles: () => apiRequest<MarketSignalGenericListResponse<MarketSignalModelProfile>>("/market-signals/model-profiles"),
  conditionPreview: (condition: MarketSignalCondition, observation_date?: string | null) =>
    apiRequest<MarketSignalConditionPreviewResponse>("/market-signals/condition-preview", { method: "POST", body: JSON.stringify({ condition, observation_date }) }),
  evaluate: (payload: { signal_ids?: number[]; active_only?: boolean; observation_date?: string; save?: boolean }) =>
    apiRequest<MarketSignalEvaluationResponse>("/market-signals/evaluate", { method: "POST", body: JSON.stringify(payload) }),
  evaluations: (id: number, limit = 50) => apiRequest<MarketSignalEvaluationResponse>(`/market-signals/${id}/evaluations?limit=${limit}`),
  evaluationHistory: (id: number, limit = 50) => apiRequest<MarketSignalEvaluationResponse>(`/market-signals/${id}/evaluation-history?limit=${limit}`),
  events: (limit = 50) => apiRequest<MarketSignalEventListResponse>(`/market-signals/events?limit=${limit}`),
  overview: () => apiRequest<MarketSignalOverview>("/market-signals/overview"),
  simulate: (id: number, years = 1) => apiRequest<MarketSignalSimulationResponse>(`/market-signals/${id}/simulate?years=${years}`, { method: "POST" }),
  gptDraft: (payload: { goal_text: string; gpt_result_json?: Record<string, unknown> | null }) =>
    apiRequest<MarketSignalGptDraftResponse>("/market-signals/gpt-rule-draft", { method: "POST", body: JSON.stringify(payload) }),
  todayEvents: () => apiRequest<MarketSignalGenericItemResponse<{ items: Record<string, unknown>[]; observation_date: string }>>("/market-signals/events/today"),
  singleIndicators: () => apiRequest<MarketSignalGenericListResponse<SingleIndicatorSignal>>("/market-signals/single-indicator"),
  singleIndicator: (id: number) => apiRequest<MarketSignalGenericItemResponse<SingleIndicatorSignal>>(`/market-signals/single-indicator/${id}`),
  previewSingleIndicatorDraft: (payload: { item_type: "INDEX" | "INDICATOR"; item_code: string; profile_code?: string; period?: string; configuration?: Record<string, number> }) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>("/market-signals/single-indicator/preview", { method: "POST", body: JSON.stringify({ payload }) }),
  createSingleIndicatorDraft: (payload: { item_type: "INDEX" | "INDICATOR"; item_code: string; profile_code?: string; configuration?: Record<string, number> }) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>("/market-signals/single-indicator/create-draft", { method: "POST", body: JSON.stringify({ payload }) }),
  createSingleIndicatorDrafts: (items: { item_type: "INDEX" | "INDICATOR"; item_code: string; profile_code?: string }[]) =>
    apiRequest<Record<string, unknown>>("/market-signals/single-indicator/create-drafts", { method: "POST", body: JSON.stringify({ payload: { items } }) }),
  singleIndicatorCoverageSummary: () =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>("/market-signals/single-indicator/coverage-summary"),
  evaluateSingleIndicator: (id: number, payload: { observation_date?: string | null; save?: boolean } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<SingleIndicatorSignal>>(`/market-signals/single-indicator/${id}/evaluate`, { method: "POST", body: JSON.stringify(payload) }),
  simulateSingleIndicator: (id: number, years = 3) =>
    apiRequest<Record<string, unknown>>(`/market-signals/single-indicator/${id}/simulate`, { method: "POST", body: JSON.stringify({ years }) }),
  singleTrendChart: (id: number, observation_date?: string | null) => {
    const query = observation_date ? `?observation_date=${encodeURIComponent(observation_date)}` : "";
    return apiRequest<Record<string, unknown>>(`/market-signals/single-indicator/${id}/trend-chart${query}`);
  },
  compositeSignals: () => apiRequest<MarketSignalGenericListResponse<CompositeSignalItem>>("/market-signals/composite"),
  evaluateComposite: (id: number, payload: { observation_date?: string | null; save?: boolean } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<CompositeSignalItem>>(`/market-signals/composite/${id}/evaluate`, { method: "POST", body: JSON.stringify(payload) }),
  validateCompositeTemplateReadiness: (id: number) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>(`/market-signals/composite/templates/${id}/validate-readiness`, { method: "POST" }),
  phenomena: () => apiRequest<MarketSignalGenericListResponse<ObjectivePhenomenonItem>>("/market-signals/phenomena"),
  evaluatePhenomenon: (id: number, payload: { observation_date?: string | null; save?: boolean } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<ObjectivePhenomenonItem>>(`/market-signals/phenomena/${id}/evaluate`, { method: "POST", body: JSON.stringify(payload) }),
  phenomenonEpisodes: (id: number) => apiRequest<MarketSignalGenericListResponse<Record<string, unknown>>>(`/market-signals/phenomena/${id}/episodes`),
  gptPhenomenonDiagnosis: (id: number, payload: { observation_date?: string | null; payload?: Record<string, unknown> } = {}) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>(`/market-signals/phenomena/${id}/gpt-diagnosis`, { method: "POST", body: JSON.stringify(payload) }),
  evidenceSources: () => apiRequest<MarketSignalGenericListResponse<Record<string, unknown>>>("/market-signals/evidence-sources"),
  ruleExperiments: () => apiRequest<MarketSignalGenericListResponse<Record<string, unknown>>>("/market-signals/rule-experiments"),
  ruleTemplates: () => apiRequest<MarketSignalGenericListResponse<MarketSignalRuleTemplate>>("/market-signals/rule-templates"),
  copyTemplate: (id: number) => apiRequest<MarketSignalDefinition>(`/market-signals/rule-templates/${id}/copy`, { method: "POST" }),
  gptDesign: (payload: { goal_text: string; gpt_result_json?: Record<string, unknown> | null }) =>
    apiRequest<MarketSignalGenericItemResponse<Record<string, unknown>>>("/market-signals/gpt-rule-design", { method: "POST", body: JSON.stringify(payload) }),
};
