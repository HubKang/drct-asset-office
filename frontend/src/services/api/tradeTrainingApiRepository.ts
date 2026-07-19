import { apiRequest } from "@/services/api/apiClient";
import type {
  TrainingFinishResponse,
  TrainingGptPackage,
  TrainingOrderRequest,
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
  TrainingSessionCreate,
  TrainingSessionDetail,
  TrainingStockListResponse,
} from "@/types/tradeTraining";

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
  listStocks: (params?: { q?: string; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiRequest<TrainingStockListResponse>(`/trade-training/stocks${query ? `?${query}` : ""}`);
  },
  createSession: (payload: TrainingSessionCreate) =>
    apiRequest<TrainingSessionDetail>("/trade-training/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSession: (sessionId: number) => apiRequest<TrainingSessionDetail>(`/trade-training/sessions/${sessionId}`),
  getResult: (sessionId: number) => apiRequest<TrainingResult>(`/trade-training/sessions/${sessionId}/result`),
  getGptPackage: (sessionId: number) => apiRequest<TrainingGptPackage>(`/trade-training/sessions/${sessionId}/gpt-package`),
  getReview: (sessionId: number) => apiRequest<SimulationReview>(`/trade-training/sessions/${sessionId}/review`),
  saveReview: (sessionId: number, payload: SimulationReviewSaveRequest) =>
    apiRequest<SimulationReview>(`/trade-training/sessions/${sessionId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  next: (sessionId: number) =>
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
