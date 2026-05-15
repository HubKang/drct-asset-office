import { FormEvent, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { ApiError } from "@/services/api/apiClient";
import { repositories } from "@/services";
import type {
  AdvisoryEvidencePackageResponse,
  EvidencePriceCandleReferenceBlock,
  EvidenceSimilarPatternCase,
  MarketMetricsSummaryResponse,
  StockDailyPrice,
  StockPriceFactSummaryResponse,
  StockPriceSummaryItem,
} from "@/types/stockPrice";

type MarketFilter = "ALL" | "KOSPI" | "KOSDAQ";
type StrategyHorizon = "swing" | "long_term" | "both";

const SUMMARY_LIMIT = 20;
const DAILY_LIMIT = 20;

function fmtNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return Intl.NumberFormat("ko-KR").format(value);
}

function fmtPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function fmtWon(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Intl.NumberFormat("ko-KR").format(value)}원`;
}

function fmtShares(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Intl.NumberFormat("ko-KR").format(value)}주`;
}

function fmtPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${value.toFixed(2)}%`;
}

function fmtRank(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${Intl.NumberFormat("ko-KR").format(value)}위`;
}

function fmtSource(value: string | null | undefined): string {
  if (!value) return "-";
  return value.toUpperCase();
}

function fmtRange(startDate: string | null | undefined, endDate: string | null | undefined): string {
  if (!startDate || !endDate) return "-";
  return `${startDate} ~ ${endDate}`;
}

function fmtEvidenceBlocks(pkg: AdvisoryEvidencePackageResponse | null): string {
  if (!pkg) return "-";
  const blocks = ["가격 요약"];
  if (pkg.market_metrics_summary) blocks.push("시장지표 요약");
  if (pkg.price_candle_reference) blocks.push("캔들 참조");
  if (pkg.price_candle_reference?.similar_pattern_cases?.length) blocks.push("유사 패턴 사례");
  if (pkg.strategy_horizon_context) blocks.push("투자 관점 컨텍스트");
  if (pkg.scenario_questions_for_gpt?.length) blocks.push("시나리오 질문");
  return blocks.join(", ");
}

function staleLabel(level: string | null | undefined): string {
  switch (level) {
    case "fresh":
      return "최신";
    case "acceptable":
      return "허용 가능";
    case "stale":
      return "주의";
    case "severely_stale":
      return "오래됨";
    default:
      return level || "-";
  }
}

function strategyHorizonLabel(value: string | null | undefined): string {
  switch (value) {
    case "swing":
      return "스윙";
    case "long_term":
      return "장기";
    case "both":
      return "스윙 + 장기";
    default:
      return value || "-";
  }
}

function staleBadgeClass(level: string | null | undefined): string {
  switch (level) {
    case "fresh":
      return "badge badge-emerald";
    case "acceptable":
      return "badge badge-blue";
    case "stale":
      return "badge badge-amber";
    case "severely_stale":
      return "badge badge-rose";
    default:
      return "badge badge-slate";
  }
}

function staleMessage(level: string | null | undefined): string | null {
  switch (level) {
    case "acceptable":
      return "시장지표 기준일이 가격 기준일과 약간 차이납니다.";
    case "stale":
      return "시장지표 기준일이 가격 기준일보다 오래되었습니다.";
    case "severely_stale":
      return "시장지표 기준일이 가격 기준일보다 오래되어 현재 수급 판단에는 주의가 필요합니다.";
    default:
      return null;
  }
}

function staleMessageClass(level: string | null | undefined): string {
  switch (level) {
    case "acceptable":
      return "inline-result";
    case "stale":
      return "inline-result inline-warning";
    case "severely_stale":
      return "inline-result inline-error";
    default:
      return "inline-result";
  }
}

function bestSimilarity(cases: EvidenceSimilarPatternCase[] | undefined): string {
  if (!cases || cases.length === 0) return "-";
  return `${cases[0].similarity_score.toFixed(2)}%`;
}

function candleReferenceSummary(reference: EvidencePriceCandleReferenceBlock | null): Array<{ label: string; value: string }> {
  if (!reference) return [];
  return [
    { label: "참조 기간", value: fmtRange(reference.start_trade_date, reference.end_trade_date) },
    { label: "캔들 행 수", value: fmtNumber(reference.row_count) },
    { label: "구간 요약 개수", value: fmtNumber(reference.timeframe_summaries.length) },
    { label: "최근 캔들 개수", value: fmtNumber(reference.recent_candles.length) },
    { label: "유사 사례 개수", value: fmtNumber(reference.similar_pattern_cases.length) },
    { label: "최고 유사도", value: bestSimilarity(reference.similar_pattern_cases) },
    { label: "패턴 기준 기간", value: `${fmtNumber(reference.pattern_window)}일` },
  ];
}

function StockPricesPage() {
  const [keyword, setKeyword] = useState("");
  const [market, setMarket] = useState<MarketFilter>("ALL");
  const [offset, setOffset] = useState(0);

  const [summaryItems, setSummaryItems] = useState<StockPriceSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedStock, setSelectedStock] = useState<StockPriceSummaryItem | null>(null);
  const [selectedSummary, setSelectedSummary] = useState<StockPriceFactSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  const [marketMetricsSummary, setMarketMetricsSummary] = useState<MarketMetricsSummaryResponse | null>(null);
  const [marketMetricsLoading, setMarketMetricsLoading] = useState(false);
  const [marketMetricsError, setMarketMetricsError] = useState("");

  const [includeCandleReference, setIncludeCandleReference] = useState(false);
  const [includeRawCandles, setIncludeRawCandles] = useState(false);
  const [includeSimilarPatterns, setIncludeSimilarPatterns] = useState(false);
  const [lookbackDays, setLookbackDays] = useState(252);
  const [recentCandleLimit, setRecentCandleLimit] = useState(60);
  const [patternWindow, setPatternWindow] = useState(20);
  const [similarCaseLimit, setSimilarCaseLimit] = useState(5);
  const [strategyHorizon, setStrategyHorizon] = useState<StrategyHorizon>("both");
  const [includeScenarioQuestions, setIncludeScenarioQuestions] = useState(true);

  const [advisoryPackage, setAdvisoryPackage] = useState<AdvisoryEvidencePackageResponse | null>(null);
  const [evidencePackageLoading, setEvidencePackageLoading] = useState(false);
  const [evidencePackageError, setEvidencePackageError] = useState("");
  const [showEvidenceJson, setShowEvidenceJson] = useState(false);
  const [copyStatusMessage, setCopyStatusMessage] = useState("");
  const [showScenarioQuestions, setShowScenarioQuestions] = useState(false);

  const [dailyRows, setDailyRows] = useState<StockDailyPrice[]>([]);
  const [dailyOffset, setDailyOffset] = useState(0);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState("");

  const effectiveIncludeRawCandles = includeCandleReference && includeRawCandles;
  const effectiveIncludeSimilarPatterns = includeCandleReference && includeSimilarPatterns;

  const loadListSummary = async (
    nextOffset = offset,
    nextFilters?: {
      keyword?: string;
      market?: MarketFilter;
    },
  ) => {
    setLoading(true);
    setError("");
    try {
      const activeKeyword = nextFilters?.keyword ?? keyword;
      const activeMarket = nextFilters?.market ?? market;
      const response = await repositories.stockPrices.listSummary({
        keyword: activeKeyword.trim() || undefined,
        market: activeMarket === "ALL" ? undefined : activeMarket,
        source: "pykrx",
        limit: SUMMARY_LIMIT,
        offset: nextOffset,
      });
      setSummaryItems(response.items);
      setSelectedStock((prev) => {
        if (response.items.length === 0) return null;
        if (!prev) return response.items[0];
        return response.items.find((item) => item.stock_id === prev.stock_id) ?? response.items[0];
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "가격 데이터 목록을 불러오지 못했습니다.");
      setSummaryItems([]);
      setSelectedStock(null);
    } finally {
      setLoading(false);
    }
  };

  const loadStockSummary = async (stockId: number) => {
    setSummaryLoading(true);
    setSummaryError("");
    setSelectedSummary(null);
    try {
      const response = await repositories.stockPrices.getSummary(stockId, { source: "pykrx" });
      setSelectedSummary(response);
    } catch (nextError) {
      if (nextError instanceof ApiError && nextError.status === 404) {
        setSummaryError("가격 요약 데이터가 없습니다.");
      } else {
        setSummaryError(nextError instanceof Error ? nextError.message : "가격 요약 데이터를 불러오지 못했습니다.");
      }
    } finally {
      setSummaryLoading(false);
    }
  };

  const loadMarketMetricsSummary = async (stockId: number) => {
    setMarketMetricsLoading(true);
    setMarketMetricsError("");
    setMarketMetricsSummary(null);
    try {
      const response = await repositories.stockPrices.getMarketMetricsSummary(stockId, { source: "marcap" });
      setMarketMetricsSummary(response);
    } catch (nextError) {
      if (nextError instanceof ApiError && nextError.status === 404) {
        setMarketMetricsError("시장지표 데이터가 없습니다.");
      } else {
        setMarketMetricsError(nextError instanceof Error ? nextError.message : "시장지표 데이터를 불러오지 못했습니다.");
      }
    } finally {
      setMarketMetricsLoading(false);
    }
  };

  const loadAdvisoryEvidencePackage = async (stockId: number) => {
    setEvidencePackageLoading(true);
    setEvidencePackageError("");
    setCopyStatusMessage("");
    try {
      const response = await repositories.stockPrices.getAdvisoryEvidencePackage(stockId, {
        price_source: "pykrx",
        market_metrics_source: "marcap",
        include_candle_reference: includeCandleReference,
        lookback_days: lookbackDays,
        recent_candle_limit: recentCandleLimit,
        include_raw_candles: effectiveIncludeRawCandles,
        pattern_window: patternWindow,
        similar_case_limit: effectiveIncludeSimilarPatterns ? similarCaseLimit : 0,
        strategy_horizon: strategyHorizon,
        include_scenario_questions: includeScenarioQuestions,
      });
      setAdvisoryPackage(response);
    } catch (nextError) {
      setAdvisoryPackage(null);
      if (nextError instanceof ApiError && nextError.status === 404) {
        setEvidencePackageError("GPT 자문 근거 패키지 데이터가 없습니다.");
      } else {
        setEvidencePackageError(nextError instanceof Error ? nextError.message : "GPT 자문 근거 패키지를 불러오지 못했습니다.");
      }
    } finally {
      setEvidencePackageLoading(false);
    }
  };

  const copyAdvisoryEvidencePackage = async () => {
    if (!advisoryPackage) return;
    const payload = JSON.stringify(advisoryPackage, null, 2);
    setCopyStatusMessage("");

    const fallbackCopy = () => {
      const textarea = document.createElement("textarea");
      textarea.value = payload;
      textarea.setAttribute("readonly", "true");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const copied = document.execCommand("copy");
      document.body.removeChild(textarea);
      if (!copied) {
        throw new Error("복사에 실패했습니다. JSON을 직접 선택해 복사해 주세요.");
      }
    };

    try {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(payload);
        } catch {
          fallbackCopy();
        }
      } else {
        fallbackCopy();
      }
      setCopyStatusMessage("GPT 근거 패키지를 복사했습니다.");
    } catch {
      setCopyStatusMessage("복사에 실패했습니다. JSON을 직접 선택해 복사해 주세요.");
    }
  };

  const loadDaily = async (stockId: number, nextOffset = dailyOffset) => {
    setDailyLoading(true);
    setDailyError("");
    try {
      const response = await repositories.stockPrices.listDaily(stockId, {
        source: "pykrx",
        limit: DAILY_LIMIT,
        offset: nextOffset,
      });
      setDailyRows(response.items);
    } catch (nextError) {
      setDailyError(nextError instanceof Error ? nextError.message : "일봉 데이터를 불러오지 못했습니다.");
      setDailyRows([]);
    } finally {
      setDailyLoading(false);
    }
  };

  useEffect(() => {
    void loadListSummary(0);
    setOffset(0);
  }, []);

  useEffect(() => {
    if (!selectedStock) {
      setSelectedSummary(null);
      setSummaryError("");
      setMarketMetricsSummary(null);
      setMarketMetricsError("");
      setAdvisoryPackage(null);
      setEvidencePackageError("");
      setShowEvidenceJson(false);
      setCopyStatusMessage("");
      setShowScenarioQuestions(false);
      setDailyRows([]);
      setDailyError("");
      return;
    }

    setDailyOffset(0);
    setDailyRows([]);
    setAdvisoryPackage(null);
    setEvidencePackageError("");
    setShowEvidenceJson(false);
    setCopyStatusMessage("");
    setShowScenarioQuestions(false);
    void loadStockSummary(selectedStock.stock_id);
    void loadMarketMetricsSummary(selectedStock.stock_id);
    void loadDaily(selectedStock.stock_id, 0);
  }, [selectedStock?.stock_id]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    setOffset(0);
    await loadListSummary(0);
  };

  const onReset = async () => {
    setKeyword("");
    setMarket("ALL");
    setOffset(0);
    await loadListSummary(0, { keyword: "", market: "ALL" });
  };

  const onToggleCandleReference = (checked: boolean) => {
    setIncludeCandleReference(checked);
    if (!checked) {
      setIncludeRawCandles(false);
      setIncludeSimilarPatterns(false);
    }
  };

  const onToggleSimilarPatterns = (checked: boolean) => {
    setIncludeSimilarPatterns(checked);
    if (checked) {
      setIncludeCandleReference(true);
    }
  };

  const canPrev = offset > 0;
  const canNext = summaryItems.length >= SUMMARY_LIMIT;
  const canDailyPrev = dailyOffset > 0;
  const canDailyNext = dailyRows.length >= DAILY_LIMIT;
  const metricsNotice = staleMessage(marketMetricsSummary?.staleness_level);
  const evidenceNotice = staleMessage(advisoryPackage?.market_metrics_summary?.staleness_level);
  const candleSummary = useMemo(() => candleReferenceSummary(advisoryPackage?.price_candle_reference ?? null), [advisoryPackage]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="가격·캔들 관리"
        description="운영 화면에서는 PyKRX 가격 데이터와 marcap 기반 시장지표를 함께 확인합니다."
      />

      <SectionCard title="검색">
        <form className="price-search-row" onSubmit={onSearch}>
          <select className="select-control" value={market} onChange={(e) => setMarket(e.target.value as MarketFilter)}>
            <option value="ALL">전체</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
          </select>
          <input
            className="input-control"
            placeholder="종목코드 또는 종목명"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            검색
          </button>
          <button type="button" className="btn btn-secondary" onClick={onReset}>
            초기화
          </button>
        </form>
      </SectionCard>

      <div className="price-page-content">
        <SectionCard title="캔들 보유 종목" className="price-stock-list-card">
          <p className="price-section-note">
            운영 화면 기준 가격 source는 `pykrx`이며, 좌측 목록에서는 수집 건수와 수집 기간을 빠르게 확인할 수 있습니다.
          </p>
          {loading ? <p className="text-sm text-muted">로딩 중입니다.</p> : null}
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          {!loading && !error && summaryItems.length === 0 ? <EmptyState message="조회된 캔들 데이터가 없습니다." /> : null}
          {!loading && !error && summaryItems.length > 0 ? (
            <>
              <div className="table-shell">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>선택</th>
                      <th>종목명</th>
                      <th>수집시작일</th>
                      <th>수집종료일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summaryItems.map((item) => {
                      const selected = selectedStock?.stock_id === item.stock_id;
                      return (
                        <tr
                          key={item.stock_id}
                          className={selected ? "selected-row row-clickable" : "row-clickable"}
                          onClick={() => setSelectedStock(item)}
                        >
                          <td>{selected ? "선택" : "-"}</td>
                          <td>
                            <div className="stock-cell">
                              <strong>{item.stock_name}</strong>
                              <span>{item.stock_code}</span>
                              <span>{`건수 ${fmtNumber(item.price_count)} · 원천 ${fmtSource(item.source)}`}</span>
                            </div>
                          </td>
                          <td>{item.min_trade_date || "-"}</td>
                          <td>{item.max_trade_date || "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="pagination-bar">
                <div className="pagination-info">이번 페이지 {summaryItems.length}건</div>
                <div className="pagination-actions">
                  <button
                    className="btn btn-secondary"
                    disabled={!canPrev}
                    onClick={() => {
                      const next = Math.max(0, offset - SUMMARY_LIMIT);
                      setOffset(next);
                      void loadListSummary(next);
                    }}
                  >
                    이전
                  </button>
                  <button
                    className="btn btn-secondary"
                    disabled={!canNext}
                    onClick={() => {
                      const next = offset + SUMMARY_LIMIT;
                      setOffset(next);
                      void loadListSummary(next);
                    }}
                  >
                    다음
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>

        <SectionCard title={selectedStock ? `${selectedStock.stock_name} 상세` : "상세 정보"} className="price-daily-table-card">
          {!selectedStock ? <EmptyState message="종목을 선택하면 가격 요약, 시장지표 요약, GPT 패키지 옵션, 일봉 데이터를 함께 확인할 수 있습니다." /> : null}

          {selectedStock ? (
            <>
              <p className="price-section-note">
                가격 요약은 `GET /stock-prices/{'{stock_id}'}/summary`, 시장지표 요약은 `GET /market-metrics/{'{stock_id}'}/summary`,
                GPT 패키지는 `GET /advisory/evidence-package/{'{stock_id}'}` 응답을 기준으로 표시됩니다.
              </p>

              <div className="price-detail-stack">
                <section className="price-detail-section">
                  <div className="price-detail-header">
                    <h3>가격 요약</h3>
                    <span className="badge badge-blue">PYKRX</span>
                  </div>
                  {summaryLoading ? <p className="text-sm text-muted">가격 요약을 불러오는 중입니다.</p> : null}
                  {!summaryLoading && summaryError ? <p className="text-sm text-rose-600">{summaryError}</p> : null}
                  {!summaryLoading && !summaryError && selectedSummary ? (
                    <div className="price-meta-grid">
                      <div className="price-meta-card"><p className="price-meta-label">최근 종가</p><strong>{fmtPrice(selectedSummary.latest_close_price)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">최근 5거래일 등락률</p><strong>{fmtPercent(selectedSummary.recent_5d_change_rate)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">최근 20거래일 평균 거래량</p><strong>{fmtNumber(selectedSummary.avg_volume_20d)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">52주 고점 대비 위치</p><strong>{fmtPercent(selectedSummary.price_position_vs_52w_high)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">최근 거래일</p><strong>{selectedSummary.latest_trade_date || "-"}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">52주 고점</p><strong>{fmtPrice(selectedSummary.high_52w)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">52주 고점일</p><strong>{selectedSummary.high_52w_date || "-"}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">5일 이동평균</p><strong>{fmtPrice(selectedSummary.latest_ma5)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">20일 이동평균</p><strong>{fmtPrice(selectedSummary.latest_ma20)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">60일 이동평균</p><strong>{fmtPrice(selectedSummary.latest_ma60)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">가격 데이터 건수</p><strong>{fmtNumber(selectedSummary.price_count)}건</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">수집 기간</p><strong>{fmtRange(selectedSummary.min_trade_date, selectedSummary.max_trade_date)}</strong></div>
                      <div className="price-meta-card"><p className="price-meta-label">데이터 원천</p><strong>{fmtSource(selectedSummary.source)}</strong></div>
                    </div>
                  ) : null}
                </section>

                <section className="price-detail-section">
                  <div className="price-detail-header">
                    <h3>시장지표 요약</h3>
                    <span className="badge badge-slate">MARCAP</span>
                  </div>
                  {marketMetricsLoading ? <p className="text-sm text-muted">시장지표 요약을 불러오는 중입니다.</p> : null}
                  {!marketMetricsLoading && marketMetricsError ? <p className="text-sm text-rose-600">{marketMetricsError}</p> : null}
                  {!marketMetricsLoading && !marketMetricsError && marketMetricsSummary ? (
                    <>
                      <div className="price-meta-grid">
                        <div className="price-meta-card"><p className="price-meta-label">거래대금</p><strong>{fmtWon(marketMetricsSummary.trading_value)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">전체 거래대금 순위</p><strong>{fmtRank(marketMetricsSummary.trading_value_rank)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시가총액</p><strong>{fmtWon(marketMetricsSummary.market_cap)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">최신성 상태</p><strong className="price-status-inline"><span className={staleBadgeClass(marketMetricsSummary.staleness_level)}>{staleLabel(marketMetricsSummary.staleness_level)}</span></strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장지표 기준일</p><strong>{marketMetricsSummary.latest_market_metrics_date}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">가격 기준일</p><strong>{marketMetricsSummary.latest_price_trade_date || "-"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">기준일 차이</p><strong>{marketMetricsSummary.stale_days === null ? "-" : `${fmtNumber(marketMetricsSummary.stale_days)}일`}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">상장주식수</p><strong>{fmtShares(marketMetricsSummary.listed_shares)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">거래량</p><strong>{fmtShares(marketMetricsSummary.trading_volume)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장 내 거래대금 순위</p><strong>{fmtRank(marketMetricsSummary.market_trading_value_rank)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">전체 거래대금 백분위</p><strong>{fmtPercent(marketMetricsSummary.trading_value_percentile)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장 내 거래대금 백분위</p><strong>{fmtPercent(marketMetricsSummary.market_trading_value_percentile)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장 구분</p><strong>{marketMetricsSummary.market || "-"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">데이터 원천</p><strong>{fmtSource(marketMetricsSummary.source)}</strong></div>
                      </div>
                      {metricsNotice ? <div className={staleMessageClass(marketMetricsSummary.staleness_level)}>{metricsNotice}</div> : null}
                      <p className="price-card-note">{marketMetricsSummary.data_note}</p>
                    </>
                  ) : null}
                  {!marketMetricsLoading && !marketMetricsError && !marketMetricsSummary ? <EmptyState message="시장지표 데이터가 없습니다." /> : null}
                </section>

                <section className="price-detail-section">
                  <div className="price-detail-header">
                    <h3>GPT 자문 패키지 옵션</h3>
                  </div>
                  <div className="evidence-options-grid">
                    <label className="evidence-option-check">
                      <input type="checkbox" checked={includeCandleReference} onChange={(e) => onToggleCandleReference(e.target.checked)} />
                      <span>최근 1년 캔들 참조 포함</span>
                    </label>
                    <label className="evidence-option-check">
                      <input
                        type="checkbox"
                        checked={includeRawCandles}
                        disabled={!includeCandleReference}
                        onChange={(e) => setIncludeRawCandles(e.target.checked)}
                      />
                      <span>전체 252개 원시 캔들 포함</span>
                    </label>
                    <label className="evidence-option-check">
                      <input
                        type="checkbox"
                        checked={includeSimilarPatterns}
                        disabled={!includeCandleReference}
                        onChange={(e) => onToggleSimilarPatterns(e.target.checked)}
                      />
                      <span>유사 패턴 분석 포함</span>
                    </label>
                    <label className="evidence-option-check">
                      <input
                        type="checkbox"
                        checked={includeScenarioQuestions}
                        onChange={(e) => setIncludeScenarioQuestions(e.target.checked)}
                      />
                      <span>시나리오 질문 포함</span>
                    </label>
                    <label className="evidence-option-field">
                      <span>투자 관점</span>
                      <select className="select-control" value={strategyHorizon} onChange={(e) => setStrategyHorizon(e.target.value as StrategyHorizon)}>
                        <option value="swing">스윙</option>
                        <option value="long_term">장기</option>
                        <option value="both">둘 다</option>
                      </select>
                    </label>
                    <label className="evidence-option-field">
                      <span>패턴 기준 기간</span>
                      <input className="input-control" type="number" min={5} max={120} value={patternWindow} onChange={(e) => setPatternWindow(Number(e.target.value) || 20)} />
                    </label>
                    <label className="evidence-option-field">
                      <span>유사 사례 개수</span>
                      <input className="input-control" type="number" min={1} max={10} value={similarCaseLimit} onChange={(e) => setSimilarCaseLimit(Number(e.target.value) || 5)} />
                    </label>
                    <label className="evidence-option-field">
                      <span>최근 원시 캔들 개수</span>
                      <input className="input-control" type="number" min={5} max={252} value={recentCandleLimit} onChange={(e) => setRecentCandleLimit(Number(e.target.value) || 60)} />
                    </label>
                  </div>
                  <p className="price-card-note">투자 관점 기본값은 둘 다이며, 시장지표 기본 원천은 marcap입니다.</p>
                  {effectiveIncludeRawCandles ? (
                    <div className="inline-result inline-warning">
                      전체 252개 원시 캔들을 포함하면 GPT에 붙여넣는 JSON 크기가 커질 수 있습니다.
                    </div>
                  ) : null}
                </section>

                <section className="price-detail-section">
                  <div className="price-detail-header">
                    <h3>GPT 자문 근거 패키지</h3>
                    <div className="price-detail-actions">
                      <button type="button" className="btn btn-secondary" disabled={evidencePackageLoading} onClick={() => void loadAdvisoryEvidencePackage(selectedStock.stock_id)}>
                        {evidencePackageLoading ? "불러오는 중..." : "GPT 근거 패키지 불러오기"}
                      </button>
                    </div>
                  </div>

                  {!evidencePackageLoading && !evidencePackageError && !advisoryPackage ? <EmptyState message="필요한 시점에 GPT 자문 근거 패키지를 불러와 보세요." /> : null}
                  {evidencePackageLoading ? <p className="text-sm text-muted">GPT 근거 패키지를 불러오는 중입니다.</p> : null}
                  {!evidencePackageLoading && evidencePackageError ? <p className="text-sm text-rose-600">{evidencePackageError}</p> : null}

                  {!evidencePackageLoading && !evidencePackageError && advisoryPackage ? (
                    <>
                      <div className="price-meta-grid">
                        <div className="price-meta-card"><p className="price-meta-label">종목명 / 종목코드</p><strong>{`${advisoryPackage.stock.stock_name} / ${advisoryPackage.stock.stock_code}`}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">패키지 생성 시각</p><strong>{advisoryPackage.generated_at}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">가격 기준일</p><strong>{advisoryPackage.price_summary.latest_trade_date || "-"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장지표 기준일</p><strong>{advisoryPackage.market_metrics_summary?.latest_market_metrics_date || "-"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">시장지표 최신성 상태</p><strong className="price-status-inline"><span className={staleBadgeClass(advisoryPackage.market_metrics_summary?.staleness_level)}>{staleLabel(advisoryPackage.market_metrics_summary?.staleness_level)}</span></strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">캔들 참조 포함</p><strong>{advisoryPackage.price_candle_reference ? "예" : "아니오"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">유사 패턴 포함</p><strong>{advisoryPackage.price_candle_reference?.similar_pattern_cases?.length ? "예" : "아니오"}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">투자 관점</p><strong>{strategyHorizonLabel(advisoryPackage.strategy_horizon_context?.selected_horizon || strategyHorizon)}</strong></div>
                        <div className="price-meta-card"><p className="price-meta-label">포함 블록</p><strong>{fmtEvidenceBlocks(advisoryPackage)}</strong></div>
                      </div>

                      {evidenceNotice ? <div className={staleMessageClass(advisoryPackage.market_metrics_summary?.staleness_level)}>{evidenceNotice}</div> : null}

                      {advisoryPackage.price_candle_reference ? (
                        <div className="evidence-note-block">
                          <p className="evidence-note-title">캔들 참조 요약</p>
                          <div className="price-meta-grid">
                            {candleSummary.map((item) => (
                              <div className="price-meta-card" key={item.label}>
                                <p className="price-meta-label">{item.label}</p>
                                <strong>{item.value}</strong>
                              </div>
                            ))}
                          </div>
                          {advisoryPackage.price_candle_reference.caution_note ? (
                            <p className="price-card-note">{advisoryPackage.price_candle_reference.caution_note}</p>
                          ) : null}
                        </div>
                      ) : null}

                      {advisoryPackage.data_quality_notes.length > 0 ? (
                        <div className="evidence-note-block evidence-note-warning">
                          <p className="evidence-note-title">데이터 품질 안내</p>
                          <ul className="evidence-note-list">
                            {advisoryPackage.data_quality_notes.map((note, idx) => <li key={`${note}-${idx}`}>{note}</li>)}
                          </ul>
                        </div>
                      ) : null}

                      {advisoryPackage.instruction_guardrails.length > 0 ? (
                        <div className="evidence-note-block">
                          <p className="evidence-note-title">GPT 사용 제한 원칙</p>
                          <ul className="evidence-note-list">
                            {advisoryPackage.instruction_guardrails.map((note, idx) => <li key={`${note}-${idx}`}>{note}</li>)}
                          </ul>
                        </div>
                      ) : null}

                      {advisoryPackage.strategy_horizon_context ? (
                        <div className="evidence-note-block">
                          <p className="evidence-note-title">투자 관점 컨텍스트</p>
                          <ul className="evidence-note-list">
                            {advisoryPackage.strategy_horizon_context.horizon_notes.map((note, idx) => <li key={`${note}-${idx}`}>{note}</li>)}
                          </ul>
                          {advisoryPackage.analysis_horizon_weights ? (
                            <p className="price-card-note">
                              관점 가중치: 스윙 {Math.round(advisoryPackage.analysis_horizon_weights.swing_weight * 100)}% / 장기 {Math.round(advisoryPackage.analysis_horizon_weights.long_term_weight * 100)}%
                            </p>
                          ) : null}
                        </div>
                      ) : null}

                      <div className="evidence-note-block">
                        <div className="price-detail-header">
                          <p className="evidence-note-title">GPT에 전달할 시나리오 질문</p>
                          <button type="button" className="btn btn-secondary" onClick={() => setShowScenarioQuestions((prev) => !prev)}>
                            {showScenarioQuestions ? "질문 숨기기" : "질문 보기"}
                          </button>
                        </div>
                        {showScenarioQuestions ? (
                          advisoryPackage.scenario_questions_for_gpt.length > 0 ? (
                            <ul className="evidence-note-list">
                              {advisoryPackage.scenario_questions_for_gpt.map((question, idx) => <li key={`${question}-${idx}`}>{question}</li>)}
                            </ul>
                          ) : (
                            <p className="price-card-note">현재 패키지에는 시나리오 질문이 포함되지 않았습니다.</p>
                          )
                        ) : null}
                      </div>

                      <div className="evidence-actions">
                        <button type="button" className="btn btn-secondary" onClick={() => setShowEvidenceJson((prev) => !prev)}>
                          {showEvidenceJson ? "JSON 숨기기" : "JSON 보기"}
                        </button>
                        <button type="button" className="btn btn-primary" onClick={copyAdvisoryEvidencePackage}>
                          GPT용 JSON 복사
                        </button>
                      </div>

                      {copyStatusMessage ? <p className="text-sm text-muted">{copyStatusMessage}</p> : null}
                      {showEvidenceJson ? <pre className="evidence-json-view">{JSON.stringify(advisoryPackage, null, 2)}</pre> : null}
                    </>
                  ) : null}
                </section>
              </div>

              {dailyLoading ? <p className="text-sm text-muted">일봉 상세를 불러오는 중입니다.</p> : null}
              {!dailyLoading && dailyError ? <p className="text-sm text-rose-600">{dailyError}</p> : null}
              {!dailyLoading && !dailyError && dailyRows.length === 0 ? <EmptyState message="조회된 일봉 데이터가 없습니다." /> : null}
              {!dailyLoading && !dailyError && dailyRows.length > 0 ? (
                <>
                  <div className="table-shell price-daily-table-shell">
                    <table className="data-table compact-table price-daily-table min-w-[920px]">
                      <thead>
                        <tr>
                          <th className="cell-nowrap">거래일</th>
                          <th className="numeric-cell">시가</th>
                          <th className="numeric-cell">고가</th>
                          <th className="numeric-cell">저가</th>
                          <th className="numeric-cell">종가</th>
                          <th className="numeric-cell">거래량</th>
                          <th className="numeric-cell">등락률</th>
                          <th className="numeric-cell">MA5</th>
                          <th className="numeric-cell">MA20</th>
                          <th className="numeric-cell">MA60</th>
                          <th className="numeric-cell">MA120</th>
                          <th className="numeric-cell">MA240</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dailyRows.map((row) => (
                          <tr key={row.id}>
                            <td className="cell-nowrap">{row.trade_date}</td>
                            <td className="numeric-cell">{fmtPrice(row.open_price)}</td>
                            <td className="numeric-cell">{fmtPrice(row.high_price)}</td>
                            <td className="numeric-cell">{fmtPrice(row.low_price)}</td>
                            <td className="numeric-cell">{fmtPrice(row.close_price)}</td>
                            <td className="numeric-cell">{fmtNumber(row.volume)}</td>
                            <td className="numeric-cell">{fmtPercent(row.change_rate)}</td>
                            <td className="numeric-cell">{fmtPrice(row.ma5)}</td>
                            <td className="numeric-cell">{fmtPrice(row.ma20)}</td>
                            <td className="numeric-cell">{fmtPrice(row.ma60)}</td>
                            <td className="numeric-cell">{fmtPrice(row.ma120)}</td>
                            <td className="numeric-cell">{fmtPrice(row.ma240)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="pagination-bar">
                    <div className="pagination-info">이번 페이지 {dailyRows.length}건</div>
                    <div className="pagination-actions">
                      <button
                        className="btn btn-secondary"
                        disabled={!canDailyPrev}
                        onClick={() => {
                          const next = Math.max(0, dailyOffset - DAILY_LIMIT);
                          setDailyOffset(next);
                          void loadDaily(selectedStock.stock_id, next);
                        }}
                      >
                        이전
                      </button>
                      <button
                        className="btn btn-secondary"
                        disabled={!canDailyNext}
                        onClick={() => {
                          const next = dailyOffset + DAILY_LIMIT;
                          setDailyOffset(next);
                          void loadDaily(selectedStock.stock_id, next);
                        }}
                      >
                        다음
                      </button>
                    </div>
                  </div>
                </>
              ) : null}
            </>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}

export default StockPricesPage;
