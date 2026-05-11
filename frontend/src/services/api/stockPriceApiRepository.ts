import { apiRequest } from "@/services/api/apiClient";
import type {
  SelectedStockPriceCollectRequest,
  SelectedStockPriceUpdateRequest,
  StockDailyPrice,
  StockPriceCollectResult,
} from "@/types/stockPrice";

export const stockPriceApiRepository = {
  collectSelected: (payload: SelectedStockPriceCollectRequest) =>
    apiRequest<StockPriceCollectResult>("/stock-prices/collect/selected", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateSelected: (payload: SelectedStockPriceUpdateRequest) =>
    apiRequest<StockPriceCollectResult>("/stock-prices/update/selected", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listDaily: (stockId: number, params?: { start_date?: string; end_date?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    if (params?.start_date) search.set("start_date", params.start_date);
    if (params?.end_date) search.set("end_date", params.end_date);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<StockDailyPrice[]>(`/stock-prices/${stockId}/daily${query ? `?${query}` : ""}`);
  },
};
