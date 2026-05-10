import sampleWatchlist from "@/data/json/sampleWatchlist.json";
import type { Watchlist, WatchlistCreateInput, WatchlistUpdateInput } from "@/types/watchlist";

let watchlist = [...(sampleWatchlist as Watchlist[])];

export const watchlistMockRepository = {
  async list(params?: { status?: string; keyword?: string }): Promise<Watchlist[]> {
    let result = [...watchlist];
    if (params?.status) result = result.filter((w) => w.status === params.status);
    if (params?.keyword) {
      result = result.filter(
        (w) => w.stock_code.includes(params.keyword as string) || w.stock_name.includes(params.keyword as string),
      );
    }
    return result;
  },
  async create(payload: WatchlistCreateInput): Promise<Watchlist> {
    const now = new Date().toISOString();
    const item: Watchlist = {
      id: watchlist.length ? Math.max(...watchlist.map((w) => w.id)) + 1 : 1,
      stock_id: payload.stock_id,
      stock_code: `MOCK${payload.stock_id}`,
      stock_name: `종목${payload.stock_id}`,
      status: payload.status,
      interest_reason: payload.interest_reason || null,
      entry_condition: payload.entry_condition || null,
      exit_condition: payload.exit_condition || null,
      risk_note: payload.risk_note || null,
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
    watchlist = watchlist.filter((w) => w.id !== watchlistId);
  },
};
