import type {
  AdvisoryEvidencePackageResponse,
  MarketMetricsSummaryResponse,
  SelectedStockPriceCollectRequest,
  StockDailyPriceListResponse,
  StockPriceCollectResult,
  StockPriceFactSummaryResponse,
  StockPriceSummaryResponse,
} from "@/types/stockPrice";

export const stockPriceMockRepository = {
  async collectSelected(payload: SelectedStockPriceCollectRequest): Promise<StockPriceCollectResult> {
    const perStock = payload.period_years * 250;
    const saved = payload.stock_ids.length * perStock;
    return {
      requested_count: payload.stock_ids.length,
      success_count: payload.stock_ids.length,
      failed_count: 0,
      skipped_count: 0,
      saved_count: saved,
      message: "mock candle collect complete",
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

  async listSummary(): Promise<StockPriceSummaryResponse> {
    return { items: [], limit: 20, offset: 0 };
  },

  async listDaily(stockId: number): Promise<StockDailyPriceListResponse> {
    return {
      stock_id: stockId,
      stock_code: `MOCK-${stockId}`,
      stock_name: `Mock Stock ${stockId}`,
      items: [],
      limit: 20,
      offset: 0,
    };
  },

  async getSummary(stockId: number): Promise<StockPriceFactSummaryResponse> {
    return {
      stock_id: stockId,
      stock_code: `MOCK-${stockId}`,
      stock_name: `Mock Stock ${stockId}`,
      source: "mock",
      price_count: 0,
      min_trade_date: null,
      max_trade_date: null,
      latest_trade_date: null,
      latest_close_price: null,
      latest_ma5: null,
      latest_ma20: null,
      latest_ma60: null,
      recent_5d_change_rate: null,
      avg_volume_20d: null,
      high_52w: null,
      high_52w_date: null,
      price_position_vs_52w_high: null,
    };
  },

  async getMarketMetricsSummary(stockId: number): Promise<MarketMetricsSummaryResponse> {
    return {
      stock_id: stockId,
      stock_code: `MOCK-${stockId}`,
      stock_name: `Mock Stock ${stockId}`,
      source: "marcap",
      latest_market_metrics_date: "2026-02-20",
      latest_price_trade_date: "2026-05-12",
      is_stale: true,
      stale_days: 81,
      staleness_level: "severely_stale",
      market: "KOSPI",
      trading_value: 1234567890,
      market_cap: 98765432100,
      listed_shares: 12345678,
      trading_volume: 345678,
      market_cap_rank: 1200,
      trading_value_rank: 450,
      market_trading_value_rank: 210,
      trading_value_percentile: 78.45,
      market_trading_value_percentile: 82.13,
      data_note: "Market metrics are based on 2026-02-20 and are older than the latest price data date 2026-05-12.",
    };
  },

  async getAdvisoryEvidencePackage(stockId: number): Promise<AdvisoryEvidencePackageResponse> {
    return {
      stock: {
        stock_id: stockId,
        stock_code: `MOCK-${stockId}`,
        stock_name: `Mock Stock ${stockId}`,
      },
      price_summary: {
        latest_trade_date: "2026-05-12",
        latest_close_price: 12345,
        latest_ma5: 12200,
        latest_ma20: 11800,
        latest_ma60: 11200,
        recent_5d_change_rate: 3.21,
        avg_volume_20d: 456789,
        high_52w: 15000,
        high_52w_date: "2026-01-15",
        price_position_vs_52w_high: 82.3,
        price_count: 485,
        source: "pykrx",
      },
      market_metrics_summary: {
        latest_market_metrics_date: "2026-02-20",
        latest_price_trade_date: "2026-05-12",
        is_stale: true,
        stale_days: 81,
        staleness_level: "severely_stale",
        market: "KOSPI",
        trading_value: 1234567890,
        market_cap: 98765432100,
        listed_shares: 12345678,
        trading_volume: 345678,
        trading_value_rank: 450,
        market_trading_value_rank: 210,
        trading_value_percentile: 78.45,
        market_trading_value_percentile: 82.13,
        source: "marcap",
        data_note: "시장지표는 2026-02-20 기준이며 최신 가격 데이터 기준일 2026-05-12보다 오래되었습니다.",
      },
      price_candle_reference: {
        included: true,
        lookback_days: 252,
        recent_candle_limit: 60,
        include_raw_candles: false,
        pattern_window: 20,
        similar_case_limit: 5,
        row_count: 252,
        start_trade_date: "2025-05-13",
        end_trade_date: "2026-05-12",
        timeframe_summaries: [
          { label: "5d", start_trade_date: "2026-05-07", end_trade_date: "2026-05-12", change_rate: -1.12, highest_price: 12600, lowest_price: 11980 },
          { label: "20d", start_trade_date: "2026-04-15", end_trade_date: "2026-05-12", change_rate: 4.23, highest_price: 13100, lowest_price: 11120 },
        ],
        recent_candles: [],
        similar_pattern_cases: [
          {
            case_id: "pattern_case_1",
            reference_end_trade_date: "2026-05-12",
            comparison_start_trade_date: "2025-09-02",
            comparison_end_trade_date: "2025-09-29",
            similarity_score: 92.44,
            historical_next_5d_change_rate: 3.21,
            historical_next_20d_change_rate: 5.77,
            note: "과거 유사 패턴은 참고 사례일 뿐이며 향후 주가 움직임을 보장하지 않습니다.",
          },
        ],
        caution_note: "과거 유사 패턴은 참고 사례일 뿐입니다. 유사 패턴 이후 실제 수익률은 예측값이 아니며 자동 매수·매도 신호로 해석하면 안 됩니다.",
      },
      strategy_horizon_context: {
        selected_horizon: "both",
        horizon_notes: [
          "단기 가격 흐름과 장기 구조 요인을 함께 검토합니다.",
          "스윙 관점과 장기 관점에서 각각 다른 확인 포인트를 구분합니다.",
        ],
      },
      analysis_horizon_weights: {
        swing_weight: 0.5,
        long_term_weight: 0.5,
      },
      scenario_questions_for_gpt: [
        "최근 가격 요약과 캔들 참조 데이터를 바탕으로 현재 주가 위치를 설명해 주세요.",
        "자동 매수·매도 판단 없이, 사용자가 직접 판단할 수 있도록 근거 중심으로 정리해 주세요.",
        "과거 유사 패턴이 제공된 경우, 이를 예측이 아니라 참고 사례로만 해석해 주세요.",
      ],
      news_summary: null,
      disclosure_summary: null,
      risk_summary: null,
      theme_summary: null,
      telegram_theme_summary: null,
      data_quality_notes: [
        "시장지표 데이터가 최신 가격 데이터보다 오래되었습니다. 현재 수급 판단에는 최신성 차이를 반드시 고려해야 합니다.",
        "시장지표는 2026-02-20 기준이며 최신 가격 데이터 기준일 2026-05-12보다 오래되었습니다.",
        "과거 유사 패턴은 참고 사례일 뿐이며 향후 주가 움직임을 보장하지 않습니다.",
        "유사 패턴 이후 실제 수익률은 예측값이 아니라 시나리오 검토용 참고 정보입니다.",
      ],
      instruction_guardrails: [
        "이 패키지는 GPT 자문을 위한 사실형 근거 자료로만 사용해야 합니다.",
        "이 패키지만으로 자동 매수, 매도, 목표가 결론을 생성하지 마십시오.",
        "시장지표가 오래되었거나 누락된 경우, 해석 전에 그 한계를 먼저 명시하십시오.",
        "과거 유사 패턴은 예측이 아니라 참고 사례로만 다루십시오.",
      ],
      generated_at: "2026-05-13 10:52:27",
    };
  },
};
