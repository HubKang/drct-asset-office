import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "@/components/common/EmptyState";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { DisclosureCollectSelectedResponse } from "@/types/disclosure";
import type { MarketTheme, MarketThemeStock } from "@/types/marketTheme";
import type { NewsCollectSelectedResponse } from "@/types/news";
import type { Stock } from "@/types/stock";
import type { SelectedMarketMetricsCollectResult, StockPriceCollectResult } from "@/types/stockPrice";
import type { Watchlist } from "@/types/watchlist";

type WatchlistViewMode = "theme" | "list";
type WatchlistStatus = "not_registered" | "active" | "inactive";
type PriceCollectionMode = "recent" | "full";
type ThemeGroup = { themeName: string; rows: Watchlist[]; activeCount: number; inactiveCount: number };
type ThemeMapPayload = { nameMap: Record<number, string>; idMap: Record<number, number> };

const MARKET_OPTIONS = [
  { value: "", label: "\uC804\uCCB4" },
  { value: "KOSPI", label: "KOSPI" },
  { value: "KOSDAQ", label: "KOSDAQ" },
] as const;

const WATCHLIST_STATE_OPTIONS = [
  { value: 1, label: "\uD65C\uC131" },
  { value: 0, label: "\uBE44\uD65C\uC131" },
  { value: -1, label: "\uC804\uCCB4" },
] as const;

function normalizeKrStockCode(code?: string | null): string {
  const value = (code || "").trim().toUpperCase();
  if (/^A\d{6}$/.test(value)) return value.slice(1);
  return value;
}

function safeMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string") return error;
  return fallback;
}

function formatCollectionPeriod(item: Watchlist): string {
  const start = item.price_start_date || "";
  const end = item.price_end_date || "";
  if (start && end) return `${start} ~ ${end}`;
  return "\uBBF8\uC218\uC9D1";
}

function formatPriceCollectRange(result: StockPriceCollectResult): string {
  const fromDates = result.results.map((item) => item.from_date).filter((value): value is string => Boolean(value));
  const toDates = result.results.map((item) => item.to_date).filter((value): value is string => Boolean(value));
  if (!fromDates.length || !toDates.length) return "";
  return `${fromDates.sort()[0]} ~ ${toDates.sort()[toDates.length - 1]}`;
}

function formatPriceCollectMessage(mode: PriceCollectionMode, priceResult: StockPriceCollectResult, metricsFailedCount: number): string {
  const label = mode === "full" ? "\uC804\uCCB4\uC218\uC9D1" : "\uCD5C\uADFC7\uC77C\uC218\uC9D1";
  const range = formatPriceCollectRange(priceResult);
  const savedText = priceResult.saved_count.toLocaleString("ko-KR");
  const rangeText = range ? `: ${range}, \uC800\uC7A5 ${savedText}\uAC74` : `: \uC800\uC7A5 ${savedText}\uAC74`;
  if (priceResult.failed_count > 0 || metricsFailedCount > 0) {
    return `${label} \uC644\uB8CC${rangeText}. \uC77C\uBD80 \uAC00\uACA9 \uB610\uB294 \uC2DC\uC7A5\uC9C0\uD45C \uAC31\uC2E0\uC5D0 \uC2E4\uD328\uD588\uC2B5\uB2C8\uB2E4.`;
  }
  return `${label} \uC644\uB8CC${rangeText}. \uAD00\uC2EC\uC885\uBAA9 \uAC00\uACA9\u00B7\uAE30\uC220\uC9C0\uD45C\u00B7\uC2DC\uC7A5\uC9C0\uD45C\uAC00 \uAC31\uC2E0\uB418\uC5C8\uC2B5\uB2C8\uB2E4.`;
}

function WatchlistPage() {
  const navigate = useNavigate();
  const listSelectAllRef = useRef<HTMLInputElement | null>(null);
  const [allWatchlistRows, setAllWatchlistRows] = useState<Watchlist[]>([]);
  const [selectedWatchlistStockIds, setSelectedWatchlistStockIds] = useState<number[]>([]);
  const [stockCount, setStockCount] = useState(0);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [watchlistError, setWatchlistError] = useState("");
  const [watchlistMarket, setWatchlistMarket] = useState("");
  const [watchlistState, setWatchlistState] = useState(1);
  const [watchlistKeyword, setWatchlistKeyword] = useState("");
  const [viewMode, setViewMode] = useState<WatchlistViewMode>("theme");
  const [themeNameByStockId, setThemeNameByStockId] = useState<Record<number, string>>({});
  const [themeIdByStockId, setThemeIdByStockId] = useState<Record<number, number>>({});
  const [expandedThemes, setExpandedThemes] = useState<string[]>([]);
  const [themeModalOpen, setThemeModalOpen] = useState(false);
  const [themeModalThemes, setThemeModalThemes] = useState<MarketTheme[]>([]);
  const [themeModalKeyword, setThemeModalKeyword] = useState("");
  const [themeModalSelectedThemeId, setThemeModalSelectedThemeId] = useState<number | null>(null);
  const [themeModalSaving, setThemeModalSaving] = useState(false);
  const [themeModalStock, setThemeModalStock] = useState<Watchlist | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalKeyword, setModalKeyword] = useState("");
  const [modalLoading, setModalLoading] = useState(false);
  const [modalRows, setModalRows] = useState<Stock[]>([]);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [fullRefreshConfirmOpen, setFullRefreshConfirmOpen] = useState(false);
  const [selectedNewsCollectResult, setSelectedNewsCollectResult] = useState<NewsCollectSelectedResponse | null>(null);
  const [selectedDisclosureCollectResult, setSelectedDisclosureCollectResult] = useState<DisclosureCollectSelectedResponse | null>(null);
  const [selectedPriceCollectResult, setSelectedPriceCollectResult] = useState<StockPriceCollectResult | null>(null);
  const [selectedMarketMetricsCollectResult, setSelectedMarketMetricsCollectResult] =
    useState<SelectedMarketMetricsCollectResult | null>(null);

  const fetchAllWatchlistRows = async (): Promise<Watchlist[]> => {
    const pageLimit = 500;
    const rows: Watchlist[] = [];
    for (let offset = 0; offset < 25000; offset += pageLimit) {
      const pageRows = await repositories.watchlist.list({ is_active: undefined, limit: pageLimit, offset });
      rows.push(...pageRows);
      if (pageRows.length < pageLimit) break;
    }
    return rows;
  };

  const fetchStockCount = async (): Promise<number> => {
    const pageLimit = 500;
    let count = 0;
    for (let offset = 0; offset < 25000; offset += pageLimit) {
      const pageRows = await repositories.stocks.list({ is_active: 1, limit: pageLimit, offset });
      count += pageRows.length;
      if (pageRows.length < pageLimit) break;
    }
    return count;
  };

  const loadThemeMap = async (): Promise<ThemeMapPayload> => {
    const themes: MarketTheme[] = await repositories.marketThemes.list({ is_active: 1, theme_level: "THEME", limit: 200, offset: 0 });
    const entries = await Promise.all(
      themes.map(async (theme) => {
        const stocks = await repositories.marketThemes.listThemeStocks(theme.id);
        return stocks
          .filter((x) => x.is_active === 1)
          .map((x) => ({ stockId: x.stock_id, themeId: theme.id, themeName: theme.theme_name, isPrimary: x.is_primary === 1 }));
      }),
    );
    const picked: Record<number, { themeId: number; themeName: string; isPrimary: boolean }> = {};
    entries.flat().forEach((x) => {
      if (!picked[x.stockId] || (x.isPrimary && !picked[x.stockId].isPrimary)) {
        picked[x.stockId] = { themeId: x.themeId, themeName: x.themeName, isPrimary: x.isPrimary };
      }
    });
    const nameMap: Record<number, string> = {};
    const idMap: Record<number, number> = {};
    Object.entries(picked).forEach(([stockId, item]) => {
      nameMap[Number(stockId)] = item.themeName;
      idMap[Number(stockId)] = item.themeId;
    });
    return { nameMap, idMap };
  };

  const refreshAll = async () => {
    setLoadingWatchlist(true);
    setWatchlistError("");
    try {
      const [watchlistRows, count, themeMap] = await Promise.all([fetchAllWatchlistRows(), fetchStockCount(), loadThemeMap()]);
      setAllWatchlistRows(watchlistRows);
      setStockCount(count);
      setThemeNameByStockId(themeMap.nameMap);
      setThemeIdByStockId(themeMap.idMap);
    } catch (error) {
      setWatchlistError(safeMessage(error, "관심종목 데이터를 불러오는 중 오류가 발생했습니다."));
      setAllWatchlistRows([]);
    } finally {
      setLoadingWatchlist(false);
    }
  };

  useEffect(() => {
    void refreshAll();
  }, []);

  const watchlistByStockId = useMemo(() => {
    const map: Record<number, Watchlist> = {};
    allWatchlistRows.forEach((x) => {
      map[x.stock_id] = x;
    });
    return map;
  }, [allWatchlistRows]);

  const watchlistStatusByStockId = useMemo(() => {
    const map: Record<number, WatchlistStatus> = {};
    allWatchlistRows.forEach((x) => {
      map[x.stock_id] = x.is_active === 1 ? "active" : "inactive";
    });
    return map;
  }, [allWatchlistRows]);

  const filteredWatchlist = useMemo(() => {
    const keyword = watchlistKeyword.trim().toLowerCase();
    return allWatchlistRows.filter((x) => {
      if (watchlistMarket && x.market !== watchlistMarket) return false;
      if (watchlistState >= 0 && x.is_active !== watchlistState) return false;
      if (!keyword) return true;
      return x.stock_name.toLowerCase().includes(keyword) || normalizeKrStockCode(x.stock_code).toLowerCase().includes(keyword);
    });
  }, [allWatchlistRows, watchlistKeyword, watchlistMarket, watchlistState]);

  const filteredWatchlistStockIds = useMemo(() => filteredWatchlist.map((row) => row.stock_id), [filteredWatchlist]);
  const selectedFilteredCount = filteredWatchlistStockIds.filter((stockId) => selectedWatchlistStockIds.includes(stockId)).length;
  const allFilteredSelected = filteredWatchlistStockIds.length > 0 && selectedFilteredCount === filteredWatchlistStockIds.length;
  const someFilteredSelected = selectedFilteredCount > 0 && selectedFilteredCount < filteredWatchlistStockIds.length;

  useEffect(() => {
    if (listSelectAllRef.current) listSelectAllRef.current.indeterminate = someFilteredSelected;
  }, [someFilteredSelected]);

  const toggleRowsSelection = (rows: Watchlist[], checked: boolean) => {
    const targetIds = rows.map((row) => row.stock_id);
    setSelectedWatchlistStockIds((prev) => checked ? Array.from(new Set([...prev, ...targetIds])) : prev.filter((id) => !targetIds.includes(id)));
  };
  const themeGroups = useMemo<ThemeGroup[]>(() => {
    const bucket: Record<string, Watchlist[]> = {};
    filteredWatchlist.forEach((x) => {
      const themeName = themeNameByStockId[x.stock_id] || "테마 미지정";
      if (!bucket[themeName]) bucket[themeName] = [];
      bucket[themeName].push(x);
    });
    return Object.entries(bucket)
      .map(([themeName, rows]) => ({
        themeName,
        rows,
        activeCount: rows.filter((x) => x.is_active === 1).length,
        inactiveCount: rows.filter((x) => x.is_active !== 1).length,
      }))
      .sort((a, b) => b.rows.length - a.rows.length || a.themeName.localeCompare(b.themeName));
  }, [filteredWatchlist, themeNameByStockId]);

  useEffect(() => {
    if (expandedThemes.length === 0 && themeGroups.length > 0) {
      setExpandedThemes(themeGroups.map((x) => x.themeName));
    }
  }, [themeGroups, expandedThemes.length]);

  const activeCount = allWatchlistRows.filter((x) => x.is_active === 1).length;
  const inactiveCount = allWatchlistRows.filter((x) => x.is_active !== 1).length;

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionLoading(key);
    setActionError("");
    setActionMessage("");
    setSelectedNewsCollectResult(null);
    setSelectedDisclosureCollectResult(null);
    setSelectedPriceCollectResult(null);
    setSelectedMarketMetricsCollectResult(null);
    try {
      await action();
    } catch (error) {
      setActionError(safeMessage(error, "작업 실행 중 오류가 발생했습니다."));
    } finally {
      setActionLoading("");
    }
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

  const onRefreshSelectedPriceAndMarketMetrics = async (mode: PriceCollectionMode) => {
    if (selectedWatchlistStockIds.length === 0) return;
    const actionKey = mode === "full" ? "refresh-selected-price-market-metrics-full" : "refresh-selected-price-market-metrics-recent";
    await runAction(actionKey, async () => {
      const priceResult = await repositories.stockPrices.collectSelected({
        stock_ids: selectedWatchlistStockIds,
        period_years: 2,
        source: "kiwoom_rest",
        overlap_days: 7,
        force_full_refresh: mode === "full",
      });
      setSelectedPriceCollectResult(priceResult);
      const metricsResult = await repositories.stockPrices.collectSelectedMarketMetrics({
        stock_ids: selectedWatchlistStockIds,
        source: "kiwoom_rest",
      });
      setSelectedMarketMetricsCollectResult(metricsResult);
      setActionMessage(formatPriceCollectMessage(mode, priceResult, metricsResult.failed_count));
      if (mode === "full") setFullRefreshConfirmOpen(false);
    });
  };

  const onToggleWatchlistActive = async (item: Watchlist, nextActive: number) => {
    if (nextActive === 0) {
      const confirmed = window.confirm(
        "선택한 관심종목을 비활성화하시겠습니까?\n\n비활성화해도 기존 뉴스·공시·가격 데이터는 삭제되지 않습니다.\n다시 활성화하면 같은 종목코드 기준으로 기존 이력을 이어서 확인할 수 있습니다.",
      );
      if (!confirmed) return;
    }

    await runAction(`watchlist-${item.id}-${nextActive}`, async () => {
      await repositories.watchlist.update(item.id, { is_active: nextActive });
      await refreshAll();
      setActionMessage(
        nextActive === 0
          ? "관심종목이 비활성화되었습니다. 기존 수집 데이터는 유지됩니다."
          : "관심종목이 활성화되었습니다. 기존 수집 이력을 이어서 사용할 수 있습니다.",
      );
    });
  };

  const runModalSearch = async () => {
    const keyword = modalKeyword.trim();
    if (!keyword) {
      setModalRows([]);
      return;
    }
    setModalLoading(true);
    try {
      setModalRows(await repositories.stocks.list({ keyword, is_active: 1, limit: 80, offset: 0 }));
    } catch (error) {
      setActionError(safeMessage(error, "종목 검색 중 오류가 발생했습니다."));
    } finally {
      setModalLoading(false);
    }
  };

  const onAddFromModal = async (stockId: number) => {
    await runAction(`add-modal-${stockId}`, async () => {
      await repositories.watchlist.create({ stock_id: stockId, status: "관심" });
      await refreshAll();
      setActionMessage("관심종목에 추가되었습니다.");
      void runModalSearch();
    });
  };

  const onReactivateFromModal = async (stockId: number) => {
    const row = watchlistByStockId[stockId];
    if (!row) return;
    await runAction(`reactivate-modal-${stockId}`, async () => {
      await repositories.watchlist.update(row.id, { is_active: 1 });
      await refreshAll();
      setActionMessage("활성 관심종목으로 전환되었습니다. 기존 수집 이력을 이어서 사용할 수 있습니다.");
      void runModalSearch();
    });
  };

  const onFocusInWatchlist = (stock: Stock) => {
    setModalOpen(false);
    setWatchlistState(1);
    setWatchlistKeyword(stock.stock_name);
    setViewMode("theme");
  };

  const toggleStockSelection = (stockId: number, checked: boolean) => {
    setSelectedWatchlistStockIds((prev) => (checked ? Array.from(new Set([...prev, stockId])) : prev.filter((id) => id !== stockId)));
  };

  const onSelectThemeGroup = (group: ThemeGroup, activeOnly: boolean) => {
    const targetIds = group.rows.filter((x) => (activeOnly ? x.is_active === 1 : true)).map((x) => x.stock_id);
    setSelectedWatchlistStockIds((prev) => Array.from(new Set([...prev, ...targetIds])));
  };

  const onOpenThemeModal = async (row: Watchlist) => {
    setThemeModalStock(row);
    setThemeModalKeyword("");
    setThemeModalSelectedThemeId(themeIdByStockId[row.stock_id] || null);
    setThemeModalOpen(true);
    try {
      if (themeModalThemes.length === 0) {
        const themes = await repositories.marketThemes.list({ is_active: 1, theme_level: "THEME", limit: 500, offset: 0 });
        setThemeModalThemes(themes);
      }
    } catch (error) {
      setActionError(safeMessage(error, "테마 목록을 불러오는 중 오류가 발생했습니다."));
    }
  };

  const filteredThemeModalThemes = useMemo(() => {
    const keyword = themeModalKeyword.trim().toLowerCase();
    const selectableThemes = themeModalThemes.filter((x) => x.theme_level !== "THEME_GROUP");
    if (!keyword) return selectableThemes;
    return selectableThemes.filter((x) => x.theme_name.toLowerCase().includes(keyword));
  }, [themeModalKeyword, themeModalThemes]);

  const onSavePrimaryTheme = async () => {
    if (!themeModalStock || !themeModalSelectedThemeId) return;
    setThemeModalSaving(true);
    setActionError("");
    setActionMessage("");
    try {
      const themes = (themeModalThemes.length > 0 ? themeModalThemes : await repositories.marketThemes.list({ is_active: 1, theme_level: "THEME", limit: 500, offset: 0 }))
        .filter((theme) => theme.theme_level !== "THEME_GROUP");
      const stocksByTheme = await Promise.all(
        themes.map(async (theme) => ({ themeId: theme.id, rows: await repositories.marketThemes.listThemeStocks(theme.id) })),
      );
      const stockMappings: MarketThemeStock[] = stocksByTheme
        .flatMap((x) => x.rows)
        .filter((x) => x.stock_id === themeModalStock.stock_id);
      const target = stockMappings.find((x) => x.theme_id === themeModalSelectedThemeId);

      await Promise.all(
        stockMappings
          .filter((x) => x.is_primary === 1 && x.theme_id !== themeModalSelectedThemeId)
          .map((x) => repositories.marketThemes.updateThemeStock(x.mapping_id, { is_primary: false, is_active: 1 })),
      );

      if (target) {
        await repositories.marketThemes.updateThemeStock(target.mapping_id, { is_primary: true, is_active: 1 });
      } else {
        await repositories.marketThemes.createThemeStock(themeModalSelectedThemeId, { stock_id: themeModalStock.stock_id, is_primary: true });
      }
      await refreshAll();
      setThemeModalOpen(false);
      setThemeModalStock(null);
      setActionMessage("테마가 저장되었습니다.");
    } catch (error) {
      setActionError(safeMessage(error, "테마 저장에 실패했습니다."));
    } finally {
      setThemeModalSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="watchlist-top-compact">
        <div className="watchlist-top-main">
          <h1 className="watchlist-top-title">관심 종목</h1>
          <p className="watchlist-top-description">관심 종목을 운영하고, 활성 종목의 뉴스·공시·가격 데이터를 수집합니다.</p>
          <div className="watchlist-top-actions">
            <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
              + 관심종목 등록
            </button>
          </div>
        </div>

        <div className="watchlist-top-stats">
          <div className="watchlist-top-stat-card">
            <p className="watchlist-top-stat-label">전체종목</p>
            <strong className="watchlist-top-stat-value">{stockCount.toLocaleString()}건</strong>
            <p className="watchlist-top-stat-sub">KOSPI/KOSDAQ</p>
          </div>
          <div className="watchlist-top-stat-card watchlist-top-stat-card-wide">
            <p className="watchlist-top-stat-label">관심종목</p>
            <strong className="watchlist-top-stat-value">{allWatchlistRows.length.toLocaleString()}건</strong>
            <p className="watchlist-top-stat-sub">
              활성 {activeCount} · 비활성 {inactiveCount}
            </p>
          </div>
        </div>
      </div>

      <SectionCard title="관심종목 운영 목록">
        <div className="watchlist-card-title-wrap">
          <span className="watchlist-card-title">관심종목 운영 목록</span>
          <span className="hint-icon" title="활성 종목은 뉴스·공시·가격 데이터 수집 대상입니다. 비활성 종목은 수집 대상에서는 제외되지만 기존 수집 데이터는 유지됩니다.">
            ⓘ
          </span>
        </div>
        <form className="watchlist-ops-toolbar" onSubmit={(e) => e.preventDefault()}>
          <select className="select-control" value={watchlistMarket} onChange={(e) => setWatchlistMarket(e.target.value)}>
            {MARKET_OPTIONS.map((x) => (
              <option key={`market-${x.value || "all"}`} value={x.value}>
                {x.label}
              </option>
            ))}
          </select>
          <select className="select-control" value={watchlistState} onChange={(e) => setWatchlistState(Number(e.target.value))}>
            {WATCHLIST_STATE_OPTIONS.map((x) => (
              <option key={`state-${x.value}`} value={x.value}>
                {x.label}
              </option>
            ))}
          </select>
          <input className="input-control" placeholder="종목명 또는 종목코드" value={watchlistKeyword} onChange={(e) => setWatchlistKeyword(e.target.value)} />
          <button type="button" className="btn btn-secondary" onClick={() => setWatchlistKeyword(watchlistKeyword.trim())}>
            조회
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setWatchlistMarket("");
              setWatchlistState(1);
              setWatchlistKeyword("");
              setSelectedWatchlistStockIds([]);
            }}
          >
            초기화
          </button>
        </form>

        <div className="watchlist-view-action-row">
          <div className="watchlist-view-tabs">
            <button type="button" className={`watchlist-view-tab ${viewMode === "list" ? "active" : ""}`} onClick={() => setViewMode("list")}>
              전체 목록
            </button>
            <button type="button" className={`watchlist-view-tab ${viewMode === "theme" ? "active" : ""}`} onClick={() => setViewMode("theme")}>
              테마별 보기
            </button>
            <span className="hint-icon" title="관심종목을 연결된 테마 기준으로 그룹화하여 보여줍니다. 테마가 없는 종목은 ‘테마 미지정’ 그룹에 표시됩니다.">
              ⓘ
            </span>
          </div>

          <div className="watchlist-selection-bar">
            {selectedWatchlistStockIds.length > 0 ? (
              <div className="watchlist-selection-count">선택 {selectedWatchlistStockIds.length}건</div>
            ) : null}
            <div className="watchlist-selection-actions">
              <button className="btn btn-primary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-news"} onClick={() => void onCollectSelectedNews()}>
                뉴스 수집
              </button>
              <button className="btn btn-primary" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "collect-selected-disclosures"} onClick={() => void onCollectSelectedDisclosures()}>
                공시 수집
              </button>
              <button
                className="btn btn-primary"
                title={"\uB9C8\uC9C0\uB9C9 \uC218\uC9D1\uC77C \uAE30\uC900 7\uC77C \uC804\uBD80\uD130 \uC624\uB298\uAE4C\uC9C0 \uB2E4\uC2DC \uC218\uC9D1\uD569\uB2C8\uB2E4. \uAE30\uC874 \uB370\uC774\uD130\uAC00 \uC5C6\uC73C\uBA74 \uCD5C\uCD08\uC218\uC9D1\uC73C\uB85C \uCC98\uB9AC\uB429\uB2C8\uB2E4."}
                disabled={selectedWatchlistStockIds.length === 0 || actionLoading.startsWith("refresh-selected-price-market-metrics")}
                onClick={() => void onRefreshSelectedPriceAndMarketMetrics("recent")}
              >
                {actionLoading === "refresh-selected-price-market-metrics-recent" ? "\uCD5C\uADFC7\uC77C\uC218\uC9D1 \uC911..." : "\uCD5C\uADFC7\uC77C\uC218\uC9D1"}
              </button>
              <button
                className="btn btn-secondary watchlist-full-refresh-button"
                title={"\uAE30\uC874 \uC218\uC9D1 \uAE30\uAC04 \uC804\uCCB4\uB97C \uB2E4\uC2DC \uC694\uCCAD\uD574 upsert\uD569\uB2C8\uB2E4. \uAE30\uC874 \uB370\uC774\uD130\uB294 \uC0AD\uC81C\uB418\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4."}
                disabled={selectedWatchlistStockIds.length === 0 || actionLoading.startsWith("refresh-selected-price-market-metrics")}
                onClick={() => setFullRefreshConfirmOpen(true)}
              >
                {actionLoading === "refresh-selected-price-market-metrics-full" ? "\uC804\uCCB4\uC218\uC9D1 \uC911..." : "\uC804\uCCB4\uC218\uC9D1"}
              </button>
              <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0} onClick={() => navigate("/advisory-packages")}>
                GPT 자료 패키지
              </button>
              <button className="btn btn-secondary" disabled={selectedWatchlistStockIds.length === 0} onClick={() => navigate("/stock-prices")}>
                Data분석 이동
              </button>
            </div>
            <p className="watchlist-collection-help">
              {"\uCD5C\uADFC7\uC77C\uC218\uC9D1\uC740 \uB9C8\uC9C0\uB9C9 \uC218\uC9D1\uC77C \uAE30\uC900 7\uC77C \uC804\uBD80\uD130 \uC624\uB298\uAE4C\uC9C0 \uB2E4\uC2DC \uC218\uC9D1\uD569\uB2C8\uB2E4. \uC804\uCCB4\uC218\uC9D1\uC740 \uAE30\uC874 \uAE30\uAC04 \uC804\uCCB4\uB97C \uB2E4\uC2DC \uC694\uCCAD\uD558\uBA70, \uAE30\uC874 \uB370\uC774\uD130\uB294 \uC0AD\uC81C\uB418\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4."}
            </p>
          </div>

        </div>

        {actionMessage ? <div className="inline-result inline-success">{actionMessage}</div> : null}
        {actionError ? <div className="inline-result inline-error">{actionError}</div> : null}
        {selectedNewsCollectResult ? <div className="inline-result">선택 뉴스 수집 결과 확인 완료</div> : null}
        {selectedDisclosureCollectResult ? <div className="inline-result">선택 공시 수집 결과 확인 완료</div> : null}
        {selectedPriceCollectResult ? <div className="inline-result">선택 가격 수집 결과 확인 완료</div> : null}
        {selectedMarketMetricsCollectResult ? <div className="inline-result">선택 시장지표 수집 결과 확인 완료</div> : null}

        {loadingWatchlist ? <p className="text-sm text-muted">관심종목 목록 로딩 중입니다.</p> : null}
        {watchlistError ? <p className="text-sm text-rose-600">{watchlistError}</p> : null}
        {!loadingWatchlist && !watchlistError && filteredWatchlist.length === 0 ? <EmptyState message="조회된 관심종목이 없습니다." /> : null}

        {!loadingWatchlist && !watchlistError && filteredWatchlist.length > 0 && viewMode === "theme" ? (
          <div className="theme-group-list">
            {themeGroups.map((group) => {
              const expanded = expandedThemes.includes(group.themeName);
              return (
                <div key={group.themeName} className="theme-group-card">
                  <div className="theme-group-header">
                    <button
                      type="button"
                      className="theme-group-toggle"
                      onClick={() => setExpandedThemes((prev) => (prev.includes(group.themeName) ? prev.filter((x) => x !== group.themeName) : [...prev, group.themeName]))}
                    >
                      <strong>{group.themeName}</strong>
                      <span>{group.rows.length}종목 · 활성 {group.activeCount} · 비활성 {group.inactiveCount}</span>
                    </button>
                    <div className="theme-group-actions">
                      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => onSelectThemeGroup(group, false)}>
                        전체 선택
                      </button>
                      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => onSelectThemeGroup(group, true)}>
                        활성만 선택
                      </button>
                    </div>
                  </div>
                  {expanded ? (
                    <div className="table-shell">
                      <table className="data-table compact-table watchlist-table min-w-[760px]">
                        <thead>
                          <tr>
                            <th className="selection-cell"><input className="selection-checkbox" type="checkbox" aria-label="그룹 전체 선택" title="그룹 전체 선택" checked={group.rows.length > 0 && group.rows.every((row) => selectedWatchlistStockIds.includes(row.stock_id))} onChange={(e) => toggleRowsSelection(group.rows, e.target.checked)} /></th>
                            <th>상태</th>
                            <th>종목</th>
                            <th>시장</th>
                            <th>테마</th>
                            <th className="watchlist-period-col">데이터수집기간</th>
                            <th>작업</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.rows.map((row) => {
                            const selected = selectedWatchlistStockIds.includes(row.stock_id);
                            return (
                              <tr key={row.id} className={selected ? "selected-row" : ""}>
                                <td className="selection-cell">
                                  <input className="selection-checkbox" type="checkbox" checked={selected} onChange={(e) => toggleStockSelection(row.stock_id, e.target.checked)} />
                                </td>
                                <td>
                                  <StatusBadge label={row.is_active === 1 ? "활성" : "비활성"} tone={row.is_active === 1 ? "emerald" : "amber"} />
                                </td>
                                <td>
                                  <div className="stock-cell">
                                    <strong>{row.stock_name}</strong>
                                    <span>{normalizeKrStockCode(row.stock_code)}</span>
                                  </div>
                                </td>
                                <td>{row.market || "-"}</td>
                                <td>
                                  <button type="button" className="watchlist-theme-badge" onClick={() => void onOpenThemeModal(row)}>
                                    {themeNameByStockId[row.stock_id] || "테마 미지정"}
                                  </button>
                                </td>
                                <td className="watchlist-period-col">
                                  {formatCollectionPeriod(row) === "미수집" ? <span className="badge badge-slate">미수집</span> : formatCollectionPeriod(row)}
                                </td>
                                <td>
                                  {row.is_active === 1 ? (
                                    <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(row, 0)}>
                                      비활성화
                                    </button>
                                  ) : (
                                    <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(row, 1)}>
                                      활성화
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}

        {!loadingWatchlist && !watchlistError && filteredWatchlist.length > 0 && viewMode === "list" ? (
          <div className="table-shell">
            <table className="data-table compact-table watchlist-table min-w-[760px]">
              <thead>
                <tr>
                  <th className="selection-cell"><input ref={listSelectAllRef} className="selection-checkbox" type="checkbox" aria-label="현재 목록 전체 선택" title="현재 목록 전체 선택" checked={allFilteredSelected} onChange={(e) => toggleRowsSelection(filteredWatchlist, e.target.checked)} /></th>
                  <th>상태</th>
                  <th>종목명/코드</th>
                  <th>시장</th>
                  <th>테마</th>
                  <th className="watchlist-period-col">데이터수집기간</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                {filteredWatchlist.map((row) => {
                  const selected = selectedWatchlistStockIds.includes(row.stock_id);
                  return (
                    <tr key={row.id} className={selected ? "selected-row" : ""}>
                      <td className="selection-cell">
                        <input className="selection-checkbox" type="checkbox" checked={selected} onChange={(e) => toggleStockSelection(row.stock_id, e.target.checked)} />
                      </td>
                      <td>
                        <StatusBadge label={row.is_active === 1 ? "활성" : "비활성"} tone={row.is_active === 1 ? "emerald" : "amber"} />
                      </td>
                      <td>
                        <div className="stock-cell">
                          <strong>{row.stock_name}</strong>
                          <span>{normalizeKrStockCode(row.stock_code)}</span>
                        </div>
                      </td>
                      <td>{row.market || "-"}</td>
                      <td>
                        <button type="button" className="watchlist-theme-badge" onClick={() => void onOpenThemeModal(row)}>
                          {themeNameByStockId[row.stock_id] || "테마 미지정"}
                        </button>
                      </td>
                      <td className="watchlist-period-col">
                        {formatCollectionPeriod(row) === "미수집" ? <span className="badge badge-slate">미수집</span> : formatCollectionPeriod(row)}
                      </td>
                      <td>
                        {row.is_active === 1 ? (
                          <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(row, 0)}>
                            비활성화
                          </button>
                        ) : (
                          <button className="btn btn-secondary btn-table-sm" onClick={() => void onToggleWatchlistActive(row, 1)}>
                            활성화
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>

      {fullRefreshConfirmOpen ? (
        <div className="modal-backdrop" onClick={() => setFullRefreshConfirmOpen(false)}>
          <div className="modal-card watchlist-refresh-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>{"\uC804\uCCB4\uC218\uC9D1\uC744 \uC2E4\uD589\uD558\uC2DC\uACA0\uC2B5\uB2C8\uAE4C?"}</h3>
              <button className="btn btn-secondary btn-table-sm" type="button" onClick={() => setFullRefreshConfirmOpen(false)}>
                {"\uCDE8\uC18C"}
              </button>
            </div>
            <div className="watchlist-refresh-confirm-body">
              <p>{"\uC804\uCCB4\uC218\uC9D1\uC740 \uAD00\uC2EC\uC885\uBAA9\uC758 \uAE30\uC874 \uC218\uC9D1 \uAE30\uAC04 \uB370\uC774\uD130\uB97C \uB2E4\uC2DC \uC694\uCCAD\uD574 upsert\uD569\uB2C8\uB2E4."}</p>
              <p>{"\uAE30\uC874 \uB370\uC774\uD130\uB294 \uC0AD\uC81C\uB418\uC9C0 \uC54A\uC9C0\uB9CC, \uC218\uC9D1 \uC2DC\uAC04\uC774 \uC624\uB798 \uAC78\uB9B4 \uC218 \uC788\uC2B5\uB2C8\uB2E4."}</p>
              <p className="watchlist-refresh-confirm-note">{"\uC77C\uBC18\uC801\uC778 \uAC31\uC2E0\uC740 \uCD5C\uADFC7\uC77C\uC218\uC9D1\uC744 \uC0AC\uC6A9\uD558\uC138\uC694."}</p>
            </div>
            <div className="watchlist-refresh-confirm-actions">
              <button className="btn btn-secondary" type="button" disabled={actionLoading === "refresh-selected-price-market-metrics-full"} onClick={() => setFullRefreshConfirmOpen(false)}>
                {"\uCDE8\uC18C"}
              </button>
              <button className="btn btn-danger" type="button" disabled={selectedWatchlistStockIds.length === 0 || actionLoading === "refresh-selected-price-market-metrics-full"} onClick={() => void onRefreshSelectedPriceAndMarketMetrics("full")}>
                {actionLoading === "refresh-selected-price-market-metrics-full" ? "\uC804\uCCB4\uC218\uC9D1 \uC911..." : "\uC804\uCCB4\uC218\uC9D1 \uC2E4\uD589"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {modalOpen ? (
        <div className="modal-backdrop" onClick={() => setModalOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>
                관심종목 등록
                <span className="hint-icon" title="종목명 또는 종목코드로 전체종목을 검색해 관심종목에 추가합니다. 이미 등록된 종목은 중복 추가되지 않습니다.">
                  ⓘ
                </span>
              </h3>
              <button className="btn btn-secondary btn-table-sm" onClick={() => setModalOpen(false)}>
                닫기
              </button>
            </div>
            <form
              className="watchlist-modal-search"
              onSubmit={(e) => {
                e.preventDefault();
                void runModalSearch();
              }}
            >
              <input className="input-control" placeholder="종목명 또는 종목코드 입력" value={modalKeyword} onChange={(e) => setModalKeyword(e.target.value)} />
              <button type="submit" className="btn btn-primary">
                검색
              </button>
            </form>
            {modalLoading ? <p className="text-sm text-muted">검색 중입니다.</p> : null}
            {!modalLoading && modalRows.length === 0 ? <EmptyState message="검색 결과가 없습니다." /> : null}
            {!modalLoading && modalRows.length > 0 ? (
              <div className="table-shell">
                <table className="data-table compact-table min-w-[760px]">
                  <thead>
                    <tr>
                      <th>종목명</th>
                      <th>종목코드</th>
                      <th>시장</th>
                      <th>등록상태/액션</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modalRows.map((row) => {
                      const status = watchlistStatusByStockId[row.id] || "not_registered";
                      return (
                        <tr key={row.id}>
                          <td className="cell-title">{row.stock_name}</td>
                          <td>{normalizeKrStockCode(row.stock_code)}</td>
                          <td>{row.market || "-"}</td>
                          <td>
                            {status === "not_registered" ? (
                              <button className="btn btn-primary btn-table-sm" onClick={() => void onAddFromModal(row.id)}>
                                추가
                              </button>
                            ) : null}
                            {status === "active" ? (
                              <div className="watchlist-modal-status-actions">
                                <StatusBadge label="이미 활성" tone="blue" />
                                <button className="btn btn-secondary btn-table-sm" onClick={() => onFocusInWatchlist(row)}>
                                  관심목록에서 보기
                                </button>
                              </div>
                            ) : null}
                            {status === "inactive" ? (
                              <button className="btn btn-secondary btn-table-sm" onClick={() => void onReactivateFromModal(row.id)}>
                                재활성화
                              </button>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {themeModalOpen && themeModalStock ? (
        <div className="modal-backdrop" onClick={() => setThemeModalOpen(false)}>
          <div className="modal-card watchlist-theme-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>
                테마 선택
                <span
                  className="hint-icon"
                  title="선택한 종목의 대표 테마를 지정합니다. 지정 후 테마별 보기에서 해당 테마 그룹에 표시됩니다."
                >
                  i
                </span>
              </h3>
              <button className="btn btn-secondary btn-table-sm" onClick={() => setThemeModalOpen(false)}>
                닫기
              </button>
            </div>
            <div className="watchlist-theme-modal-stock">
              <strong>{themeModalStock.stock_name}</strong>
              <span>
                {normalizeKrStockCode(themeModalStock.stock_code)} · {themeModalStock.market || "-"}
              </span>
            </div>
            <div className="watchlist-theme-modal-search">
              <input className="input-control" placeholder="테마명 검색" value={themeModalKeyword} onChange={(e) => setThemeModalKeyword(e.target.value)} />
            </div>
            <div className="watchlist-theme-modal-list">
              {filteredThemeModalThemes.map((theme) => (
                <label key={theme.id} className="watchlist-theme-modal-item">
                  <input
                    type="radio"
                    name="watchlist-theme-select"
                    checked={themeModalSelectedThemeId === theme.id}
                    onChange={() => setThemeModalSelectedThemeId(theme.id)}
                  />
                  <span>{theme.theme_name}</span>
                </label>
              ))}
              {filteredThemeModalThemes.length === 0 ? <EmptyState message="검색 결과가 없습니다." /> : null}
            </div>
            <div className="watchlist-theme-modal-actions">
              <button className="btn btn-secondary" onClick={() => setThemeModalOpen(false)}>
                취소
              </button>
              <button className="btn btn-primary" disabled={!themeModalSelectedThemeId || themeModalSaving} onClick={() => void onSavePrimaryTheme()}>
                {themeModalSaving ? "저장 중..." : "저장"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default WatchlistPage;
