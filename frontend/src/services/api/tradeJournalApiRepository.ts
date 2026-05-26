import { apiRequest } from "@/services/api/apiClient";
import type {
  TradeJournal,
  TradeJournalImage,
  TradeJournalListResponse,
  TradeJournalSaveRequest,
  TradeMethod,
  TradeMethodSaveRequest,
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
  createTradeJournalImage: (
    journalId: number,
    payload: { image_type: string; image_path: string; image_memo?: string; original_filename?: string }
  ) => apiRequest<TradeJournalImage>(`/trade-journals/${journalId}/images`, { method: "POST", body: JSON.stringify(payload) }),
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
  deleteTradeJournalImage: (imageId: number) =>
    apiRequest<{ success: boolean }>(`/trade-journal-images/${imageId}`, { method: "DELETE" }),
};
