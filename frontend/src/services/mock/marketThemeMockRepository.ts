import type {
  MarketThemeCandidate,
  MarketThemeCandidateApproveResult,
  MarketThemeCandidateGenerateInput,
  MarketThemeCandidateGenerateResult,
  MarketThemeCandidateReviewInput,
  MarketThemeByStockResponse,
  MarketTheme,
  MarketThemeCreateInput,
  MarketThemeLatestReturnDetail,
  MarketThemeListParams,
  MarketThemeMonthlyReturnParams,
  MarketThemeMonthlyReturnResponse,
  MarketThemePriceFlowChartParams,
  MarketThemePriceFlowChartResponse,
  MarketThemeFlowChartResponse,
  MarketThemeFlowTrendParams,
  MarketThemeFlowTrendResponse,
  MarketThemeRangeReturnParams,
  MarketThemeReturnRefreshRequest,
  MarketThemeReturnRecalculationPreview,
  MarketThemeReturnRecalculationResponse,
  MarketThemeReturnRefreshResponse,
  MarketThemeReturnPredictionResponse,
  MarketThemeReturnMLStatus,
  MarketThemeReturnMLTrainResponse,
  MarketThemeObservationResponse,
  MarketThemeObservationMLTrainResponse,
  MarketThemeObservationDiagnosticsResponse,
  MarketThemeStock,
  RealtimeThemeRefreshResponse,
  RealtimeThemeStocksResponse,
  RealtimeThemeTreemapResponse,
  MarketThemeStockCreateInput,
  MarketThemeStockMemoUpdateInput,
  MarketThemeStockMemoResponse,
  MarketThemeStockSupplySummary,
  MarketThemeStockUpdateInput,
  MarketThemeUpdateInput,
} from "@/types/marketTheme";

const themes: MarketTheme[] = [];
const mappings: MarketThemeStock[] = [];
const candidates: MarketThemeCandidate[] = [];

export const marketThemeMockRepository = {
  async getRealtimeTreemap(): Promise<RealtimeThemeTreemapResponse> {
    return { trade_date: new Date().toISOString().slice(0, 10), snapshot_at: null, theme_count: 0, linked_stock_count: 0, unique_stock_count: 0, valid_stock_count: 0, failed_stock_count: 0, themes: [] };
  },
  async refreshRealtimeTreemap(): Promise<RealtimeThemeRefreshResponse> {
    return { ...(await this.getRealtimeTreemap()), success: true, price_api_call_count: 0, kiwoom_fetch_ms: 0, db_upsert_ms: 0, theme_aggregation_ms: 0, snapshot_response_ms: 0, stock_fetch_min_ms: null, stock_fetch_avg_ms: null, stock_fetch_max_ms: null, duration_ms: 0, message: "mock Snapshot" };
  },
  async getRealtimeThemeStocks(themeId: number): Promise<RealtimeThemeStocksResponse> {
      return { theme_id: themeId, theme_name: "", theme_rank: 0, theme_change_rate: null, trade_date: new Date().toISOString().slice(0, 10), snapshot_at: null, linked_stock_count: 0, valid_stock_count: 0, stocks: [] };
  },
  async getObservationDiagnostics(): Promise<MarketThemeObservationDiagnosticsResponse> {
    const empty = { evaluated_days: 0, precision_top20: null, precision_at_5: null, ndcg_at_5: null, spearman: null, mean_rank_error: null };
    return { quality_evaluated_days: 0, recent_5: { quality_days: 0, current: empty, refreshed: empty },
      recent_20: { quality_days: 0, current: empty, refreshed: empty }, all: { quality_days: 0, current: empty, refreshed: empty },
      paired_correction: { paired_days: 0, mean_rank_error_current: null, mean_rank_error_refreshed: null, mean_refresh_effect: null, improved_theme_count: 0, worsened_theme_count: 0, unchanged_theme_count: 0 },
      status_performance: [], score_bucket_performance: [], diagnostic_status: "INSUFFICIENT_DATA",
      messages: [{ code: "INSUFFICIENT_DATA", severity: "INFO", title: "데이터 축적 중", message: "아직 로직 변경을 판단하기에는 데이터가 부족합니다." }], ml_quality_days_since_training: 0 };
  },
  async getLatestObservationPriority(): Promise<MarketThemeObservationResponse> {
    return { status: "DRAFT", message: "저장된 관찰 우선순위가 없습니다.", data_cutoff_date: null, calculation_data_cutoff_date: null, default_target_date: null, run: null, items: [], metrics: null, actual_universe_count: null, market_indicator_latest_refreshed_at: null };
  },
  async getObservationPriority(_targetDate: string): Promise<MarketThemeObservationResponse> { return this.getLatestObservationPriority(); },
  async calculateObservationPriority(_targetDate: string, _refreshMarketIndicators = false): Promise<MarketThemeObservationResponse> { return this.getLatestObservationPriority(); },
  async validateObservationPriority(_targetDate: string): Promise<MarketThemeObservationResponse> { return this.getLatestObservationPriority(); },
  async trainObservationML(): Promise<MarketThemeObservationMLTrainResponse> {
    return { status: "INSUFFICIENT_DATA", message: "Mock 데이터가 없습니다.", feature_version: "THEME_OBSERVATION_FEATURE_V1", train_start_date: null, train_end_date: null, distinct_base_dates: 0, train_row_count: 0, qualified_date_count: 0, excluded_universe_dates: 0, validation_fold_count: 0, candidates: [] };
  },
  async getLatestReturnPrediction(): Promise<MarketThemeReturnPredictionResponse> {
    return { status: "DRAFT", message: "저장된 예측이 없습니다.", data_cutoff_date: null, default_target_date: null, run: null, items: [], shadow_items: [], metrics: null, recommendations: [], method_metrics: [] };
  },
  async getReturnPrediction(_targetDate: string): Promise<MarketThemeReturnPredictionResponse> {
    return this.getLatestReturnPrediction();
  },
  async predictReturns(_targetDate: string): Promise<MarketThemeReturnPredictionResponse> {
    throw new Error("mock mode: predictReturns not implemented");
  },
  async validateReturnPrediction(_targetDate: string): Promise<MarketThemeReturnPredictionResponse> {
    throw new Error("mock mode: validateReturnPrediction not implemented");
  },
  async getReturnMLStatus(): Promise<MarketThemeReturnMLStatus> {
    return { status: "UNAVAILABLE", available: false, model_version: null, model_type: null, feature_version: null, trained_at: null,
      train_start_date: null, train_end_date: null, distinct_train_dates: 0, train_row_count: 0, validation_fold_count: 0,
      validation_metrics: null, rule_metrics: null, baseline_metrics: null, artifact_path: null, common_evaluated_runs: 0,
      cumulative_rule_mae: null, cumulative_ml_mae: null, cumulative_rule_precision_at_5: null,
      cumulative_ml_precision_at_5: null, cumulative_rule_ndcg_at_5: null, cumulative_ml_ndcg_at_5: null,
      promotion_readiness: "NOT_READY", target_type: null, selection_gate_status: "NOT_EVALUATED", selection_reason: null,
      readiness: "NOT_READY", drift_status: "WATCH", recent_5: null, recent_20: null, all_common: null,
      remaining_runs_for_review: 20, advice_code: "ML_SAMPLE_INSUFFICIENT", advice_message: "실전 공통 검증 데이터가 부족합니다." };
  },
  async trainReturnMLShadow(): Promise<MarketThemeReturnMLTrainResponse> {
    throw new Error("mock mode: trainReturnMLShadow not implemented");
  },
  async trainReturnMLRankCandidates(): Promise<MarketThemeReturnMLTrainResponse> {
    throw new Error("mock mode: trainReturnMLRankCandidates not implemented");
  },
  async selectReturnMLShadow(_modelVersion: string): Promise<MarketThemeReturnMLStatus> {
    throw new Error("mock mode: selectReturnMLShadow not implemented");
  },
  async predictReturnMLShadow(_targetDate: string): Promise<MarketThemeReturnPredictionResponse> {
    throw new Error("mock mode: predictReturnMLShadow not implemented");
  },
  async list(_params?: MarketThemeListParams): Promise<MarketTheme[]> {
    return themes;
  },
  async get(themeId: number): Promise<MarketTheme> {
    const row = themes.find((x) => x.id === themeId);
    if (!row) throw new Error("market theme not found");
    return row;
  },
  async create(_payload: MarketThemeCreateInput): Promise<MarketTheme> {
    throw new Error("mock mode: create not implemented");
  },
  async update(_themeId: number, _payload: MarketThemeUpdateInput): Promise<MarketTheme> {
    throw new Error("mock mode: update not implemented");
  },
  async deactivate(_themeId: number): Promise<MarketTheme> {
    throw new Error("mock mode: deactivate not implemented");
  },
  async delete(_themeId: number) {
    throw new Error("mock mode: delete not implemented");
  },
  async refreshReturns(_payload: MarketThemeReturnRefreshRequest): Promise<MarketThemeReturnRefreshResponse> {
    return {
      success: true,
      return_date: new Date().toISOString().slice(0, 10),
      refreshed_at: new Date().toISOString(),
      theme_count: 0,
      stock_count: 0,
      success_stock_count: 0,
      failed_stock_count: 0,
      inserted_count: 0,
      updated_count: 0,
      rest_post_calls: 0,
      auth_token_issue_count: 0,
      ka10001_calls: 0,
      ka10015_calls: 0,
      items: [],
      message: "mock mode: 갱신할 테마가 없습니다.",
    };
  },
  async startPriceFlowRefresh(_payload: MarketThemeReturnRefreshRequest) {
    return {
      job_id: "mock-theme-price-flow",
      status: "PENDING",
      message: "작업 시작을 기다리고 있습니다.",
      requested_at: new Date().toISOString(),
    };
  },
  async getPriceFlowRefreshJob(jobId: string) {
    return {
      job_id: jobId,
      status: "COMPLETED" as const,
      stage: "COMPLETED",
      completed_count: 0,
      total_count: 0,
      current_stage: "COMPLETED",
      current_stage_label: "작업 완료",
      completed_stock_count: 0,
      total_stock_count: 0,
      failed_stock_count: 0,
      price_result: { target_count: 0, attempted_count: 0, success_count: 0, up_to_date_count: 0, no_data_count: 0, skipped_count: 0, failed_count: 0, inserted_rows: 0, updated_rows: 0 },
      technical_indicator_result: { target_count: 0, attempted_count: 0, success_count: 0, up_to_date_count: 0, no_data_count: 0, skipped_count: 0, failed_count: 0, inserted_rows: 0, updated_rows: 0 },
      investor_flow_result: { target_count: 0, attempted_count: 0, success_count: 0, up_to_date_count: 0, no_data_count: 0, skipped_count: 0, failed_count: 0, inserted_rows: 0, updated_rows: 0 },
      program_flow_result: { target_count: 0, attempted_count: 0, success_count: 0, up_to_date_count: 0, no_data_count: 0, skipped_count: 0, failed_count: 0, inserted_rows: 0, updated_rows: 0 },
      theme_return_result: { target_count: 0, attempted_count: 0, success_count: 0, up_to_date_count: 0, no_data_count: 0, skipped_count: 0, failed_count: 0, inserted_rows: 0, updated_rows: 0 },
      requested_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      error: null,
      failures: [],
      message: "mock mode: 갱신할 테마가 없습니다.",
      result: await this.refreshReturns({ scope: "all_active" }),
    };
  },
  async getStockPriceFlowChart(stockId: number, params: MarketThemePriceFlowChartParams): Promise<MarketThemePriceFlowChartResponse> {
    const stock = mappings.find((row) => row.stock_id === stockId);
    if (!stock) throw new Error("market theme stock not found");
    const requestedDays = params.period === "1M" ? 20 : params.period === "3M" ? 63 : 126;
    return {
      stock: { stock_id: stock.stock_id, stock_code: stock.stock_code, stock_name: stock.stock_name, market: stock.market ?? null },
      requested_unit: params.unit,
      requested_view: params.view,
      period: { code: params.period, requested_trading_days: requestedDays, actual_trading_days: 0, start_date: null, end_date: null },
      latest_dates: { price: null, investor: null, program: null, common: null },
      data_quality: { status: "EMPTY", valid_days: 0, missing_price_days: 0, missing_investor_days: 0, missing_program_days: 0, completeness_ratio: 0 },
      summary: {
        price_return_pct: null, individual_cumulative: null, foreign_cumulative: null,
        institution_cumulative: null, program_cumulative: null, individual_positive_days: 0,
        foreign_positive_days: 0, institution_positive_days: 0, program_positive_days: 0,
        individual_streak: 0, foreign_streak: 0, institution_streak: 0, program_streak: 0,
      },
      series: [],
      events: [],
    };
  },
  async getThemePriceFlowChart(themeId: number, params: { period: "1M" | "3M" | "6M"; focus_date?: string }): Promise<MarketThemeFlowChartResponse> {
    const theme = themes.find((row) => row.id === themeId);
    if (!theme) throw new Error("market theme not found");
    const requestedDays = params.period === "1M" ? 20 : params.period === "3M" ? 63 : 126;
    const emptyActor = { cumulative_amount: null, positive_days: 0, positive_stock_count: 0, data_stock_count: 0 };
    return {
      theme_id: themeId, theme_name: theme.theme_name,
      period: { code: params.period, requested_trading_days: requestedDays, actual_trading_days: 0, start_date: null, end_date: null },
      latest_theme_return_date: null, latest_flow_date: null, common_latest_date: null,
      aggregation_basis: "CURRENT_ACTIVE_LINKS", attribution_mode: "FULL", data_quality: "EMPTY",
      summary: { theme_return_pct: null, individual: emptyActor, foreign: emptyActor, institution: emptyActor, program: emptyActor },
      series: [], focus_date: params.focus_date ?? null, selected: null,
    };
  },
  async getThemeFlowTrend(params: MarketThemeFlowTrendParams): Promise<MarketThemeFlowTrendResponse> {
    return {
      request: {
        end_date: params.end_date, actual_end_date: null, recent_days: params.recent_days ?? 30,
        actor: params.actor, metric: params.metric, attribution_mode: params.attribution,
        aggregation_basis: "CURRENT_ACTIVE_LINKS", theme_group_id: params.theme_group_id ?? null,
        search: params.search ?? null, limit: params.limit ?? null,
      },
      dates: [], summary: { top_today: null, top_five_day: null, top_breadth: null, top_streak: null },
      themes: [], performance: { cache_hit: false },
    };
  },
  async getLatestReturn(themeId: number): Promise<MarketThemeLatestReturnDetail> {
    const row = themes.find((x) => x.id === themeId);
    if (!row) throw new Error("market theme not found");
    return {
      theme_id: row.id,
      theme_name: row.theme_name,
      theme_group_name: row.parent_theme_name ?? null,
      return_date: null,
      avg_change_rate: null,
      snapshot_at: null,
      stock_count: row.stock_count,
      success_stock_count: 0,
      failed_stock_count: 0,
      rising_stock_count: 0,
      falling_stock_count: 0,
      flat_stock_count: 0,
      total_trading_value_100m: null,
      stocks: [],
    };
  },
  async getDailyReturn(themeId: number, date: string): Promise<MarketThemeLatestReturnDetail> {
    const detail = await this.getLatestReturn(themeId);
    return { ...detail, return_date: date };
  },
  async getReturnRecalculationPreview(themeId: number): Promise<MarketThemeReturnRecalculationPreview> {
    const row = themes.find((theme) => theme.id === themeId);
    if (!row) throw new Error("market theme not found");
    return {
      theme_id: row.id,
      theme_name: row.theme_name,
      connected_stock_count: row.stock_count,
      period_from: null,
      period_to: null,
      data_source: "STORED_STOCK_DAILY_PRICES",
    };
  },
  async recalculateReturns(themeId: number): Promise<MarketThemeReturnRecalculationResponse> {
    const preview = await this.getReturnRecalculationPreview(themeId);
    return {
      ...preview,
      success: true,
      processed_date_count: 0,
      inserted_count: 0,
      updated_count: 0,
      skipped_date_count: 0,
      recalculated_at: new Date().toISOString(),
    };
  },
  async listMonthlyReturns(params: MarketThemeMonthlyReturnParams): Promise<MarketThemeMonthlyReturnResponse> {
    const [year, month] = params.month.split("-").map(Number);
    const endDate = new Date(year, month, 0).getDate();
    return {
      month: params.month,
      active_only: params.active_only ?? true,
      display_start_date: `${params.month}-01`,
      display_end_date: `${params.month}-${String(endDate).padStart(2, "0")}`,
      themes: [],
      summary: {
        top_rising_theme: null,
        top_falling_theme: null,
        top_trading_value_theme: null,
        rising_day_theme: null,
      },
    };
  },
  async listRangeReturns(params: MarketThemeRangeReturnParams): Promise<MarketThemeMonthlyReturnResponse> {
    const end = new Date(`${params.end_date}T00:00:00`);
    const start = new Date(end);
    start.setDate(start.getDate() - ((params.days ?? 30) - 1));
    return {
      month: params.end_date.slice(0, 7),
      end_date: params.end_date,
      days: params.days ?? 30,
      active_only: params.active_only ?? true,
      display_start_date: start.toISOString().slice(0, 10),
      display_end_date: params.end_date,
      themes: [],
      summary: {
        top_rising_theme: null,
        top_falling_theme: null,
        top_trading_value_theme: null,
        rising_day_theme: null,
        top_continuous_rising_theme: null,
      },
    };
  },
  async listThemeStocks(themeId: number): Promise<MarketThemeStock[]> {
    return mappings.filter((x) => x.theme_id === themeId);
  },
  async getThemeStockSupplySummary(themeId: number, stockId: number): Promise<MarketThemeStockSupplySummary> {
    const row = mappings.find((item) => item.theme_id === themeId && item.stock_id === stockId);
    return {
      theme_id: themeId,
      theme_name: themes.find((theme) => theme.id === themeId)?.theme_name ?? "-",
      stock_id: stockId,
      stock_code: row?.stock_code ?? "",
      stock_name: row?.stock_name ?? "-",
      supply_day_count: row?.supply_day_count ?? 0,
      recent_30d_supply_day_count: row?.recent_30d_supply_day_count ?? 0,
      first_supply_date: row?.first_supply_date ?? null,
      last_supply_date: row?.last_supply_date ?? null,
      all_theme_supply_day_count: row?.supply_day_count ?? 0,
      recent_supply_dates: [],
      current_theme: {
        theme_id: themeId,
        theme_name: themes.find((theme) => theme.id === themeId)?.theme_name ?? "-",
        color: "#dc2626",
      },
      linked_theme_supply_summaries: [],
      period_start_date: "",
      period_end_date: "",
      recent_30d_theme_supply_count: row?.recent_30d_supply_day_count ?? 0,
      current_theme_supply_count: row?.supply_day_count ?? 0,
      overall_stock_supply_count: row?.supply_day_count ?? 0,
      latest_current_theme_supply_date: row?.last_supply_date ?? null,
      first_current_theme_supply_date: row?.first_supply_date ?? null,
      current_theme_supply_dates: [],
      overall_stock_supply_dates: [],
      stock_memos: [],
    };
  },
  async createThemeStock(_themeId: number, _payload: MarketThemeStockCreateInput): Promise<MarketThemeStock> {
    throw new Error("mock mode: createThemeStock not implemented");
  },
  async updateThemeStockMemo(_themeId: number, _stockId: number, _payload: MarketThemeStockMemoUpdateInput): Promise<MarketThemeStock> {
    throw new Error("mock mode: updateThemeStockMemo not implemented");
  },
  async updateThemeStock(_mappingId: number, _payload: MarketThemeStockUpdateInput): Promise<MarketThemeStock> {
    throw new Error("mock mode: updateThemeStock not implemented");
  },
  async deactivateThemeStock(_mappingId: number): Promise<MarketThemeStock> {
    throw new Error("mock mode: deactivateThemeStock not implemented");
  },
  async listThemesByStockCode(stockCode: string): Promise<MarketThemeByStockResponse> {
    return {
      stock_code: stockCode,
      stock_name: null,
      themes: [],
    };
  },
  async listStockMemos(stockCode: string): Promise<MarketThemeStockMemoResponse> {
    return {
      stock_code: stockCode,
      stock_name: null,
      items: [],
    };
  },
  async listCandidates(): Promise<MarketThemeCandidate[]> {
    return candidates;
  },
  async generateCandidates(_payload: MarketThemeCandidateGenerateInput): Promise<MarketThemeCandidateGenerateResult> {
    return {
      generated_count: 0,
      updated_count: 0,
      skipped_existing_mapping_count: 0,
      skipped_rejected_count: 0,
      source: "all",
      lookback_days: 7,
    };
  },
  async approveCandidate(_candidateId: number): Promise<MarketThemeCandidateApproveResult> {
    throw new Error("mock mode: approveCandidate not implemented");
  },
  async rejectCandidate(_candidateId: number, _payload: MarketThemeCandidateReviewInput): Promise<MarketThemeCandidate> {
    throw new Error("mock mode: rejectCandidate not implemented");
  },
  async ignoreCandidate(_candidateId: number, _payload: MarketThemeCandidateReviewInput): Promise<MarketThemeCandidate> {
    throw new Error("mock mode: ignoreCandidate not implemented");
  },
};
