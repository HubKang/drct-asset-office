import sampleWatchlist from "@/data/json/sampleWatchlist.json";
import type {
  WatchlistEvaluateResponse,
  WatchlistEvaluationFactor,
  WatchlistEvaluationHistoryItem,
  WatchlistEvaluationListItem,
  WatchlistEvaluationListResponse,
  WatchlistGptPromptResponse,
} from "@/types/watchlistEvaluation";
import type { Watchlist } from "@/types/watchlist";

const rows = sampleWatchlist as Watchlist[];
const historyByWatchlistId: Record<number, WatchlistEvaluationHistoryItem[]> = {};
const marketByWatchlistId: Record<number, { score: number; factors: WatchlistEvaluationFactor[]; evaluatedAt: string }> = {};
let runId = 1;
let scoreId = 1;

function mockFactors(scoreIdValue?: number): WatchlistEvaluationFactor[] {
  return [
    { id: 1, score_id: scoreIdValue, category: "MARKET", factor_code: "DOMESTIC_INDEX_TREND", factor_name: "국내 지수 흐름", normalized_score: 22, weight: 30, contribution_score: 22, raw_value: "KOSPI/KOSDAQ 대체 mock 흐름", reason: "mock 모드 시장 지수 흐름 예시입니다.", source_table: "mock", source_date: new Date().toISOString().slice(0, 10) },
    { id: 2, score_id: scoreIdValue, category: "MARKET", factor_code: "MARKET_BREADTH", factor_name: "시장 체감/폭", normalized_score: null, weight: 20, contribution_score: null, raw_value: null, reason: "상승/하락 종목 수 데이터가 없어 점수에 반영하지 않았습니다.", source_table: null, source_date: null },
    { id: 3, score_id: scoreIdValue, category: "MARKET", factor_code: "MARKET_LIQUIDITY", factor_name: "시장 유동성", normalized_score: 9, weight: 15, contribution_score: 9, raw_value: "20일 평균 대비 95%", reason: "mock 모드 유동성 예시입니다.", source_table: "mock", source_date: new Date().toISOString().slice(0, 10) },
    { id: 4, score_id: scoreIdValue, category: "MARKET", factor_code: "US_MARKET_TREND", factor_name: "미국 시장 흐름", normalized_score: null, weight: 20, contribution_score: null, raw_value: null, reason: "미국 시장 데이터가 없어 점수에 반영하지 않았습니다.", source_table: null, source_date: null },
    { id: 5, score_id: scoreIdValue, category: "MARKET", factor_code: "EXTERNAL_RISK", factor_name: "외부 위험", normalized_score: 13, weight: 15, contribution_score: 13, raw_value: "위험 감점 조건 없음", reason: "mock 모드 외부 위험 예시입니다.", source_table: "mock", source_date: new Date().toISOString().slice(0, 10) },
  ];
}

function buildItem(row: Watchlist): WatchlistEvaluationListItem {
  const history = historyByWatchlistId[row.id] || [];
  const latest = history[0];
  const market = marketByWatchlistId[row.id];
  const factors = market?.factors || [];
  return {
    watchlist_id: row.id,
    stock_id: row.stock_id,
    stock_code: row.stock_code,
    stock_name: row.stock_name,
    market: row.market,
    is_active: row.is_active === 1,
    watch_reason: row.interest_reason,
    stock_type: row.security_type || "UNCLASSIFIED",
    market_score: market?.score ?? null,
    market_status: market ? "PARTIAL" : "NOT_EVALUATED",
    market_grade: market ? "우호" : "미평가",
    market_summary: market ? "대체로 양호한 시장 환경입니다. 다만 일부 데이터가 없어 판단은 제한됩니다." : "시장 평가 전입니다.",
    market_factors: factors,
    missing_market_data: factors.filter((item) => item.contribution_score == null).map((item) => item.factor_name),
    material_score: null,
    supply_score: null,
    chart_score: null,
    financial_score: null,
    total_score: latest?.total_score ?? null,
    data_confidence: latest?.data_confidence ?? "NOT_EVALUATED",
    last_evaluated_at: latest?.evaluated_at ?? null,
    missing_data: latest?.missing_data ?? ["financial", "supply"],
  };
}

export const watchlistEvaluationMockRepository = {
  async list(): Promise<WatchlistEvaluationListResponse> {
    const items = rows.map(buildItem);
    return {
      items,
      summary: {
        watchlist_count: items.length,
        active_count: items.filter((item) => item.is_active).length,
        inactive_count: items.filter((item) => !item.is_active).length,
        evaluated_count: items.filter((item) => item.last_evaluated_at).length,
        not_evaluated_count: items.filter((item) => !item.last_evaluated_at).length,
        missing_data_count: items.filter((item) => item.missing_data.length > 0 || (item.missing_market_data || []).length > 0).length,
        last_evaluated_at: items.map((item) => item.last_evaluated_at).filter(Boolean).sort().slice(-1)[0] || null,
      },
    };
  },
  async evaluate(watchlistIds: number[]): Promise<WatchlistEvaluateResponse> {
    const now = new Date().toISOString().slice(0, 19).replace("T", " ");
    const currentRunId = runId++;
    watchlistIds.forEach((watchlistId) => {
      const currentScoreId = scoreId++;
      marketByWatchlistId[watchlistId] = { score: 67.74, factors: mockFactors(currentScoreId), evaluatedAt: now };
      historyByWatchlistId[watchlistId] = [
        {
          score_id: currentScoreId,
          run_id: currentRunId,
          run_date: now.slice(0, 10),
          run_type: "MANUAL",
          status: "SUCCESS",
          evaluated_at: now,
          market_score: 67.74,
          market_status: "PARTIAL",
          market_grade: "우호",
          material_score: null,
          supply_score: null,
          chart_score: null,
          financial_score: null,
          total_score: null,
          overall_status: "미평가",
          data_confidence: "PARTIAL",
          missing_data: ["financial", "supply", "market:MARKET_BREADTH", "market:US_MARKET_TREND"],
        },
        ...(historyByWatchlistId[watchlistId] || []),
      ];
    });
    return { run_id: currentRunId, evaluated_count: watchlistIds.length, status: "SUCCESS" };
  },
  async evaluateAll(): Promise<WatchlistEvaluateResponse> {
    return this.evaluate(rows.map((row) => row.id));
  },
  async history(watchlistId: number): Promise<WatchlistEvaluationHistoryItem[]> {
    return historyByWatchlistId[watchlistId] || [];
  },
  async createGptPrompt(watchlistId: number): Promise<WatchlistGptPromptResponse> {
    const row = rows.find((item) => item.id === watchlistId);
    return {
      watchlist_id: watchlistId,
      prompt: `DrCT 관심종목 시재수차재 평가 검토 요청: ${row?.stock_name || "-"}(${row?.stock_code || "-"})\n시장, 재료, 수급, 차트, 재무 관점에서 근거와 부족한 데이터를 구분해 주세요.`,
    };
  },
};