import { apiRequest } from "@/services/api/apiClient";
import type {
  TradeReviewDetail,
  TradeReviewGptPackage,
  TradeReviewListResponse,
  TradeReviewSaveRequest,
  TradeReviewSummary,
} from "@/types/tradeReview";

export const tradeReviewApiRepository = {
  fetchTradeReviews: (params: {
    from_date?: string;
    to_date?: string;
    review_status?: string;
    trade_grade?: string;
    result_type?: string;
    method_id?: number;
    stock_name?: string;
    main_mistake?: string;
    impulse_trade?: string;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && String(value).trim() !== "") search.set(key, String(value));
    });
    return apiRequest<TradeReviewListResponse>(`/trade-reviews?${search.toString()}`);
  },
  fetchTradeReviewSummary: (params: { from_date?: string; to_date?: string }) => {
    const search = new URLSearchParams();
    if (params.from_date) search.set("from_date", params.from_date);
    if (params.to_date) search.set("to_date", params.to_date);
    return apiRequest<TradeReviewSummary>(`/trade-reviews/summary?${search.toString()}`);
  },
  fetchTradeReviewDetail: (journalId: number) => apiRequest<TradeReviewDetail>(`/trade-reviews/${journalId}`),
  fetchTradeReviewGptPackage: (journalId: number) =>
    apiRequest<TradeReviewGptPackage>(`/trade-reviews/${journalId}/gpt-package`),
  saveTradeReview: (journalId: number, payload: TradeReviewSaveRequest) =>
    apiRequest<TradeReviewDetail>(`/trade-reviews/${journalId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
