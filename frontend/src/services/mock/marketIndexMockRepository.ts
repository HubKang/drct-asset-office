import type {
  MarketIndexCollectRequest,
  MarketIndexCollectResponse,
  MarketIndexCompareResponse,
  MarketIndexDailyPriceItem,
  MarketIndexDailyPriceListResponse,
  MarketIndexListResponse,
} from "@/types/marketIndex";

const baseIndexes = [
  { index_code: "KOSPI", index_name: "코스피", category: "국내대표지수", market: "KOSPI", base: 2810, step: 5.4, status: "LATEST" },
  { index_code: "KOSDAQ", index_name: "코스닥", category: "국내대표지수", market: "KOSDAQ", base: 845, step: 2.1, status: "LATEST" },
  { index_code: "KOSPI200", index_name: "코스피200", category: "국내보조지수", market: "KOSPI", base: 382, step: 0.9, status: "WAITING" },
  { index_code: "KOSDAQ150", index_name: "코스닥150", category: "국내보조지수", market: "KOSDAQ", base: 1360, step: 3.3, status: "WAITING" },
  { index_code: "KOSPI_ELECTRONICS", index_name: "코스피 전기전자", category: "업종지수", market: "KOSPI", base: 28600, step: 62, status: "WAITING" },
  { index_code: "KOSDAQ_SEMICONDUCTOR", index_name: "코스닥 반도체", category: "업종지수", market: "KOSDAQ", base: 1840, step: 5.6, status: "WAITING" },
  { index_code: "KOSDAQ_PHARMA", index_name: "코스닥 제약", category: "업종지수", market: "KOSDAQ", base: 9600, step: 18, status: "NOT_COLLECTED" },
  { index_code: "GOLD_KRX", index_name: "KRX 금 현물", category: "금현물", market: "KRX", base: 142000, step: 120, status: "WAITING" },
];

const formatDate = (date: Date) => date.toISOString().slice(0, 10);

function buildRows(indexCode: string, days = 260): MarketIndexDailyPriceItem[] {
  const meta = baseIndexes.find((item) => item.index_code === indexCode) ?? baseIndexes[0];
  const today = new Date("2026-06-29T00:00:00");
  const rows: MarketIndexDailyPriceItem[] = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const wave = Math.sin((days - i) / 9) * meta.step * 8;
    const trend = (days - i) * meta.step * 0.08;
    const close = meta.base + wave + trend;
    const open = close - Math.sin(i / 5) * meta.step * 2;
    const high = Math.max(open, close) + meta.step * 3;
    const low = Math.min(open, close) - meta.step * 3;
    rows.push({
      index_code: indexCode,
      price_date: formatDate(d),
      open_price: Number(open.toFixed(2)),
      high_price: Number(high.toFixed(2)),
      low_price: Number(low.toFixed(2)),
      close_price: Number(close.toFixed(2)),
      volume: Math.round(500000 + (days - i) * 1200),
      trading_value: Math.round(8000000000000 + (days - i) * 2000000000),
      change_rate: Number((Math.sin(i / 7) * 0.8).toFixed(2)),
      source_provider: "MOCK",
    });
  }
  return rows.map((row, idx) => {
    const sma = (window: number) => {
      if (idx + 1 < window) return null;
      const part = rows.slice(idx - window + 1, idx + 1);
      return Number((part.reduce((sum, item) => sum + (item.close_price ?? 0), 0) / window).toFixed(2));
    };
    return { ...row, ma5: sma(5), ma20: sma(20), ma60: sma(60), ma120: sma(120) };
  });
}

const dailyRows = Object.fromEntries(baseIndexes.map((item) => [item.index_code, item.status === "LATEST" ? buildRows(item.index_code) : []]));

const filterRows = (indexCode: string, params?: { start_date?: string; end_date?: string }) =>
  (dailyRows[indexCode] ?? []).filter((row) => {
    if (params?.start_date && row.price_date < params.start_date) return false;
    if (params?.end_date && row.price_date > params.end_date) return false;
    return true;
  });

export const marketIndexMockRepository = {
  async list(): Promise<MarketIndexListResponse> {
    return {
      items: baseIndexes.map((item, idx) => {
        const rows = dailyRows[item.index_code] ?? [];
        const latest = rows[rows.length - 1];
        const returnRate = (days: number) => {
          const base = rows[rows.length - 1 - days];
          if (!latest?.close_price || !base?.close_price) return null;
          return Number(((latest.close_price / base.close_price - 1) * 100).toFixed(2));
        };
        return {
          id: idx + 1,
          index_code: item.index_code,
          index_name: item.index_name,
          category: item.category,
          market: item.market,
          currency: "KRW",
          provider: "MOCK",
          provider_symbol: item.status === "LATEST" ? item.index_code : null,
          description: item.status === "WAITING" ? "키움 provider mapping이 아직 설정되지 않은 지표입니다." : null,
          is_active: true,
          display_order: idx + 1,
          collection_status: item.status,
          error_message: item.status === "WAITING" ? "키움 provider mapping이 아직 설정되지 않은 지표입니다." : null,
          last_collected_date: latest?.price_date,
          latest_price_date: latest?.price_date,
          latest_close_price: latest?.close_price,
          latest_close: latest?.close_price,
          latest_volume: latest?.volume,
          latest_trading_value: latest?.trading_value,
          recent_5d_return: returnRate(5),
          recent_20d_return: returnRate(20),
          recent_5d_return_pct: returnRate(5),
          recent_20d_return_pct: returnRate(20),
        };
      }),
    };
  },
  async collect(payload: MarketIndexCollectRequest): Promise<MarketIndexCollectResponse> {
    const codes = payload.index_codes?.length ? payload.index_codes : baseIndexes.map((item) => item.index_code);
    const waiting = codes.filter((code) => baseIndexes.find((item) => item.index_code === code)?.status !== "LATEST");
    return {
      requested_count: codes.length,
      success_count: codes.length - waiting.length,
      failed_count: 0,
      saved_count: (codes.length - waiting.length) * 260,
      message: "mock market indicator collect complete",
      results: codes.map((code) => {
        const meta = baseIndexes.find((item) => item.index_code === code);
        const isWaiting = meta?.status !== "LATEST";
        return {
          index_code: code,
          index_name: meta?.index_name ?? code,
          status: isWaiting ? "WAITING" : "LATEST",
          collected_count: isWaiting ? 0 : 260,
          saved_count: isWaiting ? 0 : 260,
          from_date: payload.start_date,
          to_date: payload.end_date,
          message: isWaiting ? "키움 provider mapping이 아직 설정되지 않은 지표입니다." : "mock collect",
        };
      }),
    };
  },
  async listDailyPrices(indexCode: string, params?: { start_date?: string; end_date?: string }): Promise<MarketIndexDailyPriceListResponse> {
    return {
      index_code: indexCode,
      index_name: baseIndexes.find((item) => item.index_code === indexCode)?.index_name ?? indexCode,
      items: filterRows(indexCode, params),
    };
  },
  async compare(params?: { index_codes?: string[]; start_date?: string; end_date?: string; normalize?: boolean }): Promise<MarketIndexCompareResponse> {
    const codes = params?.index_codes?.length ? params.index_codes : ["KOSPI", "KOSDAQ"];
    return {
      normalize: params?.normalize ?? true,
      start_date: params?.start_date,
      end_date: params?.end_date,
      series: codes.map((code) => {
        const rows = filterRows(code, params);
        const first = rows.find((row) => row.close_price)?.close_price ?? 1;
        return {
          index_code: code,
          index_name: baseIndexes.find((item) => item.index_code === code)?.index_name ?? code,
          points: rows.map((row) => ({
            date: row.price_date,
            value: params?.normalize === false ? row.close_price : Number((((row.close_price ?? 0) / first) * 100).toFixed(4)),
            close_price: row.close_price,
          })),
        };
      }),
    };
  },
};
