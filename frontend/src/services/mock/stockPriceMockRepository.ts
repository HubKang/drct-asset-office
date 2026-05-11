import type {
  SelectedStockPriceCollectRequest,
  SelectedStockPriceUpdateRequest,
  StockDailyPrice,
  StockPriceCollectResult,
} from "@/types/stockPrice";

export const stockPriceMockRepository = {
  async collectSelected(payload: SelectedStockPriceCollectRequest): Promise<StockPriceCollectResult> {
    const perStock = payload.period_years * 250;
    const saved = payload.stock_ids.length * perStock;
    return {
      requested_count: payload.stock_ids.length,
      success_count: payload.stock_ids.length,
      failed_count: 0,
      saved_count: saved,
      message: "mock 데이터 캔들 수집 완료",
      results: payload.stock_ids.map((stockId) => ({
        stock_id: stockId,
        stock_code: `MOCK-${stockId}`,
        stock_name: `Mock Stock ${stockId}`,
        status: "success",
        saved_count: perStock,
        message: "mock backfill",
      })),
    };
  },
  async updateSelected(payload: SelectedStockPriceUpdateRequest): Promise<StockPriceCollectResult> {
    const perStock = 5;
    const saved = payload.stock_ids.length * perStock;
    return {
      requested_count: payload.stock_ids.length,
      success_count: payload.stock_ids.length,
      failed_count: 0,
      saved_count: saved,
      message: "mock 데이터 캔들 갱신 완료",
      results: payload.stock_ids.map((stockId) => ({
        stock_id: stockId,
        stock_code: `MOCK-${stockId}`,
        stock_name: `Mock Stock ${stockId}`,
        status: "success",
        saved_count: perStock,
        message: "mock update",
      })),
    };
  },
  async listDaily(): Promise<StockDailyPrice[]> {
    return [];
  },
};
