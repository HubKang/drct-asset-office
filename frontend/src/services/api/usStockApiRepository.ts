import { apiRequest } from "@/services/api/apiClient";
import type { UsPriceCollectionMode, UsPriceCollectionResponse, UsStock, UsStockBulkCreateResponse, UsStockBulkInput, UsStockBulkPreviewResponse, UsStockDeleteImpact, UsStockDeleteResponse, UsStockInput, UsStockListResponse, UsStockSummary, UsStockUpdateInput } from "@/types/usStock";

export const usStockApiRepository = {
  list: (params: { keyword?: string; exchange?: string; stock_type?: string; is_active?: number; price_status?: string; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") search.set(key, String(value));
    });
    return apiRequest<UsStockListResponse>(`/us-stocks?${search.toString()}`);
  },
  summary: () => apiRequest<UsStockSummary>("/us-stocks/summary"),
  create: (payload: UsStockInput) => apiRequest<UsStock>("/us-stocks", { method: "POST", body: JSON.stringify(payload) }),
  update: (stockId: number, payload: UsStockUpdateInput) => apiRequest<UsStock>(`/us-stocks/${stockId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteImpact: (stockId: number) => apiRequest<UsStockDeleteImpact>(`/us-stocks/${stockId}/delete-impact`),
  delete: (stockId: number, confirmSymbol: string) => apiRequest<UsStockDeleteResponse>(`/us-stocks/${stockId}?confirm_symbol=${encodeURIComponent(confirmSymbol)}`, { method: "DELETE" }),
  previewBulk: (payload: UsStockBulkInput) => apiRequest<UsStockBulkPreviewResponse>("/us-stocks/bulk/preview", { method: "POST", body: JSON.stringify(payload) }),
  createBulk: (payload: UsStockBulkInput) => apiRequest<UsStockBulkCreateResponse>("/us-stocks/bulk", { method: "POST", body: JSON.stringify(payload) }),
  collectPrices: (mode: UsPriceCollectionMode, stockIds?: number[]) => apiRequest<UsPriceCollectionResponse>("/us-stocks/prices/collect", { method: "POST", body: JSON.stringify({ mode, trading_days: 260, stock_ids: stockIds }), timeoutMs: 300000 }),
};
