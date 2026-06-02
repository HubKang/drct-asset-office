import { apiRequest } from "@/services/api/apiClient";
import type {
  TrainingFinishResponse,
  TrainingGptPackage,
  TrainingOrderRequest,
  TrainingResult,
  SimulationReview,
  SimulationReviewSaveRequest,
  TrainingSessionCreate,
  TrainingSessionDetail,
  TrainingStockListResponse,
} from "@/types/tradeTraining";

export const tradeTrainingApiRepository = {
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
