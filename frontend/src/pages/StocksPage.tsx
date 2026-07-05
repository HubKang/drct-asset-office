import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import {
  buildNaverStockCandleChartUrl,
  createNaverChartSidcode,
  normalizeNaverStockCode,
  type NaverStockCandlePeriod,
} from "@/utils/naverChart";
import type { Stock } from "@/types/stock";
import type { StockSyncResponse } from "@/types/stockSync";

type MarketFilter = "ALL" | "KOSPI" | "KOSDAQ" | "INACTIVE";
type SecurityFilter = "ALL" | "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other";
type SyncMarket = "ALL" | "KOSPI" | "KOSDAQ";
type SecurityType = "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other";

const SECURITY_TYPES: SecurityType[] = ["common_stock", "preferred_stock", "etf", "etn", "spac", "reit", "other"];
const SECURITY_LABELS: Record<SecurityType, string> = {
  common_stock: "보통주",
  preferred_stock: "우선주",
  etf: "ETF",
  etn: "ETN",
  spac: "스팩",
  reit: "리츠",
  other: "기타",
};

const createEmptySecurityTypeMap = <T,>(value: T): Record<SecurityType, T> => ({
  common_stock: value,
  preferred_stock: value,
  etf: value,
  etn: value,
  spac: value,
  reit: value,
  other: value,
});

function formatSyncedAt(value: string | null | undefined): string {
  if (!value) return "-";
  const normalized = value.replace("T", " ");
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized;
}

function StockChartImage({
  stockCode,
  stockName,
  period,
  label,
  sidcode,
  onOpen,
}: {
  stockCode: string;
  stockName: string;
  period: NaverStockCandlePeriod;
  label: string;
  sidcode: number;
  onOpen: (chart: { url: string; alt: string }) => void;
}) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setHasError(false);
  }, [period, sidcode, stockCode]);

  if (!stockCode || hasError) {
    return <div className="stock-management-chart-fallback">차트 없음</div>;
  }

  const url = buildNaverStockCandleChartUrl(stockCode, period, sidcode);
  const alt = `${stockName || stockCode} ${label} 차트`;

  return (
    <button
      type="button"
      className="stock-management-chart-button"
      onClick={() => onOpen({ url, alt })}
    >
      <img
        src={url}
        alt={alt}
        className="stock-management-chart-image"
        loading="lazy"
        onError={() => setHasError(true)}
      />
    </button>
  );
}

function StocksPage() {
  const [items, setItems] = useState<Stock[]>([]);
  const [keyword, setKeyword] = useState("");
  const [marketFilter, setMarketFilter] = useState<MarketFilter>("ALL");
  const [securityFilter, setSecurityFilter] = useState<SecurityFilter>("ALL");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [syncMarket, setSyncMarket] = useState<SyncMarket>("ALL");
  const [includeSecurityTypes, setIncludeSecurityTypes] = useState<SecurityType[]>(["common_stock"]);
  const [typeCounts, setTypeCounts] = useState<Record<SecurityType, number>>(() => createEmptySecurityTypeMap(0));
  const [typeLatestSyncedAt, setTypeLatestSyncedAt] = useState<Record<SecurityType, string | null>>(() => createEmptySecurityTypeMap<string | null>(null));
  const [chartSidcode, setChartSidcode] = useState(createNaverChartSidcode());
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string } | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResult, setSyncResult] = useState<StockSyncResponse | null>(null);
  const [syncError, setSyncError] = useState("");
  const [showRawLog, setShowRawLog] = useState(false);

  const buildListParams = (nextOffset = offset) => {
    const params: {
      keyword?: string;
      market?: string;
      is_active?: number;
      security_type?: string;
      limit: number;
      offset: number;
    } = { limit, offset: nextOffset };
    if (keyword.trim()) params.keyword = keyword.trim();
    if (marketFilter === "KOSPI" || marketFilter === "KOSDAQ") params.market = marketFilter;
    params.is_active = marketFilter === "INACTIVE" ? 0 : 1;
    if (securityFilter !== "ALL") params.security_type = securityFilter;
    return params;
  };

  const load = async (nextOffset = offset) => {
    const data = await repositories.stocks.list(buildListParams(nextOffset));
    setItems(data);
    setChartSidcode(createNaverChartSidcode());
  };

  const loadTypeCounts = async () => {
    const next = createEmptySecurityTypeMap(0);
    const latest = createEmptySecurityTypeMap<string | null>(null);
    await Promise.all(
      SECURITY_TYPES.map(async (type) => {
        let count = 0;
        for (let pageOffset = 0; pageOffset < 50000; pageOffset += 500) {
          const rows = await repositories.stocks.list({ is_active: 1, security_type: type, limit: 500, offset: pageOffset });
          count += rows.length;
          rows.forEach((row) => {
            if (row.last_synced_at && (!latest[type] || row.last_synced_at > latest[type])) {
              latest[type] = row.last_synced_at;
            }
          });
          if (rows.length < 500) break;
        }
        next[type] = count;
      }),
    );
    setTypeCounts(next);
    setTypeLatestSyncedAt(latest);
  };

  useEffect(() => {
    void load();
  }, [offset]);

  useEffect(() => {
    void loadTypeCounts();
  }, []);

  const activeCount = useMemo(() => items.filter((i) => i.is_active === 1).length, [items]);

  const onSearch = async () => {
    setOffset(0);
    await load(0);
  };

  const onResetSearch = async () => {
    setKeyword("");
    setMarketFilter("ALL");
    setSecurityFilter("ALL");
    setOffset(0);
    await load(0);
  };

  const onToggleActive = async (stockId: number, nextActive: number) => {
    await repositories.stocks.update(stockId, { is_active: nextActive });
    await load();
    await loadTypeCounts();
  };

  const toggleSecurityType = (type: SecurityType) => {
    setIncludeSecurityTypes((prev) => (prev.includes(type) ? prev.filter((x) => x !== type) : [...prev, type]));
  };

  const runSync = async (preview: boolean) => {
    if (includeSecurityTypes.length === 0) {
      setSyncError("종목 유형을 1개 이상 선택해주세요.");
      return;
    }
    if (!preview) {
      const ok = window.confirm(
        "최신 KRX 목록으로 종목 마스터를 재구축하시겠습니까?\n\n현재 종목 마스터 목록은 재구성되며, 선택한 종목유형만 최신 목록으로 다시 반영됩니다.\n기존 수집 데이터는 삭제되지 않습니다.",
      );
      if (!ok) return;
    }

    setSyncLoading(true);
    setSyncError("");
    setSyncResult(null);
    setShowRawLog(false);
    try {
      const markets = syncMarket === "ALL" ? ["KOSPI", "KOSDAQ"] : [syncMarket];
      const result = await repositories.stocks.syncStocks({
        markets,
        dry_run: preview,
        deactivate_missing: false,
        include_security_types: includeSecurityTypes,
        mode: "rebuild",
      });
      setSyncResult(result);
      await load();
      await loadTypeCounts();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "종목 갱신 중 오류가 발생했습니다.");
    } finally {
      setSyncLoading(false);
    }
  };

  const canPrev = offset > 0;
  const canNext = items.length >= limit;
  const renderSecurityType = (value: string | null) => SECURITY_LABELS[(value as SecurityType) || "other"] || "기타";

  return (
    <div className="space-y-4">
      <PageHeader
        title="종목 관리"
        description="KRX 최신 목록을 기준으로 DrCT에셋 종목 마스터를 재구축합니다."
        action={<StatusBadge label={`활성 ${activeCount} / 이번 페이지 ${items.length}`} tone="blue" />}
      />

      <SectionCard title="최신 KRX 목록 재구축">
        <div className="watchlist-card-title-wrap">
          <span className="watchlist-card-title">동기화 옵션</span>
          <span className="hint-icon" title="선택한 종목유형 기준으로 기존 종목 마스터를 비활성화한 뒤 최신 KRX 목록으로 다시 반영합니다.">
            i
          </span>
        </div>

        <div className="stock-sync-market-row">
          <select className="select-control" value={syncMarket} onChange={(e) => setSyncMarket(e.target.value as SyncMarket)}>
            <option value="ALL">전체 시장</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
          </select>
          <div className="stock-sync-market-actions">
            <button className="btn btn-secondary" onClick={() => void runSync(true)} disabled={syncLoading}>
              미리보기
            </button>
            <button className="btn btn-primary" onClick={() => void runSync(false)} disabled={syncLoading}>
              선택 타입 최신 목록으로 갱신
            </button>
            {syncLoading ? (
              <span className="inline-flex items-center gap-1 text-sm text-slate-600">
                <Loader2 size={14} className="animate-spin" />
                처리 중...
              </span>
            ) : null}
          </div>
        </div>

        <div className="stock-type-card-grid">
          {SECURITY_TYPES.map((type) => {
            const selected = includeSecurityTypes.includes(type);
            return (
              <button key={type} type="button" className={`stock-type-card ${selected ? "selected" : ""}`} onClick={() => toggleSecurityType(type)}>
                <strong>{SECURITY_LABELS[type]}</strong>
                <span>{typeCounts[type].toLocaleString()}건</span>
                <span>마지막 동기화 {formatSyncedAt(typeLatestSyncedAt[type])}</span>
                <em>{selected ? "선택" : "미선택"}</em>
              </button>
            );
          })}
        </div>

        {syncError ? <div className="inline-result inline-error">{syncError}</div> : null}
        {syncResult ? (
          <>
            <div className="stock-sync-summary-grid">
              <div className="stock-sync-summary-card"><span>원본 수집</span><strong>{syncResult.raw_fetched_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>대상 추출</span><strong>{syncResult.eligible_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>기존 비활성화</span><strong>{syncResult.deleted_existing_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>신규 등록</span><strong>{syncResult.inserted_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>재활성/갱신</span><strong>{(syncResult.reactivated_count + syncResult.updated_count).toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>오류</span><strong>{syncResult.error_count.toLocaleString()}</strong></div>
            </div>
            {syncResult.dry_run ? <div className="inline-result">미리보기 결과입니다. DB에는 반영되지 않았습니다.</div> : null}
            <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setShowRawLog((v) => !v)}>
              {showRawLog ? "상세 로그 숨기기" : "상세 로그 보기"}
            </button>
            {showRawLog ? <div className="inline-result">{syncResult.message}</div> : null}
          </>
        ) : null}
      </SectionCard>

      <SectionCard title="검색">
        <form
          className="stock-search-row"
          onSubmit={(e) => {
            e.preventDefault();
            void onSearch();
          }}
        >
          <select className="select-control" value={marketFilter} onChange={(e) => setMarketFilter(e.target.value as MarketFilter)}>
            <option value="ALL">전체</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
            <option value="INACTIVE">비활성</option>
          </select>
          <select className="select-control" value={securityFilter} onChange={(e) => setSecurityFilter(e.target.value as SecurityFilter)}>
            <option value="ALL">종목유형</option>
            {SECURITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {SECURITY_LABELS[t]}
              </option>
            ))}
          </select>
          <div><input className="input-control" placeholder="종목코드 또는 종목명" value={keyword} onChange={(e) => setKeyword(e.target.value)} /></div>
          <button type="submit" className="btn btn-primary stock-search-btn">검색</button>
          <button type="button" className="btn btn-secondary stock-search-btn" onClick={onResetSearch}>초기화</button>
        </form>
      </SectionCard>

      <SectionCard title="종목 목록">
        {items.length === 0 ? (
          <EmptyState message="조회된 종목이 없습니다." />
        ) : (
          <>
            <div className="table-shell stock-management-table-shell">
              <table className="data-table compact-table stock-management-table">
                <colgroup>
                  <col className="stock-management-col-code" />
                  <col className="stock-management-col-name" />
                  <col className="stock-management-col-market" />
                  <col className="stock-management-col-type" />
                  <col className="stock-management-col-active" />
                  <col className="stock-management-col-chart" />
                  <col className="stock-management-col-chart" />
                  <col className="stock-management-col-chart" />
                  <col className="stock-management-col-actions" />
                </colgroup>
                <thead>
                  <tr><th>종목코드</th><th>종목명</th><th>시장</th><th>종목유형</th><th>활성</th><th>일봉</th><th>주봉</th><th>월봉</th><th>작업</th></tr>
                </thead>
                <tbody>
                  {items.map((s) => {
                    const stockCode = normalizeNaverStockCode(s.stock_code);
                    const codeTitle = stockCode && stockCode !== s.stock_code ? s.stock_code : undefined;
                    return (
                      <tr key={s.id}>
                        <td className="cell-nowrap font-medium text-slate-800" title={codeTitle}>{stockCode || s.stock_code}</td>
                        <td className="cell-nowrap truncate stock-management-name-cell" title={s.stock_name}>{s.stock_name}</td>
                        <td className="cell-nowrap">{s.market || "-"}</td>
                        <td className="cell-nowrap">{renderSecurityType(s.security_type)}</td>
                        <td>{s.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                        <td><StockChartImage stockCode={stockCode} stockName={s.stock_name} period="day" label="일봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td><StockChartImage stockCode={stockCode} stockName={s.stock_name} period="week" label="주봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td><StockChartImage stockCode={stockCode} stockName={s.stock_name} period="month" label="월봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td>
                          <div className="stock-management-actions">
                            <button className={`btn ${s.is_active === 1 ? "btn-danger" : "btn-secondary"} btn-table-sm stock-management-action-button`} onClick={() => onToggleActive(s.id, s.is_active === 1 ? 0 : 1)}>
                              {s.is_active === 1 ? "비활성" : "활성"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="pagination-bar">
              <div className="pagination-info">현재 위치: {offset + 1} ~ {offset + items.length} / 조회 건수: {items.length}건</div>
              <div className="pagination-actions">
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => Math.max(0, prev - limit))} disabled={!canPrev}>이전</button>
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => prev + limit)} disabled={!canNext}>다음</button>
              </div>
            </div>
          </>
        )}
      </SectionCard>
      {zoomedChart ? (
        <div className="stock-management-chart-modal" onClick={() => setZoomedChart(null)}>
          <img
            src={zoomedChart.url}
            alt={zoomedChart.alt}
            className="stock-management-chart-modal-image"
            onClick={(event) => {
              event.stopPropagation();
              setZoomedChart(null);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export default StocksPage;
