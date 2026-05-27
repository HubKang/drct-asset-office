import { apiRequest } from "@/services/api/apiClient";
import type {
  TradeJournal,
  TradeCalendarDaySummary,
  TradeJournalImage,
  TradeJournalListResponse,
  TradeMonthlyStatisticsResponse,
  TradeJournalSaveRequest,
  TradeMethod,
  TradeMethodSaveRequest,
  TradeJournalGptReviewPackage,
} from "@/types/tradeJournal";

export const tradeJournalApiRepository = {
  listTradeMethods: (params?: { keyword?: string; is_active?: number }) => {
    const search = new URLSearchParams();
    if (params?.keyword && params.keyword.trim()) search.set("keyword", params.keyword.trim());
    if (typeof params?.is_active === "number") search.set("is_active", String(params.is_active));
    const query = search.toString();
    return apiRequest<TradeMethod[]>(`/trade-methods${query ? `?${query}` : ""}`);
  },
  createTradeMethod: (payload: TradeMethodSaveRequest) =>
    apiRequest<TradeMethod>("/trade-methods", { method: "POST", body: JSON.stringify(payload) }),
  updateTradeMethod: (methodId: number, payload: Partial<TradeMethodSaveRequest>) =>
    apiRequest<TradeMethod>(`/trade-methods/${methodId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  fetchTradeJournals: (params: {
    start_date?: string;
    end_date?: string;
    stock_name?: string;
    stock_theme?: string;
    trade_method_id?: number;
    result_type?: string;
  }) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && String(v).trim() !== "") search.set(k, String(v));
    });
    return apiRequest<TradeJournalListResponse>(`/trade-journals?${search.toString()}`);
  },
  createTradeJournal: (payload: TradeJournalSaveRequest) =>
    apiRequest<TradeJournal>("/trade-journals", { method: "POST", body: JSON.stringify(payload) }),
  fetchTradeJournalDetail: (journalId: number) => apiRequest<TradeJournal>(`/trade-journals/${journalId}`),
  updateTradeJournal: (journalId: number, payload: Partial<TradeJournalSaveRequest>) =>
    apiRequest<TradeJournal>(`/trade-journals/${journalId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTradeJournal: (journalId: number) => apiRequest<{ success: boolean }>(`/trade-journals/${journalId}`, { method: "DELETE" }),
  fetchTradeJournalImages: (journalId: number) => apiRequest<TradeJournalImage[]>(`/trade-journals/${journalId}/images`),
  uploadTradeJournalImage: (
    journalId: number,
    payload: { image_type: string; image_memo?: string; file: File }
  ) => {
    const formData = new FormData();
    formData.set("image_type", payload.image_type);
    if (payload.image_memo) formData.set("image_memo", payload.image_memo);
    formData.set("file", payload.file);
    return apiRequest<TradeJournalImage>(`/trade-journals/${journalId}/images/upload`, {
      method: "POST",
      body: formData,
    });
  },
  updateTradeJournalImage: (
    imageId: number,
    payload: { image_memo?: string; image_type?: string }
  ) => apiRequest<TradeJournalImage>(`/trade-journal-images/${imageId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTradeJournalImage: (imageId: number) =>
    apiRequest<{ success: boolean }>(`/trade-journal-images/${imageId}`, { method: "DELETE" }),
  fetchTradeCalendarMonthly: (month: string) =>
    apiRequest<TradeCalendarDaySummary[]>(`/trade-journals/calendar/monthly?month=${encodeURIComponent(month)}`),
  fetchTradeCalendarDaily: (date: string) =>
    apiRequest<TradeJournalListResponse>(`/trade-journals/calendar/daily?date=${encodeURIComponent(date)}`),
  fetchTradeMonthlyStatistics: (params: {
    page?: number;
    page_size?: number;
    start_month?: string;
    end_month?: string;
  }) => {
    const search = new URLSearchParams();
    if (params.page) search.set("page", String(params.page));
    if (params.page_size) search.set("page_size", String(params.page_size));
    if (params.start_month) search.set("start_month", params.start_month);
    if (params.end_month) search.set("end_month", params.end_month);
    return apiRequest<TradeMonthlyStatisticsResponse>(`/trade-journals/statistics/monthly?${search.toString()}`);
  },
  fetchGptReviewPackage: (journalId: number) => apiRequest<TradeJournalGptReviewPackage>(`/trade-journals/${journalId}/gpt-review-package`),
};
