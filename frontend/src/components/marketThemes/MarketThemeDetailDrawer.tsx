import { useEffect, useMemo, useRef, useState } from "react";
import { Info } from "lucide-react";
import { StockFlowCompactCard, ThemeFlowOverview, type FlowActor } from "@/components/marketThemes/FlowSummaryCards";
import MarketThemeFlowChartPanel from "@/components/marketThemes/MarketThemeFlowChartPanel";
import MarketThemePriceFlowModal from "@/components/marketThemes/MarketThemePriceFlowModal";
import { repositories } from "@/services";
import type { MarketThemeFlowTrendActor, MarketThemeLatestReturnDetail } from "@/types/marketTheme";
import { buildNaverStockCandleChartUrl, createNaverChartSidcode, normalizeNaverStockCode, type NaverStockCandlePeriod } from "@/utils/naverChart";

export type MarketThemeDetailFlowContext = { actor: MarketThemeFlowTrendActor } | null;
type ThemeStockSort = "default" | "name" | "memo";
type ZoomedChart = { url: string; alt: string; title?: string };
const detailCache = new Map<string, MarketThemeLatestReturnDetail>();

const fmtPct = (value: number | null | undefined) => value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
const fmtEok = (value: number | null | undefined) => value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
const returnToneClass = (value: number | null | undefined) => value == null || Number.isNaN(Number(value)) ? "theme-return-empty" : Number(value) > 0 ? "theme-return-positive" : Number(value) < 0 ? "theme-return-negative" : "theme-return-neutral";

export function ThemeLinkedStockChart({ stockCode, stockName, period, label, sidcode, onOpen, variant = "table" }: {
  stockCode: string; stockName: string; period: NaverStockCandlePeriod; label: string; sidcode: number;
  onOpen: (chart: ZoomedChart) => void; variant?: "table" | "detail";
}) {
  const [hasError, setHasError] = useState(false);
  useEffect(() => setHasError(false), [period, sidcode, stockCode]);
  if (!stockCode || hasError) return <div className={`theme-linked-stock-chart-fallback${variant === "detail" ? " theme-detail-daily-chart-fallback" : ""}`}>{hasError ? "차트 불러오기 실패" : "차트 없음"}</div>;
  const url = buildNaverStockCandleChartUrl(stockCode, period, sidcode);
  const alt = `${stockName || stockCode} ${label} 차트`;
  return <button type="button" className={`theme-linked-stock-chart-button${variant === "detail" ? " theme-detail-daily-chart-button" : ""}`} aria-label={`${stockName || stockCode} ${label} 차트 크게 보기`} onClick={(event) => { event.stopPropagation(); onOpen({ url, alt, title: alt }); }}>
    <img src={url} alt={alt} className={`theme-linked-stock-chart${variant === "detail" ? " theme-detail-daily-chart-image" : ""}`} loading="lazy" onError={() => setHasError(true)} />
  </button>;
}

export default function MarketThemeDetailDrawer({ open, themeId, dataDate, flowContext = null, onClose }: {
  open: boolean; themeId: number | null; dataDate?: string | null; flowContext?: MarketThemeDetailFlowContext; onClose: () => void;
}) {
  const [detail, setDetail] = useState<MarketThemeLatestReturnDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stockSort, setStockSort] = useState<ThemeStockSort>("memo");
  const [zoomedChart, setZoomedChart] = useState<ZoomedChart | null>(null);
  const [stockFlowModal, setStockFlowModal] = useState<{ stockId: number; stockName: string; themeId: number; focusDate: string | null } | null>(null);
  const [themeFlowModal, setThemeFlowModal] = useState<{ themeId: number; themeName: string; focusDate: string | null; actor: FlowActor | null } | null>(null);
  const requestRef = useRef(0);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const drawerRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const chartSidcode = useMemo(() => createNaverChartSidcode(), [themeId]);
  const cacheKey = themeId ? `${themeId}:${dataDate || "latest"}` : "";

  const load = async (useCache = true) => {
    if (!themeId) return;
    const requestId = ++requestRef.current;
    const cached = useCache ? detailCache.get(cacheKey) : null;
    if (cached) { setDetail(cached); setError(""); setLoading(false); return; }
    setLoading(true); setError(""); setDetail(null);
    try {
      const result = dataDate ? await repositories.marketThemes.getDailyReturn(themeId, dataDate) : await repositories.marketThemes.getLatestReturn(themeId);
      if (requestId !== requestRef.current) return;
      detailCache.set(cacheKey, result); setDetail(result);
    } catch (reason) {
      if (requestId === requestRef.current) setError(reason instanceof Error && reason.message.trim() ? reason.message : "테마 상세 정보를 불러오지 못했습니다.");
    } finally { if (requestId === requestRef.current) setLoading(false); }
  };

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    setStockSort("memo"); setZoomedChart(null); setStockFlowModal(null); setThemeFlowModal(null);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    if (!open || !themeId) return;
    void load();
    return () => { requestRef.current += 1; };
  }, [cacheKey, open, themeId]);

  const close = () => {
    setZoomedChart(null); setStockFlowModal(null); setThemeFlowModal(null); onClose();
    const target = previousFocusRef.current;
    window.setTimeout(() => target?.focus(), 0);
  };
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (zoomedChart) setZoomedChart(null);
        else if (stockFlowModal) setStockFlowModal(null);
        else if (themeFlowModal) setThemeFlowModal(null);
        else close();
        return;
      }
      if (event.key !== "Tab" || zoomedChart || stockFlowModal || themeFlowModal) return;
      const focusable = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? []).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKeyDown); return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, stockFlowModal, themeFlowModal, zoomedChart]);

  const stocks = useMemo(() => {
    const rows = [...(detail?.stocks ?? [])];
    if (stockSort === "default") return rows;
    return rows.sort((a, b) => stockSort === "name"
      ? a.stock_name.localeCompare(b.stock_name, "ko-KR") || a.stock_id - b.stock_id
      : Number(Boolean(b.stock_memo?.trim())) - Number(Boolean(a.stock_memo?.trim())) || Number(b.trading_value_100m ?? -Infinity) - Number(a.trading_value_100m ?? -Infinity) || a.stock_name.localeCompare(b.stock_name, "ko-KR"));
  }, [detail, stockSort]);
  const highlightedActors = flowContext ? flowContext.actor === "FOREIGN_INSTITUTION" ? ["foreign", "institution"] : flowContext.actor === "FOREIGN" ? ["foreign"] : flowContext.actor === "INSTITUTION" ? ["institution"] : flowContext.actor === "INDIVIDUAL" ? ["individual"] : ["program"] : [];
  if (!open) return null;

  return <>
    <div className="theme-return-drawer-backdrop" onClick={close}>
      <aside ref={drawerRef} className="theme-return-drawer" role="dialog" aria-modal="true" aria-labelledby="shared-theme-detail-title" onClick={(event) => event.stopPropagation()}>
        <div className="theme-return-drawer-header"><div><h3 id="shared-theme-detail-title">테마 상세</h3><p>{detail?.theme_name ?? "테마 정보를 불러오는 중입니다."}</p></div><button ref={closeButtonRef} type="button" className="btn btn-secondary btn-table-sm" onClick={close}>닫기</button></div>
        <div className="theme-return-drawer-body">
          {loading ? <div className="theme-detail-drawer-skeleton" aria-label="테마 상세 조회 중"><i /><i /><i /></div> : null}
          {error ? <div className="theme-detail-drawer-error"><p>{error}</p><button type="button" className="btn btn-secondary" onClick={() => void load(false)}>다시 시도</button></div> : null}
          {!loading && !error && detail ? <div className="theme-return-detail-stack">
            <div className="theme-return-detail-title-block"><strong>{detail.theme_name}</strong><span>{detail.theme_group_name || "미지정 테마그룹"}</span></div>
            {detail.return_date ? <>
              <div className="theme-return-kpi-grid">
                <div><span>테마등락률</span><strong className={returnToneClass(detail.avg_change_rate)}>{fmtPct(detail.avg_change_rate)}</strong></div><div><span>연결 종목</span><strong>{detail.stock_count}개</strong></div><div><span>거래대금(억)</span><strong>{fmtEok(detail.total_trading_value_100m)}</strong></div><div><span>상승</span><strong className="theme-return-positive">{detail.rising_stock_count}개</strong></div><div><span>하락</span><strong className="theme-return-negative">{detail.falling_stock_count}개</strong></div><div><span>보합</span><strong className="theme-return-neutral">{detail.flat_stock_count}개</strong></div>
              </div>
              <div className="theme-return-meta"><span>기준일: {detail.return_date}</span><span>최종 갱신: {detail.snapshot_at || "-"}</span>{detail.failed_stock_count > 0 ? <span>조회 실패: {detail.failed_stock_count}개</span> : null}</div>
              {detail.flow_summary ? <ThemeFlowOverview summary={detail.flow_summary} highlightedActors={highlightedActors as FlowActor[]} onActorClick={(actor) => { setZoomedChart(null); setThemeFlowModal({ themeId: detail.theme_id, themeName: detail.theme_name, focusDate: detail.return_date, actor }); }} /> : null}
              {detail.stocks.length ? <><div className="theme-detail-stock-sortbar"><label><span>종목 정렬</span><select className="select-control" value={stockSort} onChange={(event) => setStockSort(event.target.value as ThemeStockSort)}><option value="memo">메모+거래대금</option><option value="name">종목명</option><option value="default">기존순</option></select></label></div>
                <div className="theme-detail-stock-list" role="table" aria-label={`${detail.theme_name} 연결 종목`}><div className="theme-detail-stock-header" role="row"><span role="columnheader">종목명</span><span role="columnheader">거래대금(억)</span><span role="columnheader">등락률(%)</span><span role="columnheader">개외기 수급</span><span role="columnheader" title="네이버에서 제공하는 현재 기준 일봉 차트입니다." className="theme-detail-daily-heading">일봉 <Info size={13} aria-hidden="true" /></span><span role="columnheader" title="네이버에서 제공하는 현재 기준 주봉 차트입니다." className="theme-detail-daily-heading">주봉 <Info size={13} aria-hidden="true" /></span></div>
                  {stocks.map((stock) => { const stockCode = normalizeNaverStockCode(stock.stock_code); return <div className="theme-detail-stock-row" role="row" key={`${stock.stock_id}-${stock.stock_code}`}><div className="stock-cell" role="cell"><strong>{stock.stock_name || stock.stock_code || "-"}</strong>{stock.stock_memo?.trim() ? <small className="theme-detail-stock-memo" title={stock.stock_memo}>{stock.stock_memo}</small> : null}{stock.stock_code ? <span>{stockCode || stock.stock_code}</span> : null}{stock.data_status !== "success" ? <small className="theme-return-fail-text">조회 실패</small> : null}</div><span className="theme-detail-stock-number" role="cell">{fmtEok(stock.trading_value_100m)}</span><span className={`theme-detail-stock-number ${returnToneClass(stock.change_rate)}`} role="cell">{fmtPct(stock.change_rate)}</span><div role="cell"><StockFlowCompactCard summary={stock.flow_summary} baseDate={detail.return_date} onClick={() => { setZoomedChart(null); setStockFlowModal({ stockId: stock.stock_id, stockName: stock.stock_name || stock.stock_code || "종목", themeId: detail.theme_id, focusDate: detail.return_date }); }} /></div><div className="theme-detail-daily-chart-cell" role="cell"><ThemeLinkedStockChart stockCode={stockCode} stockName={stock.stock_name} period="day" label="일봉" sidcode={chartSidcode} onOpen={setZoomedChart} variant="detail" /></div><div className="theme-detail-daily-chart-cell" role="cell"><ThemeLinkedStockChart stockCode={stockCode} stockName={stock.stock_name} period="week" label="주봉" sidcode={chartSidcode} onOpen={setZoomedChart} variant="detail" /></div></div>; })}
                </div></> : <p className="selected-empty-message">이 테마에 연결된 종목이 없습니다.</p>}
            </> : detail.stock_count > 0 ? <p className="selected-empty-message">아직 갱신된 테마등락률 데이터가 없습니다.</p> : <p className="selected-empty-message">이 테마에 연결된 종목이 없습니다.</p>}
          </div> : null}
        </div>
      </aside>
    </div>
    {zoomedChart ? <div className="theme-linked-stock-chart-modal" onClick={() => setZoomedChart(null)}><div className="theme-linked-stock-chart-modal-panel" onClick={(event) => event.stopPropagation()}><div className="theme-linked-stock-chart-modal-header"><h3>{zoomedChart.title || zoomedChart.alt}</h3><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setZoomedChart(null)}>닫기</button></div><img src={zoomedChart.url} alt={zoomedChart.alt} className="theme-linked-stock-chart-modal-image theme-linked-stock-chart-modal-image-clickable" onClick={() => setZoomedChart(null)} /></div></div> : null}
    {stockFlowModal ? <MarketThemePriceFlowModal stockId={stockFlowModal.stockId} stockName={stockFlowModal.stockName} themeId={stockFlowModal.themeId} focusDate={stockFlowModal.focusDate} onClose={() => setStockFlowModal(null)} /> : null}
    {themeFlowModal ? <div className="market-flow-modal-backdrop" onClick={() => setThemeFlowModal(null)}><section className="market-flow-modal" role="dialog" aria-modal="true" aria-label={`${themeFlowModal.themeName} 테마 가격·수급 추이`} onClick={(event) => event.stopPropagation()}><header className="market-flow-modal-header"><div><h3>{themeFlowModal.themeName}</h3><p>테마 가격·수급 추이</p></div><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setThemeFlowModal(null)}>닫기</button></header><div className="market-flow-modal-body"><MarketThemeFlowChartPanel themeId={themeFlowModal.themeId} focusDate={themeFlowModal.focusDate} initialActor={themeFlowModal.actor} /></div></section></div> : null}
  </>;
}
