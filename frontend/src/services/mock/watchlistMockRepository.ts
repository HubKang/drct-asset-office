import sampleWatchlist from "@/data/json/sampleWatchlist.json";
import type {
  Watchlist,
  WatchlistBulkCreateInput,
  WatchlistBulkCreateResponse,
  WatchlistCreateInput,
  WatchlistListParams,
  WatchlistUpdateInput,
} from "@/types/watchlist";

let watchlist = [...(sampleWatchlist as Watchlist[])];

export const watchlistMockRepository = {
  async list(params?: WatchlistListParams): Promise<Watchlist[]> {
    let result = [...watchlist];
    if (params?.status) result = result.filter((w) => w.status === params.status);
    if (params?.market) result = result.filter((w) => (w.market || "") === params.market);
    if (params?.is_active !== undefined) result = result.filter((w) => w.is_active === params.is_active);
    if (params?.keyword) {
      const keyword = params.keyword;
      result = result.filter((w) => w.stock_code.includes(keyword) || w.stock_name.includes(keyword));
    }
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? result.length;
    return result.slice(offset, offset + limit);
  },
  async listStockIds(): Promise<number[]> {
    return watchlist.filter((item) => item.is_active === 1).map((item) => item.stock_id);
  },
  async bulkAdd(payload: WatchlistBulkCreateInput): Promise<WatchlistBulkCreateResponse> {
    const now = new Date().toISOString();
    let insertedCount = 0;
    let reactivatedCount = 0;
    let skippedCount = 0;

    for (const stockId of payload.stock_ids) {
      const existing = watchlist.find((item) => item.stock_id === stockId);
      if (existing?.is_active === 1) {
        skippedCount += 1;
        continue;
      }
      if (existing?.is_active === 0) {
        existing.is_active = 1;
        existing.updated_at = now;
        reactivatedCount += 1;
        continue;
      }

      const nextId = watchlist.length ? Math.max(...watchlist.map((item) => item.id)) + 1 : 1;
      watchlist = [
        {
          id: nextId,
          stock_id: stockId,
          stock_code: `MOCK${stockId}`,
          stock_name: `종목${stockId}`,
          market: "KOSPI",
          security_type: "common_stock",
          status: "관심",
          interest_reason: payload.memo || null,
          entry_condition: null,
          exit_condition: null,
          risk_note: null,
          is_active: 1,
          registered_at: now,
          updated_at: now,
        },
        ...watchlist,
      ];
      insertedCount += 1;
    }

    return {
      requested_count: payload.stock_ids.length,
      inserted_count: insertedCount,
      reactivated_count: reactivatedCount,
      skipped_count: skippedCount,
      message: `관심종목 ${insertedCount}건 추가, ${reactivatedCount}건 재활성화, ${skippedCount}건 건너뜀`,
    };
  },
  async create(payload: WatchlistCreateInput): Promise<Watchlist> {
    const now = new Date().toISOString();
    const item: Watchlist = {
      id: watchlist.length ? Math.max(...watchlist.map((w) => w.id)) + 1 : 1,
      stock_id: payload.stock_id,
      stock_code: `MOCK${payload.stock_id}`,
      stock_name: `종목${payload.stock_id}`,
      market: "KOSPI",
      security_type: "common_stock",
      status: payload.status,
      interest_reason: payload.interest_reason || null,
      entry_condition: payload.entry_condition || null,
      exit_condition: payload.exit_condition || null,
      risk_note: payload.risk_note || null,
      is_active: 1,
      registered_at: now,
      updated_at: now,
    };
    watchlist = [item, ...watchlist];
    return item;
  },
  async update(watchlistId: number, payload: WatchlistUpdateInput): Promise<Watchlist> {
    const idx = watchlist.findIndex((w) => w.id === watchlistId);
    if (idx < 0) throw new Error("watchlist not found");
    watchlist[idx] = { ...watchlist[idx], ...payload, updated_at: new Date().toISOString() };
    return watchlist[idx];
  },
  async remove(watchlistId: number): Promise<void> {
    watchlist = watchlist.map((item) =>
      item.id === watchlistId ? { ...item, is_active: 0, updated_at: new Date().toISOString() } : item,
    );
  },
};
