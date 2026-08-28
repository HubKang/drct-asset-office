import { apiRequest } from "@/services/api/apiClient";
import type {
  TrainingFinishResponse,
  TrainingGptPackage,
  TrainingOrderRequest,
  RiskOrderPreview,
  RiskOrderPreviewRequest,
  TradeTrainingRiskScenarioDetail,
  TradeTrainingRiskScenarioDraftRequest,
  TradeTrainingRiskScenarioRevisionListResponse,
  ScenarioExecutionReview,
  ScenarioHabitsResponse,
  TrainingResult,
  SimulationReview,
  SimulationReviewSaveRequest,
  TrainingCalendarResponse,
  TradeTrainingAccount,
  TradeTrainingAccountDeleteResponse,
  TradeTrainingAccountPerformance,
  TradeTrainingAccountListResponse,
  TradeTrainingAccountSaveRequest,
  TradeTrainingAccountSessionListResponse,
  TradeTrainingAccountSummary,
  TradeTrainingClosedTradeListResponse,
  TradeTrainingPriceCollectionMode,
  TradeTrainingPriceCollectionResult,
  TrainingSessionCreate,
  TrainingSessionDetail,
  TrainingStockListResponse,
  TechnicalAnalysisPreview,
  TechnicalAnalysisPreviewRequest,
} from "@/types/tradeTraining";
import type {
  MultiPeriodTechnicalAnalysis,
  MultiPeriodTechnicalAnalysisRequest,
} from "@/types/multiPeriodTechnicalAnalysis";

export const tradeTrainingApiRepository = {
  listAccounts: (params?: { status?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    const query = search.toString();
    return apiRequest<TradeTrainingAccountListResponse>(`/trade-training/accounts${query ? `?${query}` : ""}`);
  },
  createAccount: (payload: TradeTrainingAccountSaveRequest) =>
    apiRequest<TradeTrainingAccount>("/trade-training/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getAccount: (accountId: number) => apiRequest<TradeTrainingAccount>(`/trade-training/accounts/${accountId}`),
  updateAccount: (accountId: number, payload: Partial<TradeTrainingAccountSaveRequest>) =>
    apiRequest<TradeTrainingAccount>(`/trade-training/accounts/${accountId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getAccountSummary: (accountId: number) =>
    apiRequest<TradeTrainingAccountSummary>(`/trade-training/accounts/${accountId}/summary`),
  listAccountSessions: (accountId: number, params?: { status?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    const query = search.toString();
    return apiRequest<TradeTrainingAccountSessionListResponse>(`/trade-training/accounts/${accountId}/sessions${query ? `?${query}` : ""}`);
  },
  listAccountClosedTrades: (accountId: number) =>
    apiRequest<TradeTrainingClosedTradeListResponse>(`/trade-training/accounts/${accountId}/closed-trades`),
  getAccountPerformance: (accountId: number) =>
    apiRequest<TradeTrainingAccountPerformance>(`/trade-training/accounts/${accountId}/performance`),
  deleteAccount: (accountId: number) =>
    apiRequest<TradeTrainingAccountDeleteResponse>(`/trade-training/accounts/${accountId}`, { method: "DELETE" }),
  getCalendar: (month: string) =>
    apiRequest<TrainingCalendarResponse>(`/trade-training/calendar?month=${encodeURIComponent(month)}`),
  listStocks: (params?: { q?: string; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.page !== undefined) search.set("page", String(params.page));
    if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
    const query = search.toString();
    return apiRequest<TrainingStockListResponse>(`/trade-training/stocks${query ? `?${query}` : ""}`);
  },
  collectStockPrices: (stockId: number, mode: TradeTrainingPriceCollectionMode) =>
    apiRequest<TradeTrainingPriceCollectionResult>(`/trade-training/stocks/${stockId}/collect-prices`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  createSession: (payload: TrainingSessionCreate) =>
    apiRequest<TrainingSessionDetail>("/trade-training/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSession: (sessionId: number) => apiRequest<TrainingSessionDetail>(`/trade-training/sessions/${sessionId}`),
  previewTechnicalAnalysis: (payload: TechnicalAnalysisPreviewRequest, signal?: AbortSignal) =>
    apiRequest<TechnicalAnalysisPreview>("/trade-training/technical-analysis/preview", {
      method: "POST", body: JSON.stringify(payload), signal,
    }),
  previewMultiPeriodTechnicalAnalysis: (payload: MultiPeriodTechnicalAnalysisRequest, signal?: AbortSignal) =>
    apiRequest<MultiPeriodTechnicalAnalysis>("/trade-training/technical-analysis/multi-period-preview", {
      method: "POST", body: JSON.stringify(payload), signal,
    }),
  getResult: (sessionId: number) => apiRequest<TrainingResult>(`/trade-training/sessions/${sessionId}/result`),
  getGptPackage: (sessionId: number) => apiRequest<TrainingGptPackage>(`/trade-training/sessions/${sessionId}/gpt-package`),
  getReview: (sessionId: number) => apiRequest<SimulationReview>(`/trade-training/sessions/${sessionId}/review`),
  saveReview: (sessionId: number, payload: SimulationReviewSaveRequest) =>
    apiRequest<SimulationReview>(`/trade-training/sessions/${sessionId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRiskScenario: (sessionId: number) =>
    apiRequest<TradeTrainingRiskScenarioDetail>(`/trade-training/sessions/${sessionId}/risk-scenario`),
  saveRiskScenarioDraft: (sessionId: number, payload: TradeTrainingRiskScenarioDraftRequest) =>
    apiRequest<TradeTrainingRiskScenarioDetail>(`/trade-training/sessions/${sessionId}/risk-scenario/draft`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  updateRiskScenario: (scenarioId: number, payload: TradeTrainingRiskScenarioDraftRequest) =>
    apiRequest<TradeTrainingRiskScenarioDetail>(`/trade-training/risk-scenarios/${scenarioId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  cancelRiskScenario: (scenarioId: number) =>
    apiRequest<TradeTrainingRiskScenarioDetail>(`/trade-training/risk-scenarios/${scenarioId}/cancel`, { method: "POST" }),
  listRiskScenarioRevisions: (scenarioId: number) =>
    apiRequest<TradeTrainingRiskScenarioRevisionListResponse>(`/trade-training/risk-scenarios/${scenarioId}/revisions`),
  getScenarioHabits: (accountId: number, params: { range: "20" | "50" | "all"; stock_id?: number; result: string; scenario: string }) => {
    const search = new URLSearchParams({ range: params.range, result: params.result, scenario: params.scenario });
    if (params.stock_id) search.set("stock_id", String(params.stock_id));
    return apiRequest<ScenarioHabitsResponse>(`/trade-training/accounts/${accountId}/scenario-habits?${search}`);
  },
  getRiskScenarioExecutionReview: (scenarioId: number) =>
    apiRequest<ScenarioExecutionReview>(`/trade-training/risk-scenarios/${scenarioId}/execution-review`),
  previewRiskOrder: (sessionId: number, payload: RiskOrderPreviewRequest) =>
    apiRequest<RiskOrderPreview>(`/trade-training/sessions/${sessionId}/risk-order-preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),  next: (sessionId: number) =>
    apiRequest<TrainingSessionDetail>(`/trade-training/sessions/${sessionId}/next`, { method: "POST" }),
  buy: (sessionId: number, payload: TrainingOrderRequest) =>
    apiRequest<TrainingSessionDetail>(`/trade-training/sessions/${sessionId}/buy`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sell: (sessionId: number, payload: TrainingOrderRequest) =>
    apiRequest<TrainingSessionDetail>(`/trade-training/sessions/${sessionId}/sell`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  finish: (sessionId: number) =>
    apiRequest<TrainingFinishResponse>(`/trade-training/sessions/${sessionId}/finish`, { method: "POST" }),
  abort: (sessionId: number) =>
    apiRequest<TrainingFinishResponse>(`/trade-training/sessions/${sessionId}/abort`, { method: "POST" }),
};
