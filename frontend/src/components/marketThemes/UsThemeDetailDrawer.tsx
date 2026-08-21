import { useEffect, useRef, useState } from "react";
import { Info, X } from "lucide-react";
import { repositories } from "@/services";
import type { UsStockCharts, UsThemeReturnDetail, UsThemeStockRole } from "@/types/usMarketTheme";

type ZoomedChart = { url: string; title: string };
type DetailStock = UsThemeReturnDetail["stocks"][number];

const chartCache = new Map<number, Promise<UsStockCharts>>();
const ROLE_HINTS: Record<UsThemeStockRole, string> = {
  LEADER: "대표 주도 종목",
  CORE: "핵심 종목",
  RELATED: "관련 종목",
  ETF: "테마 ETF · 테마강도 계산 제외",
};

const pct = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const tone = (value: number | null | undefined) => value == null || value === 0 ? "" : value > 0 ? "value-up" : "value-down";
const shortDate = (value: string | null | undefined) => value ? `${value.slice(5, 7)}.${value.slice(8, 10)}` : "-";
const price = (value: number | null | undefined) => value == null ? "-" : `$${value.toLocaleString("en-US", { maximumFractionDigits: 4 })}`;

function loadCharts(stockId: number) {
  let request = chartCache.get(stockId);
  if (!request) {
    request = repositories.usMarketThemes.charts(stockId);
    chartCache.set(stockId, request);
    request.then((result) => { if (!result.available) chartCache.delete(stockId); }).catch(() => chartCache.delete(stockId));
  }
  return request;
}

function UsThemeStockCharts({ stock, onOpen }: { stock: DetailStock; onOpen: (chart: ZoomedChart) => void }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [requested, setRequested] = useState(false);
  const [charts, setCharts] = useState<UsStockCharts | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setRequested(false); setCharts(null); setFailed(false);
    if (!stock.naver_code) return;
    const element = rootRef.current;
    if (!element || typeof IntersectionObserver === "undefined") { setRequested(true); return; }
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      setRequested(true); observer.disconnect();
    }, { rootMargin: "160px 0px" });
    observer.observe(element);
    return () => observer.disconnect();
  }, [stock.naver_code, stock.us_stock_id]);

  useEffect(() => {
    if (!requested || !stock.naver_code) return;
    let active = true;
    loadCharts(stock.us_stock_id).then((result) => { if (active) setCharts(result); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [requested, stock.naver_code, stock.us_stock_id]);

  return <div ref={rootRef} className="us-theme-detail-chart-grid">
    {(["day", "week", "month"] as const).map((period) => {
      const label = period === "day" ? "일봉" : period === "week" ? "주봉" : "월봉";
      const url = charts?.[period];
      const fallback = !stock.naver_code ? "차트없음" : failed ? "조회불가" : !requested ? "차트 준비" : !charts ? "조회 중" : "차트없음";
      return <section key={period} className="us-theme-detail-chart-panel">
        <strong>{label}</strong>
        {url ? <button type="button" className="theme-linked-stock-chart-button" aria-label={`${stock.symbol} ${label} 크게 보기`} onClick={() => onOpen({ url, title: `${stock.symbol} ${label}` })}>
          <img src={url} alt={`${stock.symbol} ${label}`} className="theme-linked-stock-chart" loading="lazy" decoding="async" />
        </button> : <div className="theme-linked-stock-chart-fallback">{fallback}</div>}
      </section>;
    })}
  </div>;
}

export default function UsThemeDetailDrawer({ open, themeId, tradeDate, onClose }: {
  open: boolean;
  themeId: number | null;
  tradeDate?: string | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<UsThemeReturnDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [zoomed, setZoomed] = useState<ZoomedChart | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const drawerRef = useRef<HTMLElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const requestRef = useRef(0);

  const load = async () => {
    if (!themeId) return;
    const requestId = ++requestRef.current;
    setLoading(true); setError(""); setDetail(null);
    try {
      const result = await repositories.usMarketThemes.detail(themeId, tradeDate);
      if (requestId === requestRef.current) setDetail(result);
    } catch (reason) {
      if (requestId === requestRef.current) setError(reason instanceof Error && reason.message.trim() ? reason.message : "테마 상세 정보를 불러오지 못했습니다.");
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    if (!open || !themeId) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    setZoomed(null);
    void load();
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => {
      requestRef.current += 1;
      document.body.style.overflow = previousOverflow;
    };
  }, [open, themeId, tradeDate]);

  const close = () => {
    setZoomed(null); onClose();
    const target = previousFocusRef.current;
    window.setTimeout(() => target?.focus(), 0);
  };

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { if (zoomed) setZoomed(null); else close(); return; }
      if (event.key !== "Tab" || zoomed) return;
      const focusable = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])') ?? []).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, zoomed]);

  if (!open) return null;
  const duplicateGroupName = detail?.theme_group_name.trim().toLowerCase() === detail?.theme_name.trim().toLowerCase();
  return <>
    <div className="theme-return-drawer-backdrop us-theme-detail-backdrop" onMouseDown={close}>
      <aside ref={drawerRef} className="theme-return-drawer us-theme-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="us-theme-detail-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="theme-return-drawer-header us-theme-detail-header">
          <div><h3 id="us-theme-detail-title">{detail?.theme_name ?? "테마 상세"}</h3><p>{detail ? `${duplicateGroupName ? "" : `${detail.theme_group_name} · `}미국 US` : "테마 정보를 불러오는 중입니다."}</p></div>
          <button ref={closeButtonRef} type="button" className="icon-button" onClick={close} aria-label="테마 상세 닫기"><X size={19} /></button>
        </header>
        <div className="theme-return-drawer-body us-theme-detail-body">
          {loading ? <div className="theme-detail-drawer-skeleton" aria-label="테마 상세 정보를 불러오는 중"><i /><i /><i /></div> : null}
          {error ? <div className="theme-detail-drawer-error"><p>테마 상세 정보를 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={() => void load()}>다시 시도</button></div> : null}
          {!loading && !error && detail ? <div className="us-theme-detail-stack">
            {detail.description ? <p className="us-theme-detail-description">{detail.description}</p> : null}
            <div className="us-theme-detail-summary">
              <article><span>기준일</span><strong>{shortDate(detail.trade_date)}</strong></article>
              <article><span>단순등락률</span><strong className={tone(detail.simple_return)}>{pct(detail.simple_return)}</strong></article>
              <article><span>테마강도</span><strong className={tone(detail.theme_strength)}>{pct(detail.theme_strength)}</strong></article>
              <article><span>상승확산</span><strong>{detail.aggregate ? `${detail.up_count}/${detail.valid_stock_count} · ${detail.breadth_ratio == null ? "-" : `${(detail.breadth_ratio * 100).toFixed(0)}%`}` : "-"}</strong></article>
              <article><span>연결 종목</span><strong>{detail.linked_stock_count}개</strong></article>
            </div>
            <div className="us-theme-detail-section-heading"><div><h4>구성 종목</h4><span>{detail.trade_date ? `${detail.trade_date} 기준 가격·등락률` : "가격 집계 데이터 없음"}</span></div><small title="종목 등락률은 Drawer 기준일 값이며, 네이버 차트 이미지는 현재 최신 차트입니다."><Info size={13} /> 차트는 현재 최신 기준입니다.</small></div>
            {detail.stocks.length ? <div className="us-theme-detail-stock-list">
              {detail.stocks.map((stock) => <article key={stock.us_stock_id} className="us-theme-detail-stock-card">
                <header className="us-theme-detail-stock-header">
                  <div className="us-theme-detail-stock-primary">
                    <strong className="us-theme-detail-stock-name">{stock.symbol} · {stock.name_ko || stock.name || "-"}</strong>
                    <i aria-hidden="true" />
                    <strong className={`us-theme-detail-stock-return ${tone(stock.daily_return)}`} title={stock.daily_return == null ? "해당 기준일 가격 데이터가 없습니다." : undefined}>{pct(stock.daily_return)}</strong>
                    <i aria-hidden="true" />
                    <span className="us-theme-detail-stock-close">종가 {price(stock.close_price)}</span>
                  </div>
                  <div className="us-theme-detail-stock-meta">
                    {stock.name && stock.name !== stock.name_ko ? <span className="us-theme-detail-stock-english" title={stock.name}>{stock.name}</span> : null}
                    <span>{stock.exchange}</span>
                    <span className="us-theme-role-badge" title={ROLE_HINTS[stock.role]}>{stock.role}</span>
                    {stock.is_representative ? <span className="us-theme-representative-badge">대표</span> : null}
                  </div>
                </header>
                <UsThemeStockCharts stock={stock} onOpen={setZoomed} />
              </article>)}
            </div> : <p className="selected-empty-message">활성 연결 종목이 없습니다.</p>}
          </div> : null}
        </div>
      </aside>
    </div>
    {zoomed ? <div className="theme-linked-stock-chart-modal" onMouseDown={() => setZoomed(null)}><div className="theme-linked-stock-chart-modal-panel" onMouseDown={(event) => event.stopPropagation()}><div className="theme-linked-stock-chart-modal-header"><h3>{zoomed.title}</h3><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setZoomed(null)}>닫기</button></div><img src={zoomed.url} alt={zoomed.title} className="theme-linked-stock-chart-modal-image theme-linked-stock-chart-modal-image-clickable" onClick={() => setZoomed(null)} /></div></div> : null}
  </>;
}
