import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { DisclosureCollectSelectedResponse } from "@/types/disclosure";
import type { NewsCollectSelectedResponse } from "@/types/news";
import type { Stock } from "@/types/stock";
import type { SelectedMarketMetricsCollectResult, StockPriceCollectResult } from "@/types/stockPrice";
import type { Watchlist, WatchlistBulkCreateResponse } from "@/types/watchlist";

const STOCK_TYPES = [
  { value: "common_stock", label: "보통주" },
  { value: "preferred_stock", label: "우선주" },
  { value: "etf", label: "ETF" },
  { value: "etn", label: "ETN" },
  { value: "spac", label: "스팩" },
  { value: "reit", label: "리츠" },
  { value: "other", label: "기타" },
] as const;

const MARKET_OPTIONS = [
  { value: "", label: "전체" },
  { value: "KOSPI", label: "KOSPI" },
  { value: "KOSDAQ", label: "KOSDAQ" },
] as const;

const WATCHLIST_STATE_OPTIONS = [
  { value: 1, label: "활성" },
  { value: 0, label: "비활성" },
  { value: -1, label: "전체" },
] as const;

type WatchlistStatus = "not_registered" | "active" | "inactive";

function securityTypeLabel(value?: string | null): string {
  return STOCK_TYPES.find((item) => item.value === value)?.label ?? "기타";
}

function stockStatusLabel(isActive?: number | null): string {
  return isActive === 1 ? "정상" : "비활성";
}

function watchlistStatusLabel(status: WatchlistStatus): string {
  if (status === "active") return "관심등록";
  if (status === "inactive") return "관심비활성";
  return "미등록";
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.slice(0, 10);
}

function normalizeKrStockCode(code?: string | null): string {
  const value = (code || "").trim().toUpperCase();
  if (/^A\d{6}$/.test(value)) return value.slice(1);
  return value;
}

function safeMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    const candidates = [record.detail, record.message, record.error];
    for (const value of candidates) {
      if (typeof value === "string" && value.trim()) return value;
      if (Array.isArray(value) && value.length > 0) {
        const first = value[0];
        if (typeof first === "string") return first;
        if (first && typeof first === "object") {
          const msg = (first as Record<string, unknown>).msg;
          if (typeof msg === "string" && msg.trim()) return msg;
        }
      }
    }
  }
  return fallback;
}

function WatchlistPage() {
  const navigate = useNavigate();
  const stockLimit = 20;
  const watchlistLimit = 20;

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [watchlist, setWatchlist] = useState<Watchlist[]>([]);
  const [watchlistStockIds, setWatchlistStockIds] = useState<number[]>([]);
  const [watchlistStatusByStockId, setWatchlistStatusByStockId] = useState<Record<number, WatchlistStatus>>({});

  const [stockMarket, setStockMarket] = useState("");
  const [stockSecurityType, setStockSecurityType] = useState("common_stock");
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockOffset, setStockOffset] = useState(0);

  const [watchlistMarket, setWatchlistMarket] = useState("");
  const [watchlistState, setWatchlistState] = useState(1);
  const [watchlistKeyword, setWatchlistKeyword] = useState("");
  const [watchlistOffset, setWatchlistOffset] = useState(0);

  const [selectedStockIds, setSelectedStockIds] = useState<number[]>([]);
  const [selectedWatchlistStockIds, setSelectedWatchlistStockIds] = useState<number[]>([]);

  const [loadingStocks, setLoadingStocks] = useState(false);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [stockError, setStockError] = useState("");
  const [watchlistError, setWatchlistError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionLoading, setActionLoading] = useState("");

  const [bulkResult, setBulkResult] = useState<WatchlistBulkCreateResponse | null>(null);
  const [selectedNewsCollectResult, setSelectedNewsCollectResult] = useState<NewsCollectSelectedResponse | null>(null);
  const [selectedDisclosureCollectResult, setSelectedDisclosureCollectResult] =
    useState<DisclosureCollectSelectedResponse | null>(null);
  const [selectedPriceCollectResult, setSelectedPriceCollectResult] = useState<StockPriceCollectResult | null>(null);
  const [selectedMarketMetricsCollectResult, setSelectedMarketMetricsCollectResult] =
    useState<SelectedMarketMetricsCollectResult | null>(null);
  const [selectedTechnicalIndicatorResult, setSelectedTechnicalIndicatorResult] = useState<{
    success_count: number;
    failed_count: number;
    saved_count: number;
  } | null>(null);

  const fetchAllWatchlistRows = async (): Promise<Watchlist[]> => {
    const pageLimit = 500;
    const maxPages = 50;
    const rows: Watchlist[] = [];
    let offset = 0;

    for (let page = 0; page < maxPages; page += 1) {
      const pageRows = await repositories.watchlist.list({
        is_active: undefined,
        limit: pageLimit,
        offset,
      });
      rows.push(...pageRows);

      if (pageRows.length < pageLimit) {
        break;
      }
      offset += pageLimit;
    }

    return rows;
  };

  const loadStocks = async (nextOffset = stockOffset) => {
    setLoadingStocks(true);
    setStockError("");
    try {
      const stockRows = await repositories.stocks.list({
        market: stockMarket || undefined,
        security_type: stockSecurityType || undefined,
        keyword: stockKeyword || undefined,
        is_active: 1,
        limit: stockLimit,
        offset: nextOffset,
      });

      setStocks(Array.isArray(stockRows) ? stockRows : []);
    } catch (error) {
      setStockError(safeMessage(error, "전체 종목 조회 중 오류가 발생했습니다."));
      setStocks([]);
      return;
    } finally {
      setLoadingStocks(false);
    }

    try {
      const [activeStockIds, allWatchlistRows] = await Promise.all([
        repositories.watchlist.listStockIds(),
        fetchAllWatchlistRows(),
      ]);
      const nextStatusByStockId: Record<number, WatchlistStatus> = {};
      allWatchlistRows.forEach((item) => {
        nextStatusByStockId[item.stock_id] = item.is_active === 1 ? "active" : "inactive";
      });
      setWatchlistStockIds(Array.isArray(activeStockIds) ? activeStockIds : []);
      setWatchlistStatusByStockId(nextStatusByStockId);
    } catch (error) {
      // watchlist 상태 맵 조회 실패는 전체 종목 검색 결과 노출을 막지 않도록 분리한다.
      setWatchlistStockIds([]);
      setWatchlistStatusByStockId({});
      setStockError((prev) => prev || safeMessage(error, "관심종목 상태 조회 중 오류가 발생했습니다."));
    }
  };

  const loadWatchlist = async (nextOffset = watchlistOffset) => {
    setLoadingWatchlist(true);
    setWatchlistError("");
    try {
      const rows = await repositories.watchlist.list({
        market: watchlistMarket || undefined,
        keyword: watchlistKeyword || undefined,
        is_active: watchlistState >= 0 ? watchlistState : undefined,
        limit: watchlistLimit,
        offset: nextOffset,
      });
      setWatchlist(Array.isArray(rows) ? rows : []);
    } catch (error) {
      setWatchlistError(safeMessage(error, "관심종목 Pool 조회 중 오류가 발생했습니다."));
      setWatchlist([]);
    } finally {
      setLoadingWatchlist(false);
    }
  };

  const refreshAll = async (nextStockOffset = stockOffset, nextWatchlistOffset = watchlistOffset) => {
    await Promise.all([loadStocks(nextStockOffset), loadWatchlist(nextWatchlistOffset)]);
  };

  useEffect(() => {
    void refreshAll(0, 0);
  }, []);

  const registeredStockIdSet = useMemo(
    () => new Set(Object.keys(watchlistStatusByStockId).map((id) => Number(id))),
    [watchlistStatusByStockId],
  );

  const currentSelectableStockIds = useMemo(
    () => stocks.filter((item) => !registeredStockIdSet.has(item.id)).map((item) => item.id),
    [stocks, registeredStockIdSet],
  );

  const allSelectableStocksChecked =
    currentSelectableStockIds.length > 0 && currentSelectableStockIds.every((id) => selectedStockIds.includes(id));

  const canPrevStocks = stockOffset > 0;
  const canNextStocks = stocks.length >= stockLimit;
  const canPrevWatchlist = watchlistOffset > 0;
  const canNextWatchlist = watchlist.length >= watchlistLimit;

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionLoading(key);
    setActionError("");
    setActionMessage("");
    setBulkResult(null);
    setSelectedNewsCollectResult(null);
    setSelectedDisclosureCollectResult(null);
    setSelectedPriceCollectResult(null);
    setSelectedMarketMetricsCollectResult(null);
    setSelectedTechnicalIndicatorResult(null);
    try {
      await action();
    } catch (error) {
      setActionError(safeMessage(error, "작업 실행 중 오류가 발생했습니다."));
    } finally {
      setActionLoading("");
    }
  };

  const onBulkAdd = async () => {
    if (selectedStockIds.length === 0) {
      setActionError("추가할 종목을 먼저 선택해 주세요.");
      return;
    }

    await runAction("bulk-add", async () => {
      const result = await repositories.watchlist.bulkAdd({
        stock_ids: selectedStockIds,
        memo: "관심종목 Pool 추가",
      });
      setBulkResult(result);
      setActionMessage(result.message);
      setSelectedStockIds([]);
      await refreshAll(stockOffset, watchlistOffset);
    });
  };

  const onCollectSelectedNews = async () => {
    if (selectedWatchlistStockIds.length === 0) return;
    await runAction("collect-selected-news", async () => {
      const result = await repositories.news.collectNewsForSelectedWatchlist({
        stock_ids: selectedWatchlistStockIds,
        providers: ["naver"],
        display: 20,
        sort: "date",
      });
      setSelectedNewsCollectResult(result);
      setActionMessage(`선택 뉴스 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`);
    });
  };

  const onCollectSelectedDisclosures = async () => {
    if (selectedWatchlistStockIds.length === 0) return;
    await runAction("collect-selected-disclosures", async () => {
      const result = await repositories.disclosures.collectDisclosuresForSelectedWatchlist({
        stock_ids: selectedWatchlistStockIds,
        days: 30,
        page_count: 100,
      });
      setSelectedDisclosureCollectResult(result);
      setActionMessage(`선택 공시 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`);
    });
  };

  const onCollectSelectedCandles = async () => {
    if (selectedWatchlistStockIds.length === 0) return;
    await runAction("collect-selected-candles", async () => {
      const result = await repositories.stockPrices.collectSelected({
        stock_ids: selectedWatchlistStockIds,
        period_years: 2,
        source: "kiwoom_rest",
      });
      setSelectedPriceCollectResult(result);
      setActionMessage(`선택 캔들 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건, 저장 ${result.saved_count}건`);
    });
  };

  const onCollectSelectedMarketMetrics = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("시장지표를 갱신할 관심종목을 선택해 주세요.");
      return;
    }

    await runAction("collect-selected-market-metrics", async () => {
      const result = await repositories.stockPrices.collectSelectedMarketMetrics({
        stock_ids: selectedWatchlistStockIds,
        source: "kiwoom_rest",
      });
      setSelectedMarketMetricsCollectResult(result);
      setActionMessage(`선택 시장지표 갱신 완료: 성공 ${result.success_count}건, 실패 ${result.failed_count}건`);
    });
  };

  const onRecalculateSelectedTechnicalIndicators = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("기술적 지표를 재계산할 종목을 선택해 주세요.");
      return;
    }
    await runAction("recalculate-selected-technical-indicators", async () => {
      const result = await repositories.stockPrices.calculateTechnicalIndicatorsForSelected(selectedWatchlistStockIds);
      setSelectedTechnicalIndicatorResult({
        success_count: result.success_count,
        failed_count: result.failed_count,
        saved_count: result.saved_count,
      });
      setActionMessage(`기술적 지표 재계산 완료: 성공 ${result.success_count}건, 실패 ${result.failed_count}건, 저장 ${result.saved_count}건`);
    });
  };

  const onNormalizeStockCodes = async () => {
    const confirmed = window.confirm(
      "A-prefix가 붙은 국내 주식 종목코드를 6자리 표준 코드로 정리합니다.\n예: A097230 → 097230\n관심종목 및 가격·캔들 수집 기준을 맞추기 위한 작업입니다.\n계속하시겠습니까?",
    );
    if (!confirmed) return;

    await runAction("normalize-stock-codes", async () => {
      const result = await repositories.stocks.normalizeCodes(false);
      setActionMessage(
        `종목코드 표준화 완료: ${result.updated_count}건 갱신` +
          (result.duplicate_conflict_count > 0 ? ` / 충돌 ${result.duplicate_conflict_count}건` : ""),
      );
      await refreshAll(stockOffset, watchlistOffset);
    });
  };

  const onToggleWatchlistActive = async (item: Watchlist, nextActive: number) => {
    await runAction(`watchlist-${item.id}-${nextActive}`, async () => {
      await repositories.watchlist.update(item.id, { is_active: nextActive });
      await refreshAll(stockOffset, watchlistOffset);
    });
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="관심종목 Data수집"
        description="관심종목 Pool은 뉴스, 공시, 가격·캔들 데이터 수집 및 분석의 기준이 되는 종목 목록입니다."
        action={<StatusBadge label={`활성 ${watchlistStockIds.length}건`} tone="blue" />}
      />

      <SectionCard title="빠른 작업">
        <div className="pool-action-row">
          <button className="btn btn-primary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-news"} onClick={() => void onCollectSelectedNews()}>
            {actionLoading === "collect-selected-news" ? "선택 뉴스 수집 중..." : "선택 뉴스 수집"}
          </button>
          <button className="btn btn-primary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-disclosures"} onClick={() => void onCollectSelectedDisclosures()}>
            {actionLoading === "collect-selected-disclosures" ? "선택 공시 수집 중..." : "선택 공시 수집"}
          </button>
          <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-candles"} onClick={() => void onCollectSelectedCandles()}>
            {actionLoading === "collect-selected-candles" ? "선택 캔들 수집 중..." : "선택 캔들 수집"}
          </button>
          <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-market-metrics"} onClick={() => void onCollectSelectedMarketMetrics()}>
            {actionLoading === "collect-selected-market-metrics" ? "시장지표 갱신 중..." : "선택 시장지표 갱신"}
          </button>
          <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "recalculate-selected-technical-indicators"} onClick={() => void onRecalculateSelectedTechnicalIndicators()}>
            {actionLoading === "recalculate-selected-technical-indicators" ? "기술적 지표 재계산 중..." : "기술적 지표 재계산"}
          </button>
          <button className="btn btn-secondary" onClick={() => navigate("/advisory-packages")}>
            GPT 자문 패키지
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => void onNormalizeStockCodes()}
            disabled={actionLoading === "normalize-stock-codes"}
            aria-busy={actionLoading === "normalize-stock-codes"}
          >
            {actionLoading === "normalize-stock-codes" ? "표준화 중..." : "종목코드 표준화"}
          </button>
        </div>

        {actionMessage ? <div className="inline-result">{actionMessage}</div> : null}
        {actionError ? <div className="inline-result inline-error">{actionError}</div> : null}

        {bulkResult ? (
          <div className="inline-result">
            요청 {bulkResult.requested_count}건 / 추가 {bulkResult.inserted_count}건 / 재활성화 {bulkResult.reactivated_count}건 / 건너뜀 {bulkResult.skipped_count}건
          </div>
        ) : null}

        {selectedNewsCollectResult ? (
          <div className={`inline-result ${selectedNewsCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>선택 뉴스 수집 결과 확인 완료</div>
        ) : null}
        {selectedDisclosureCollectResult ? (
          <div className={`inline-result ${selectedDisclosureCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>선택 공시 수집 결과 확인 완료</div>
        ) : null}
        {selectedPriceCollectResult ? (
          <div className={`inline-result ${selectedPriceCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>선택 캔들 수집 결과 확인 완료</div>
        ) : null}
        {selectedMarketMetricsCollectResult ? (
          <div className={`inline-result ${selectedMarketMetricsCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>선택 시장지표 갱신 결과 확인 완료</div>
        ) : null}
        {selectedTechnicalIndicatorResult ? (
          <div className={`inline-result ${selectedTechnicalIndicatorResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>선택 기술적 지표 재계산 결과 확인 완료</div>
        ) : null}
      </SectionCard>

      <div className="watchlist-pool-layout">
        <SectionCard title="전체 종목 검색">
          <form
            className="watchlist-search-row"
            onSubmit={(e) => {
              e.preventDefault();
              setStockOffset(0);
              setSelectedStockIds([]);
              void loadStocks(0);
            }}
          >
            <select className="select-control" value={stockMarket} onChange={(e) => setStockMarket(e.target.value)}>
              {MARKET_OPTIONS.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <select className="select-control" value={stockSecurityType} onChange={(e) => setStockSecurityType(e.target.value)}>
              {STOCK_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <input className="input-control" placeholder="종목코드 또는 종목명" value={stockKeyword} onChange={(e) => setStockKeyword(e.target.value)} />
            <button type="submit" className="btn btn-primary">
              검색
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setStockMarket("");
                setStockSecurityType("common_stock");
                setStockKeyword("");
                setStockOffset(0);
                setSelectedStockIds([]);
                setTimeout(() => void loadStocks(0), 0);
              }}
            >
              초기화
            </button>
          </form>

          <div className="action-row">
            <button className="btn btn-primary" onClick={() => void onBulkAdd()} disabled={selectedStockIds.length === 0 || actionLoading === "bulk-add"}>
              {actionLoading === "bulk-add" ? "추가 중..." : `선택 종목 관심종목 추가 (${selectedStockIds.length})`}
            </button>
          </div>

          {loadingStocks ? <p className="text-sm text-muted">종목 조회 중입니다.</p> : null}
          {stockError ? <p className="text-sm text-rose-600">{stockError}</p> : null}
          {!loadingStocks && !stockError && stocks.length === 0 ? <EmptyState message="조회된 종목이 없습니다." /> : null}

          {!loadingStocks && !stockError && stocks.length > 0 ? (
            <div className="table-shell">
              <table className="data-table compact-table min-w-[760px]">
                <thead>
                  <tr>
                    <th className="selection-cell">
                      <input
                        className="selection-checkbox"
                        type="checkbox"
                        checked={allSelectableStocksChecked}
                        onChange={() => {
                          if (allSelectableStocksChecked) {
                            setSelectedStockIds((prev) => prev.filter((id) => !currentSelectableStockIds.includes(id)));
                          } else {
                            setSelectedStockIds((prev) => Array.from(new Set([...prev, ...currentSelectableStockIds])));
                          }
                        }}
                      />
                    </th>
                    <th>종목코드</th>
                    <th>종목명</th>
                    <th>시장</th>
                    <th>종목유형</th>
                    <th>종목상태</th>
                    <th>관심상태</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((stock) => {
                    const watchlistStatus = watchlistStatusByStockId[stock.id] ?? "not_registered";
                    const registered = watchlistStatus !== "not_registered";
                    return (
                      <tr key={stock.id}>
                        <td className="selection-cell">
                          <input
                            className="selection-checkbox"
                            type="checkbox"
                            disabled={registered}
                            checked={selectedStockIds.includes(stock.id)}
                            onChange={(e) => {
                              if (e.target.checked) setSelectedStockIds((prev) => Array.from(new Set([...prev, stock.id])));
                              else setSelectedStockIds((prev) => prev.filter((id) => id !== stock.id));
                            }}
                          />
                        </td>
                        <td>{normalizeKrStockCode(stock.stock_code)}</td>
                        <td className="cell-title">{stock.stock_name}</td>
                        <td>{stock.market || "-"}</td>
                        <td>{securityTypeLabel(stock.security_type)}</td>
                        <td>
                          <StatusBadge label={stockStatusLabel(stock.is_active)} tone={stock.is_active === 1 ? "emerald" : "slate"} />
                        </td>
                        <td>
                          <StatusBadge label={watchlistStatusLabel(watchlistStatus)} tone={watchlistStatus === "active" ? "blue" : watchlistStatus === "inactive" ? "amber" : "slate"} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="pagination-bar">
            <div className="pagination-info">이번 페이지 {stocks.length}건</div>
            <div className="pagination-actions">
              <button
                className="btn btn-secondary"
                disabled={!canPrevStocks}
                onClick={() => {
                  const next = Math.max(0, stockOffset - stockLimit);
                  setStockOffset(next);
                  void loadStocks(next);
                }}
              >
                이전
              </button>
              <button
                className="btn btn-secondary"
                disabled={!canNextStocks}
                onClick={() => {
                  const next = stockOffset + stockLimit;
                  setStockOffset(next);
                  void loadStocks(next);
                }}
              >
                다음
              </button>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="관심종목 Pool 목록">
          <form
            className="watchlist-search-row watchlist-search-row-pool"
            onSubmit={(e) => {
              e.preventDefault();
              setWatchlistOffset(0);
              setSelectedWatchlistStockIds([]);
              void loadWatchlist(0);
            }}
          >
            <select className="select-control" value={watchlistMarket} onChange={(e) => setWatchlistMarket(e.target.value)}>
              {MARKET_OPTIONS.map((item) => (
                <option key={`pool-${item.value || "all"}`} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <select className="select-control" value={watchlistState} onChange={(e) => setWatchlistState(Number(e.target.value))}>
              {WATCHLIST_STATE_OPTIONS.map((item) => (
                <option key={`${item.value}`} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <input className="input-control" placeholder="종목코드 또는 종목명" value={watchlistKeyword} onChange={(e) => setWatchlistKeyword(e.target.value)} />
            <button type="submit" className="btn btn-primary">
              검색
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setWatchlistMarket("");
                setWatchlistState(1);
                setWatchlistKeyword("");
                setWatchlistOffset(0);
                setSelectedWatchlistStockIds([]);
                setTimeout(() => void loadWatchlist(0), 0);
              }}
            >
              초기화
            </button>
          </form>

          {loadingWatchlist ? <p className="text-sm text-muted">관심종목 Pool 로딩 중입니다.</p> : null}
          {watchlistError ? <p className="text-sm text-rose-600">{watchlistError}</p> : null}
          {!loadingWatchlist && !watchlistError && watchlist.length === 0 ? <EmptyState message="조회된 관심종목이 없습니다." /> : null}

          {!loadingWatchlist && !watchlistError && watchlist.length > 0 ? (
            <div className="table-shell">
              <table className="data-table compact-table watchlist-table min-w-[860px]">
                <thead>
                  <tr>
                    <th className="action-cell">작업</th>
                    <th>종목코드</th>
                    <th>종목명</th>
                    <th>시장</th>
                    <th>종목유형</th>
                    <th>관심상태</th>
                    <th>등록일</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlist.map((item) => (
                    <tr key={item.id}>
                      <td className="action-cell">
                        <div className="pool-row-actions">
                          <input
                            className="selection-checkbox"
                            type="checkbox"
                            checked={selectedWatchlistStockIds.includes(item.stock_id)}
                            onChange={(e) => {
                              if (e.target.checked) setSelectedWatchlistStockIds((prev) => Array.from(new Set([...prev, item.stock_id])));
                              else setSelectedWatchlistStockIds((prev) => prev.filter((id) => id !== item.stock_id));
                            }}
                          />
                          {item.is_active === 1 ? (
                            <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(item, 0)} disabled={actionLoading === `watchlist-${item.id}-0`}>
                              비활성화
                            </button>
                          ) : (
                            <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(item, 1)} disabled={actionLoading === `watchlist-${item.id}-1`}>
                              다시 활성화
                            </button>
                          )}
                        </div>
                      </td>
                      <td>{normalizeKrStockCode(item.stock_code)}</td>
                      <td className="cell-title">{item.stock_name}</td>
                      <td>{item.market || "-"}</td>
                      <td>{securityTypeLabel(item.security_type)}</td>
                      <td>
                        <StatusBadge label={item.is_active === 1 ? "관심등록" : "관심비활성"} tone={item.is_active === 1 ? "emerald" : "amber"} />
                      </td>
                      <td>{formatDate(item.registered_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="pagination-bar">
            <div className="pagination-info">이번 페이지 {watchlist.length}건</div>
            <div className="pagination-actions">
              <button
                className="btn btn-secondary"
                disabled={!canPrevWatchlist}
                onClick={() => {
                  const next = Math.max(0, watchlistOffset - watchlistLimit);
                  setWatchlistOffset(next);
                  void loadWatchlist(next);
                }}
              >
                이전
              </button>
              <button
                className="btn btn-secondary"
                disabled={!canNextWatchlist}
                onClick={() => {
                  const next = watchlistOffset + watchlistLimit;
                  setWatchlistOffset(next);
                  void loadWatchlist(next);
                }}
              >
                다음
              </button>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

export default WatchlistPage;
