import { apiRequest } from "@/services/api/apiClient";
import type {
  AdvisoryEvidencePackageResponse,
  MarketIndicatorsOverviewResponse,
  MarketMetricsSummaryResponse,
  SelectedMarketMetricsCollectRequest,
  SelectedMarketMetricsCollectResult,
  SelectedStockPriceCollectRequest,
  StockDailyPriceListResponse,
  StockPriceCollectResult,
  StockPriceFactSummaryResponse,
  StockPriceSummaryResponse,
  TechnicalIndicatorBatchCalculationResult,
  TechnicalIndicatorCalculationResult,
} from "@/types/stockPrice";

export const stockPriceApiRepository = {
  collectSelected: (payload: SelectedStockPriceCollectRequest) =>
    apiRequest<StockPriceCollectResult>("/stock-prices/collect/selected", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  collectSelectedMarketMetrics: (payload: SelectedMarketMetricsCollectRequest) =>
    apiRequest<SelectedMarketMetricsCollectResult>("/market-metrics/collect/selected", {
      method: "POST",
      body: JSON.stringify({
        stock_ids: payload.stock_ids,
        source: payload.source ?? "kiwoom_rest",
      }),
    }),
  calculateTechnicalIndicators: (stockId: number) =>
    apiRequest<TechnicalIndicatorCalculationResult>(`/technical-indicators/calculate/stock/${stockId}`, {
      method: "POST",
    }),
  calculateTechnicalIndicatorsForSelected: (stockIds: number[]) =>
    apiRequest<TechnicalIndicatorBatchCalculationResult>("/technical-indicators/calculate/selected", {
      method: "POST",
      body: JSON.stringify({ stock_ids: stockIds }),
    }),
  listSummary: (params?: { keyword?: string; market?: string; source?: string; scope?: "watchlist" | "all"; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    const resolvedSource = params?.source ?? "kiwoom_rest";
    const resolvedScope = params?.scope ?? "watchlist";
    if (params?.keyword) search.set("keyword", params.keyword);
    if (params?.market) search.set("market", params.market);
    if (resolvedSource) search.set("source", resolvedSource);
    if (resolvedScope) search.set("scope", resolvedScope);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<StockPriceSummaryResponse>(`/stock-prices/summary${query ? `?${query}` : ""}`);
  },
  listDaily: (stockId: number, params?: { start_date?: string; end_date?: string; source?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    const resolvedSource = params?.source ?? "kiwoom_rest";
    if (params?.start_date) search.set("start_date", params.start_date);
    if (params?.end_date) search.set("end_date", params.end_date);
    if (resolvedSource) search.set("source", resolvedSource);
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiRequest<StockDailyPriceListResponse>(`/stock-prices/${stockId}/daily${query ? `?${query}` : ""}`);
  },
  getSummary: (stockId: number, params?: { source?: string }) => {
    const search = new URLSearchParams();
    const resolvedSource = params?.source ?? "kiwoom_rest";
    if (resolvedSource) search.set("source", resolvedSource);
    const query = search.toString();
    return apiRequest<StockPriceFactSummaryResponse>(`/stock-prices/${stockId}/summary${query ? `?${query}` : ""}`);
  },
  getMarketMetricsSummary: (stockId: number, params?: { source?: string }) => {
    const search = new URLSearchParams();
    if (params?.source) search.set("source", params.source);
    const query = search.toString();
    return apiRequest<MarketMetricsSummaryResponse>(`/market-metrics/${stockId}/summary${query ? `?${query}` : ""}`);
  },
  getMarketIndicatorsOverview: (params?: { source?: string }) => {
    const search = new URLSearchParams();
    const resolvedSource = params?.source ?? "kiwoom_rest";
    if (resolvedSource) search.set("source", resolvedSource);
    const query = search.toString();
    return apiRequest<MarketIndicatorsOverviewResponse>(`/market-metrics/overview${query ? `?${query}` : ""}`);
  },
  getAdvisoryEvidencePackage: (
    stockId: number,
    params?: {
      price_source?: string;
      market_metrics_source?: string;
      include_candle_reference?: boolean;
      lookback_days?: number;
      recent_candle_limit?: number;
      include_raw_candles?: boolean;
      include_similar_patterns?: boolean;
      pattern_window?: number;
      similar_case_limit?: number;
      pattern_ma?: number;
      search_trading_days?: number;
      strategy_horizon?: string;
      include_scenario_questions?: boolean;
      include_news_disclosures_risk?: boolean;
      include_technical_indicators?: boolean;
    },
  ) => {
    const search = new URLSearchParams();
    if (params?.price_source) search.set("price_source", params.price_source);
    if (params?.market_metrics_source) search.set("market_metrics_source", params.market_metrics_source);
    if (params?.include_candle_reference !== undefined) {
      search.set("include_candle_reference", String(params.include_candle_reference));
    }
    if (params?.lookback_days !== undefined) search.set("lookback_days", String(params.lookback_days));
    if (params?.recent_candle_limit !== undefined) search.set("recent_candle_limit", String(params.recent_candle_limit));
    if (params?.include_raw_candles !== undefined) search.set("include_raw_candles", String(params.include_raw_candles));
    if (params?.include_similar_patterns !== undefined) search.set("include_similar_patterns", String(params.include_similar_patterns));
    if (params?.pattern_window !== undefined) search.set("pattern_window", String(params.pattern_window));
    if (params?.similar_case_limit !== undefined) search.set("similar_case_limit", String(params.similar_case_limit));
    if (params?.pattern_ma !== undefined) search.set("pattern_ma", String(params.pattern_ma));
    if (params?.search_trading_days !== undefined) search.set("search_trading_days", String(params.search_trading_days));
    if (params?.strategy_horizon) search.set("strategy_horizon", params.strategy_horizon);
    if (params?.include_scenario_questions !== undefined) {
      search.set("include_scenario_questions", String(params.include_scenario_questions));
    }
    if (params?.include_news_disclosures_risk !== undefined) {
      search.set("include_news_disclosures_risk", String(params.include_news_disclosures_risk));
    }
    if (params?.include_technical_indicators !== undefined) {
      search.set("include_technical_indicators", String(params.include_technical_indicators));
    }
    const query = search.toString();
    return apiRequest<AdvisoryEvidencePackageResponse>(
      `/advisory/evidence-package/${stockId}${query ? `?${query}` : ""}`,
    );
  },
};
