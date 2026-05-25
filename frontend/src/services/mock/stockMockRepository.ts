import sampleStocks from "@/data/json/sampleStocks.json";
import type {
  Stock,
  StockCodeNormalizeResponse,
  StockCreateInput,
  StockListParams,
  StockUpdateInput,
} from "@/types/stock";
import type { StockSyncRequest, StockSyncResponse } from "@/types/stockSync";

let stocks = [...(sampleStocks as Stock[])];

export const stockMockRepository = {
  async list(params?: string | StockListParams): Promise<Stock[]> {
    let result = [...stocks];
    if (typeof params === "string") {
      if (params) result = result.filter((s) => s.stock_code.includes(params) || s.stock_name.includes(params));
      return result;
    }
    if (params?.keyword) result = result.filter((s) => s.stock_code.includes(params.keyword as string) || s.stock_name.includes(params.keyword as string));
    if (params?.market) result = result.filter((s) => (s.market || "") === params.market);
    if (params?.is_active !== undefined) result = result.filter((s) => s.is_active === params.is_active);
    if (params?.security_type) result = result.filter((s) => (s.security_type || "common_stock") === params.security_type);
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 500;
    return result.slice(offset, offset + limit);
  },
  async create(payload: StockCreateInput): Promise<Stock> {
    const now = new Date().toISOString();
    const item: Stock = {
      id: stocks.length ? Math.max(...stocks.map((s) => s.id)) + 1 : 1,
      stock_code: payload.stock_code,
      stock_name: payload.stock_name,
      market: payload.market || null,
      sector: payload.sector || null,
      industry: payload.industry || null,
      isin_code: null,
      corp_name: null,
      corp_reg_no: null,
      last_synced_at: null,
      source: null,
      security_type: payload.security_type || "common_stock",
      is_active: 1,
      created_at: now,
      updated_at: now,
    };
    stocks = [item, ...stocks];
    return item;
  },
  async update(stockId: number, payload: StockUpdateInput): Promise<Stock> {
    const idx = stocks.findIndex((s) => s.id === stockId);
    if (idx < 0) throw new Error("stock not found");
    stocks[idx] = { ...stocks[idx], ...payload, updated_at: new Date().toISOString() };
    return stocks[idx];
  },
  async deactivate(stockId: number): Promise<Stock> {
    return this.update(stockId, { is_active: 0 });
  },
  async syncStocks(payload: StockSyncRequest): Promise<StockSyncResponse> {
    const now = new Date().toISOString();
    return {
      markets: payload.markets,
      dry_run: payload.dry_run,
      raw_fetched_count: 0,
      eligible_count: 0,
      type_counts: {},
      fetched_count: 0,
      inserted_count: 0,
      updated_count: 0,
      reactivated_count: 0,
      deactivated_count: 0,
      skipped_count: 0,
      error_count: 0,
      started_at: now,
      finished_at: now,
      message: "mock mode: stock sync preview",
    };
  },
  async normalizeCodes(dryRun = false): Promise<StockCodeNormalizeResponse> {
    const targets = stocks.filter((s) => /^A\d{6}$/i.test(s.stock_code));
    const items = targets.map((s) => ({
      stock_id: s.id,
      stock_name: s.stock_name,
      old_code: s.stock_code,
      new_code: s.stock_code.slice(1),
      status: dryRun ? "will_update" : "updated",
    }));
    if (!dryRun) {
      stocks = stocks.map((s) => (/^A\d{6}$/i.test(s.stock_code) ? { ...s, stock_code: s.stock_code.slice(1) } : s));
    }
    return {
      dry_run: dryRun,
      target_count: items.length,
      updated_count: dryRun ? 0 : items.length,
      duplicate_conflict_count: 0,
      items,
    };
  },
};
