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
    try {
      await action();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "작업 실행 중 오류가 발생했습니다.");
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
      setActionMessage(
        `선택 뉴스 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`,
      );
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
      setActionMessage(
        `선택 공시 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건`,
      );
    });
  };

  const onCollectSelectedCandles = async () => {
    if (selectedWatchlistStockIds.length === 0) return;
    await runAction("collect-selected-candles", async () => {
      const result = await repositories.stockPrices.collectSelected({
        stock_ids: selectedWatchlistStockIds,
        period_years: 2,
        source: "pykrx",
      });
      setSelectedPriceCollectResult(result);
      setActionMessage(
        `선택 캔들 수집 완료: 요청 ${result.requested_count}건, 성공 ${result.success_count}건, 실패 ${result.failed_count}건, 저장 ${result.saved_count}건, source=pykrx`,
      );
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
        title="관심종목 Pool"
        description="관심종목 Pool은 DrCT에셋에서 뉴스, 공시, 가격·캔들 데이터를 우선 수집하고 분석할 종목 목록입니다."
        action={<StatusBadge label={`활성 ${watchlistStockIds.length}건`} tone="blue" />}
      />

      <SectionCard title="빠른 작업">
        <p className="watchlist-quick-desc">
          선택한 관심종목의 실제 운영 데이터를 기준으로 수집합니다. 캔들 수집은 항상 PyKRX 기준으로 실행되며, 최초 수집은 최근 2년,
          이후에는 자동으로 증분 또는 최신 구간 재조회로 분기됩니다.
        </p>
        <div className="pool-action-row">
          <button className="btn btn-primary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-news"} onClick={() => void onCollectSelectedNews()}>
            {actionLoading === "collect-selected-news" ? "선택 뉴스 수집 중..." : "선택 뉴스 수집"}
          </button>
          <button
            className="btn btn-primary"
            disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-disclosures"}
            onClick={() => void onCollectSelectedDisclosures()}
          >
            {actionLoading === "collect-selected-disclosures" ? "선택 공시 수집 중..." : "선택 공시 수집"}
          </button>
          <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-candles"} onClick={() => void onCollectSelectedCandles()}>
            {actionLoading === "collect-selected-candles" ? "선택 캔들 수집 중..." : "선택 캔들 수집"}
          </button>
          <button className="btn btn-secondary" onClick={() => navigate("/advisory-packages")}>
            GPT 자문 패키지
          </button>
        </div>
        <p className="watchlist-quick-note">
          관심종목을 선택하면 뉴스, 공시, 캔들 수집을 각각 실행할 수 있습니다. 운영 화면에서는 캔들 수집 source를 노출하지 않고 PyKRX로 고정합니다.
        </p>

        {actionMessage ? <div className="inline-result">{actionMessage}</div> : null}
        {actionError ? <div className="inline-result inline-error">{actionError}</div> : null}
        {bulkResult ? (
          <div className="inline-result">
            요청 {bulkResult.requested_count}건 / 추가 {bulkResult.inserted_count}건 / 재활성화 {bulkResult.reactivated_count}건 / 건너뜀{" "}
            {bulkResult.skipped_count}건
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
                              if (e.target.checked) setSelectedStockIds((prev) => Array.from(new Set([...prev, stock.id])));
                              else setSelectedStockIds((prev) => prev.filter((id) => id !== stock.id));
                            }}
                          />
                        </td>
                        <td>{stock.stock_code}</td>
                        <td className="cell-title">{stock.stock_name}</td>
                        <td>{stock.market || "-"}</td>
                        <td>{securityTypeLabel(stock.security_type)}</td>
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
                              if (e.target.checked) setSelectedWatchlistStockIds((prev) => Array.from(new Set([...prev, item.stock_id])));
                              else setSelectedWatchlistStockIds((prev) => prev.filter((id) => id !== item.stock_id));
                            }}
                          />
                          {item.is_active === 1 ? (
                            <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(item, 0)} disabled={actionLoading === `watchlist-${item.id}-0`}>
                              비활성
                            </button>
                          ) : (
                            <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(item, 1)} disabled={actionLoading === `watchlist-${item.id}-1`}>
                              다시 활성화
                            </button>
                          )}
                        </div>
                      </td>
                      <td>{item.stock_code}</td>
                      <td className="cell-title">{item.stock_name}</td>
                      <td>{item.market || "-"}</td>
                      <td>{securityTypeLabel(item.security_type)}</td>
                      <td>
                        <StatusBadge label={item.is_active === 1 ? "활성" : "비활성"} tone={item.is_active === 1 ? "emerald" : "slate"} />
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
