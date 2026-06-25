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
  MarketThemeRangeReturnParams,
  MarketThemeReturnRefreshRequest,
  MarketThemeReturnRefreshResponse,
  MarketThemeStock,
  MarketThemeStockCreateInput,
  MarketThemeStockUpdateInput,
  MarketThemeUpdateInput,
} from "@/types/marketTheme";

const themes: MarketTheme[] = [];
const mappings: MarketThemeStock[] = [];
const candidates: MarketThemeCandidate[] = [];

export const marketThemeMockRepository = {
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
      items: [],
      message: "mock mode: 갱신할 테마가 없습니다.",
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
  },  async listThemeStocks(themeId: number): Promise<MarketThemeStock[]> {
    return mappings.filter((x) => x.theme_id === themeId);
  },
  async createThemeStock(_themeId: number, _payload: MarketThemeStockCreateInput): Promise<MarketThemeStock> {
    throw new Error("mock mode: createThemeStock not implemented");
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
