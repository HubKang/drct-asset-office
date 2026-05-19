import type {
  MarketThemeCandidate,
  MarketThemeCandidateApproveResult,
  MarketThemeCandidateGenerateInput,
  MarketThemeCandidateGenerateResult,
  MarketThemeCandidateReviewInput,
  MarketTheme,
  MarketThemeCreateInput,
  MarketThemeListParams,
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
  async listThemeStocks(themeId: number): Promise<MarketThemeStock[]> {
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
