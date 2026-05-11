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
import type { StockPriceCollectResult } from "@/types/stockPrice";
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

function securityTypeLabel(value?: string | null): string {
  return STOCK_TYPES.find((item) => item.value === value)?.label ?? "기타";
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.slice(0, 10);
}

function WatchlistPage() {
  const navigate = useNavigate();
  const stockLimit = 20;
  const watchlistLimit = 20;

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [watchlist, setWatchlist] = useState<Watchlist[]>([]);
  const [watchlistStockIds, setWatchlistStockIds] = useState<number[]>([]);

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
  const [selectedDisclosureCollectResult, setSelectedDisclosureCollectResult] = useState<DisclosureCollectSelectedResponse | null>(null);
  const [selectedPriceCollectResult, setSelectedPriceCollectResult] = useState<StockPriceCollectResult | null>(null);
  const [selectedPriceUpdateResult, setSelectedPriceUpdateResult] = useState<StockPriceCollectResult | null>(null);

  const loadStocks = async (nextOffset = stockOffset) => {
    setLoadingStocks(true);
    setStockError("");
    try {
      const [stockRows, activeStockIds] = await Promise.all([
        repositories.stocks.list({
          market: stockMarket || undefined,
          security_type: stockSecurityType || undefined,
          keyword: stockKeyword || undefined,
          is_active: 1,
          limit: stockLimit,
          offset: nextOffset,
        }),
        repositories.watchlist.listStockIds(),
      ]);
      setStocks(stockRows);
      setWatchlistStockIds(activeStockIds);
    } catch (error) {
      setStockError(error instanceof Error ? error.message : "전체 종목 조회 중 오류가 발생했습니다.");
    } finally {
      setLoadingStocks(false);
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
      setWatchlist(rows);
    } catch (error) {
      setWatchlistError(error instanceof Error ? error.message : "관심종목 Pool 조회 중 오류가 발생했습니다.");
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

  const registeredStockIdSet = useMemo(() => new Set(watchlistStockIds), [watchlistStockIds]);
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
    setSelectedPriceUpdateResult(null);
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "작업 실행 중 오류가 발생했습니다.");
    } finally {
      setActionLoading("");
    }
  };

  const onSearchStocks = async () => {
    setStockOffset(0);
    setSelectedStockIds([]);
    await loadStocks(0);
  };

  const onResetStocks = async () => {
    setStockMarket("");
    setStockSecurityType("common_stock");
    setStockKeyword("");
    setStockOffset(0);
    setSelectedStockIds([]);
    setTimeout(() => void loadStocks(0), 0);
  };

  const onPrevStocks = async () => {
    const nextOffset = Math.max(0, stockOffset - stockLimit);
    setStockOffset(nextOffset);
    setSelectedStockIds([]);
    await loadStocks(nextOffset);
  };

  const onNextStocks = async () => {
    const nextOffset = stockOffset + stockLimit;
    setStockOffset(nextOffset);
    setSelectedStockIds([]);
    await loadStocks(nextOffset);
  };

  const onSearchWatchlist = async () => {
    setWatchlistOffset(0);
    setSelectedWatchlistStockIds([]);
    await loadWatchlist(0);
  };

  const onResetWatchlist = async () => {
    setWatchlistMarket("");
    setWatchlistState(1);
    setWatchlistKeyword("");
    setWatchlistOffset(0);
    setSelectedWatchlistStockIds([]);
    setTimeout(() => void loadWatchlist(0), 0);
  };

  const onPrevWatchlist = async () => {
    const nextOffset = Math.max(0, watchlistOffset - watchlistLimit);
    setWatchlistOffset(nextOffset);
    setSelectedWatchlistStockIds([]);
    await loadWatchlist(nextOffset);
  };

  const onNextWatchlist = async () => {
    const nextOffset = watchlistOffset + watchlistLimit;
    setWatchlistOffset(nextOffset);
    setSelectedWatchlistStockIds([]);
    await loadWatchlist(nextOffset);
  };

  const onToggleSelectAllStocks = () => {
    if (allSelectableStocksChecked) {
      setSelectedStockIds((prev) => prev.filter((id) => !currentSelectableStockIds.includes(id)));
      return;
    }
    setSelectedStockIds((prev) => Array.from(new Set([...prev, ...currentSelectableStockIds])));
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

  const onToggleWatchlistActive = async (item: Watchlist, nextActive: number) => {
    await runAction(`watchlist-${item.id}-${nextActive}`, async () => {
      await repositories.watchlist.update(item.id, { is_active: nextActive });
      setActionMessage(nextActive === 1 ? "관심종목 Pool을 다시 활성화했습니다." : "관심종목 Pool에서 비활성화했습니다.");
      await refreshAll(stockOffset, watchlistOffset);
    });
  };

  const onCollectSelectedNews = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("관심종목을 선택하면 실행할 수 있습니다.");
      return;
    }
    await runAction("collect-selected-news", async () => {
      const result = await repositories.news.collectNewsForSelectedWatchlist({
        stock_ids: selectedWatchlistStockIds,
        providers: ["naver"],
        display: 20,
        sort: "date",
      });
      setSelectedNewsCollectResult(result);
      setActionMessage(
        `선택 뉴스 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`,
      );
    });
  };

  const onCollectSelectedDisclosures = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("관심종목을 선택하면 실행할 수 있습니다.");
      return;
    }
    await runAction("collect-selected-disclosures", async () => {
      const result = await repositories.disclosures.collectDisclosuresForSelectedWatchlist({
        stock_ids: selectedWatchlistStockIds,
        days: 30,
        page_count: 100,
      });
      setSelectedDisclosureCollectResult(result);
      setActionMessage(
        `선택 공시 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`,
      );
    });
  };

  const onCollectSelectedCandles = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("관심종목을 선택하면 실행할 수 있습니다.");
      return;
    }
    await runAction("collect-selected-candles", async () => {
      const result = await repositories.stockPrices.collectSelected({
        stock_ids: selectedWatchlistStockIds,
        period_years: 2,
        source: "mock",
      });
      setSelectedPriceCollectResult(result);
      setActionMessage(
        `선택 캔들 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 저장 ${result.saved_count}건`,
      );
    });
  };

  const onUpdateSelectedCandles = async () => {
    if (selectedWatchlistStockIds.length === 0) {
      setActionError("관심종목을 선택하면 실행할 수 있습니다.");
      return;
    }
    await runAction("update-selected-candles", async () => {
      const result = await repositories.stockPrices.updateSelected({
        stock_ids: selectedWatchlistStockIds,
        source: "mock",
      });
      setSelectedPriceUpdateResult(result);
      setActionMessage(
        `선택 캔들 갱신 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 저장 ${result.saved_count}건`,
      );
    });
  };

  const selectionGuideText =
    selectedWatchlistStockIds.length === 0
      ? "관심종목을 선택하면 뉴스·공시·캔들 수집을 실행할 수 있습니다."
      : `선택된 종목 ${selectedWatchlistStockIds.length}개를 대상으로 수집 작업을 실행합니다.`;

  return (
    <div className="space-y-4">
      <PageHeader
        title="관심종목 Pool"
        description="관심종목 Pool은 DrCT에셋이 뉴스, 공시, 가격/캔들 데이터, GPT 자문 패키지를 우선 수집·분석할 종목 목록입니다."
        action={<StatusBadge label={`활성 ${watchlistStockIds.length}건`} tone="blue" />}
      />

      <SectionCard className="watchlist-pool-hero">
        <div className="watchlist-pool-hero-grid">
          <div>
            <p className="watchlist-pool-eyebrow">ANALYSIS POOL</p>
            <h3 className="watchlist-pool-title">뉴스·공시·가격 데이터를 수집할 종목 Pool</h3>
            <p className="watchlist-pool-copy">
              관심종목 Pool은 DrCT에셋의 우선 분석 대상입니다.
              <br />
              이 목록을 기준으로 뉴스, 공시, 가격/캔들 데이터 수집과 GPT 자문 패키지 생성을 수행합니다.
            </p>
          </div>
          <div className="watchlist-pool-stat-grid">
            <div className="watchlist-pool-stat">
              <span className="watchlist-pool-stat-label">관심종목 Pool</span>
              <strong>{watchlistStockIds.length}</strong>
            </div>
            <div className="watchlist-pool-stat">
              <span className="watchlist-pool-stat-label">전체 관심종목</span>
              <strong>{watchlist.length}</strong>
            </div>
            <div className="watchlist-pool-stat">
              <span className="watchlist-pool-stat-label">선택된 종목</span>
              <strong>{selectedWatchlistStockIds.length}</strong>
            </div>
            <div className="watchlist-pool-stat">
              <span className="watchlist-pool-stat-label">Pool 상태</span>
              <strong>{watchlistState === 1 ? "활성" : watchlistState === 0 ? "비활성" : "전체"}</strong>
            </div>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="빠른 작업">
        <p className="watchlist-quick-desc">
          관심종목 Pool 목록에서 체크한 종목을 대상으로 뉴스와 공시를 수집합니다. 수집된 자료는 GPT 자문 패키지의 근거로 활용됩니다.
        </p>
        <div className="pool-action-row">
          <button
            className="btn btn-primary"
            onClick={() => void onCollectSelectedNews()}
            disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-news"}
            title={selectedWatchlistStockIds.length === 0 ? "관심종목을 선택하면 실행할 수 있습니다." : undefined}
          >
            {actionLoading === "collect-selected-news" ? "선택 뉴스 수집 중..." : "선택 뉴스 수집"}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => void onCollectSelectedDisclosures()}
            disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-disclosures"}
            title={selectedWatchlistStockIds.length === 0 ? "관심종목을 선택하면 실행할 수 있습니다." : undefined}
          >
            {actionLoading === "collect-selected-disclosures" ? "선택 공시 수집 중..." : "선택 공시 수집"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => void onCollectSelectedCandles()}
            disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-candles"}
            title={selectedWatchlistStockIds.length === 0 ? "관심종목을 선택하면 실행할 수 있습니다." : "mock 데이터로 수집됩니다."}
          >
            {actionLoading === "collect-selected-candles" ? "선택 캔들 수집 중..." : "선택 캔들 수집"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => void onUpdateSelectedCandles()}
            disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "update-selected-candles"}
            title={selectedWatchlistStockIds.length === 0 ? "관심종목을 선택하면 실행할 수 있습니다." : "mock 데이터로 갱신됩니다."}
          >
            {actionLoading === "update-selected-candles" ? "선택 캔들 갱신 중..." : "선택 캔들 갱신"}
          </button>
          <button className="btn btn-secondary" onClick={() => navigate("/advisory-packages")}>
            GPT 자문 패키지
          </button>
        </div>
        <p className="watchlist-quick-note">{selectionGuideText}</p>
        <p className="watchlist-quick-note">현재 캔들 수집은 구조 검증용 mock 데이터이며, 이후 증권사 API로 교체할 예정입니다.</p>

        {actionMessage ? <div className="inline-result">{actionMessage}</div> : null}
        {actionError ? <div className="inline-result inline-error">{actionError}</div> : null}
        {bulkResult ? (
          <div className="inline-result">
            요청 {bulkResult.requested_count}건 / 추가 {bulkResult.inserted_count}건 / 재활성화 {bulkResult.reactivated_count}건 / 건너뜀{" "}
            {bulkResult.skipped_count}건
          </div>
        ) : null}
        {selectedNewsCollectResult ? (
          <div className={`inline-result ${selectedNewsCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>
            선택 뉴스 수집: 요청 {selectedNewsCollectResult.requested_count}건, 성공 {selectedNewsCollectResult.success_count}건, 실패{" "}
            {selectedNewsCollectResult.failed_count}건
          </div>
        ) : null}
        {selectedDisclosureCollectResult ? (
          <div className={`inline-result ${selectedDisclosureCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>
            선택 공시 수집: 요청 {selectedDisclosureCollectResult.requested_count}건, 성공 {selectedDisclosureCollectResult.success_count}건, 실패{" "}
            {selectedDisclosureCollectResult.failed_count}건
          </div>
        ) : null}
        {selectedPriceCollectResult ? (
          <div className={`inline-result ${selectedPriceCollectResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>
            선택 캔들 수집: 요청 {selectedPriceCollectResult.requested_count}건, 성공 {selectedPriceCollectResult.success_count}건, 실패{" "}
            {selectedPriceCollectResult.failed_count}건, 저장 {selectedPriceCollectResult.saved_count}건
          </div>
        ) : null}
        {selectedPriceUpdateResult ? (
          <div className={`inline-result ${selectedPriceUpdateResult.failed_count > 0 ? "inline-warning" : "inline-success"}`}>
            선택 캔들 갱신: 요청 {selectedPriceUpdateResult.requested_count}건, 성공 {selectedPriceUpdateResult.success_count}건, 실패{" "}
            {selectedPriceUpdateResult.failed_count}건, 저장 {selectedPriceUpdateResult.saved_count}건
          </div>
        ) : null}
      </SectionCard>

      <div className="watchlist-pool-layout">
        <SectionCard title="전체 종목 검색">
          <form
            className="watchlist-search-row"
            onSubmit={(e) => {
              e.preventDefault();
              void onSearchStocks();
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
            <input
              className="input-control"
              placeholder="종목코드 또는 종목명"
              value={stockKeyword}
              onChange={(e) => setStockKeyword(e.target.value)}
            />
            <button type="submit" className="btn btn-primary">
              검색
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void onResetStocks()}>
              초기화
            </button>
          </form>

          <div className="action-row">
            <div className="action-row-left">
              <button className="btn btn-primary" onClick={() => void onBulkAdd()} disabled={selectedStockIds.length === 0 || actionLoading === "bulk-add"}>
                {actionLoading === "bulk-add" ? "추가 중..." : `선택 종목 관심종목 추가 (${selectedStockIds.length})`}
              </button>
            </div>
            <div className="pagination-info">현재 페이지 {Math.floor(stockOffset / stockLimit) + 1}</div>
          </div>

          {loadingStocks ? <p className="text-sm text-muted">종목 검색 중입니다.</p> : null}
          {stockError ? <p className="text-sm text-rose-600">{stockError}</p> : null}
          {!loadingStocks && !stockError && stocks.length === 0 ? <EmptyState message="조회된 종목이 없습니다." /> : null}

          {!loadingStocks && !stockError && stocks.length > 0 ? (
            <>
              <div className="table-shell">
                <table className="data-table compact-table min-w-[760px]">
                  <thead>
                    <tr>
                      <th className="selection-cell">
                        <input className="selection-checkbox" type="checkbox" checked={allSelectableStocksChecked} onChange={onToggleSelectAllStocks} />
                      </th>
                      <th>종목코드</th>
                      <th>종목명</th>
                      <th>시장</th>
                      <th>종목유형</th>
                      <th>활성</th>
                      <th>추가상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stocks.map((stock) => {
                      const registered = registeredStockIdSet.has(stock.id);
                      return (
                        <tr key={stock.id}>
                          <td className="selection-cell">
                            <input
                              className="selection-checkbox"
                              type="checkbox"
                              disabled={registered}
                              checked={selectedStockIds.includes(stock.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedStockIds((prev) => Array.from(new Set([...prev, stock.id])));
                                  return;
                                }
                                setSelectedStockIds((prev) => prev.filter((id) => id !== stock.id));
                              }}
                            />
                          </td>
                          <td className="cell-nowrap">{stock.stock_code}</td>
                          <td className="cell-title">{stock.stock_name}</td>
                          <td className="cell-nowrap">{stock.market || "-"}</td>
                          <td className="cell-nowrap">{securityTypeLabel(stock.security_type)}</td>
                          <td>
                            <StatusBadge label={stock.is_active === 1 ? "활성" : "비활성"} tone={stock.is_active === 1 ? "emerald" : "slate"} />
                          </td>
                          <td>
                            <StatusBadge label={registered ? "등록됨" : "추가 가능"} tone={registered ? "blue" : "slate"} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="pagination-bar">
                <div className="pagination-info">이번 페이지 {stocks.length}건</div>
                <div className="pagination-actions">
                  <button className="btn btn-secondary" onClick={() => void onPrevStocks()} disabled={!canPrevStocks}>
                    이전
                  </button>
                  <button className="btn btn-secondary" onClick={() => void onNextStocks()} disabled={!canNextStocks}>
                    다음
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>

        <SectionCard title="관심종목 Pool 목록">
          <form
            className="watchlist-search-row watchlist-search-row-pool"
            onSubmit={(e) => {
              e.preventDefault();
              void onSearchWatchlist();
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
            <input
              className="input-control"
              placeholder="종목코드 또는 종목명"
              value={watchlistKeyword}
              onChange={(e) => setWatchlistKeyword(e.target.value)}
            />
            <button type="submit" className="btn btn-primary">
              검색
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void onResetWatchlist()}>
              초기화
            </button>
          </form>

          {loadingWatchlist ? <p className="text-sm text-muted">관심종목 Pool을 불러오는 중입니다.</p> : null}
          {watchlistError ? <p className="text-sm text-rose-600">{watchlistError}</p> : null}
          {!loadingWatchlist && !watchlistError && watchlist.length === 0 ? <EmptyState message="조회된 관심종목 Pool이 없습니다." /> : null}

          {!loadingWatchlist && !watchlistError && watchlist.length > 0 ? (
            <>
              <div className="table-shell">
                <table className="data-table compact-table watchlist-table min-w-[860px]">
                  <thead>
                    <tr>
                      <th className="action-cell">작업</th>
                      <th>종목코드</th>
                      <th>종목명</th>
                      <th>시장</th>
                      <th>종목유형</th>
                      <th>상태</th>
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
                                if (e.target.checked) {
                                  setSelectedWatchlistStockIds((prev) => Array.from(new Set([...prev, item.stock_id])));
                                  return;
                                }
                                setSelectedWatchlistStockIds((prev) => prev.filter((stockId) => stockId !== item.stock_id));
                              }}
                            />
                            {item.is_active === 1 ? (
                              <button
                                className="btn btn-secondary btn-table-sm"
                                onClick={() => void onToggleWatchlistActive(item, 0)}
                                disabled={actionLoading === `watchlist-${item.id}-0`}
                              >
                                해제
                              </button>
                            ) : (
                              <button
                                className="btn btn-secondary btn-table-sm"
                                onClick={() => void onToggleWatchlistActive(item, 1)}
                                disabled={actionLoading === `watchlist-${item.id}-1`}
                              >
                                다시 활성화
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="cell-nowrap">{item.stock_code}</td>
                        <td className="cell-title">{item.stock_name}</td>
                        <td className="cell-nowrap">{item.market || "-"}</td>
                        <td className="cell-nowrap">{securityTypeLabel(item.security_type)}</td>
                        <td>
                          <StatusBadge label={item.is_active === 1 ? "활성" : "비활성"} tone={item.is_active === 1 ? "emerald" : "slate"} />
                        </td>
                        <td className="cell-nowrap">{formatDate(item.registered_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination-bar">
                <div className="pagination-info">이번 페이지 {watchlist.length}건</div>
                <div className="pagination-actions">
                  <button className="btn btn-secondary" onClick={() => void onPrevWatchlist()} disabled={!canPrevWatchlist}>
                    이전
                  </button>
                  <button className="btn btn-secondary" onClick={() => void onNextWatchlist()} disabled={!canNextWatchlist}>
                    다음
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}

export default WatchlistPage;
