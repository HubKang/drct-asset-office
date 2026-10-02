import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";

import NaverStockChartModal, { type NaverStockChartModalData } from "@/components/common/NaverStockChartModal";
import { ThemeLinkedStockChart } from "@/components/marketThemes/MarketThemeDetailDrawer";
import type { RealtimeThemeStocksResponse } from "@/types/marketTheme";
import { buildDaumIntradayChartUrl, formatDaumChartTimestamp } from "@/utils/daumChart";
import { createNaverChartSidcode, normalizeNaverStockCode } from "@/utils/naverChart";

type ZoomedChart = NaverStockChartModalData;

const formatRate = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const rateClass = (value: number | null) => value == null ? "is-empty" : value > 0 ? "is-positive" : value < 0 ? "is-negative" : "is-neutral";

function RealtimeIntradayChart({ stockCode, stockName, timestamp, onOpen }: {
  stockCode: string;
  stockName: string;
  timestamp: string;
  onOpen: (chart: ZoomedChart) => void;
}) {
  const [hasError, setHasError] = useState(false);
  const url = buildDaumIntradayChartUrl(stockCode, timestamp);
  useEffect(() => setHasError(false), [url]);
  if (!url || hasError) return <div className="realtime-theme-stock-chart-empty">분봉 없음</div>;
  const alt = `${stockName || stockCode} 오늘 분봉 차트`;
  return <button type="button" className="realtime-theme-intraday-chart-button" aria-label={`${alt} 크게 보기`} onClick={() => onOpen({ url, alt, title: alt, stockCode })}>
    <img src={url} alt={alt} loading="lazy" decoding="async" onError={() => setHasError(true)} />
  </button>;
}

export default function RealtimeThemeDetailDrawer({ open, data, loading, error, metric, metricLabel, metricValue, metricRank, onMetricChange, onClose, onRetry }: {
  open: boolean;
  data: RealtimeThemeStocksResponse | null;
  loading: boolean;
  error: string | null;
  metric: "average" | "strength";
  metricLabel: string;
  metricValue: number | null;
  metricRank: number | null;
  onMetricChange: (metric: "average" | "strength") => void;
  onClose: () => void;
  onRetry: () => void;
}) {
  const [zoomedChart, setZoomedChart] = useState<ZoomedChart | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const chartSidcode = useMemo(() => {
    const snapshotKey = String(data?.snapshot_at ?? "").replace(/\D/g, "");
    return Number(snapshotKey) || createNaverChartSidcode();
  }, [data?.snapshot_at]);
  const intradayChartTimestamp = useMemo(() => formatDaumChartTimestamp(), [data?.snapshot_at]);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (zoomedChart) setZoomedChart(null);
      else {
        onClose();
        window.setTimeout(() => previousFocusRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, open, zoomedChart]);

  if (!open) return null;
  return <>
    <div className="realtime-theme-drawer-backdrop" onClick={onClose}>
      <aside className="realtime-theme-drawer" role="dialog" aria-modal="true" aria-labelledby="realtime-theme-drawer-title" onClick={(event) => event.stopPropagation()}>
        <header className="realtime-theme-drawer-header">
          <div className="realtime-theme-drawer-heading">
            <div className="realtime-theme-drawer-title-row"><div><span>실시간 테마 상세</span><h2 id="realtime-theme-drawer-title">{data?.theme_name || "테마 상세"}</h2></div><div className="realtime-theme-drawer-metric-switch" aria-label="테마 계산 기준"><button type="button" className={metric === "average" ? "is-active" : ""} aria-pressed={metric === "average"} onClick={() => onMetricChange("average")}>단순평균</button><button type="button" className={metric === "strength" ? "is-active" : ""} aria-pressed={metric === "strength"} onClick={() => onMetricChange("strength")}>테마강도</button></div></div>
            {data ? <section className="realtime-theme-drawer-summary" aria-label="테마 실시간 요약">
              <div><span>{metricLabel}</span><strong className={rateClass(metricValue)}>{formatRate(metricValue)}</strong></div>
              <div><span>순위</span><strong>{metricRank == null ? "-" : `${metricRank}위`}</strong></div>
              <div><span>연결</span><strong>{data.linked_stock_count}개</strong></div>
              <div><span>유효 / 연결</span><strong>{data.valid_stock_count} / {data.linked_stock_count}</strong></div>
              <p>Snapshot {data.snapshot_at?.slice(11) || "미수집"}</p>
            </section> : null}
          </div>
          <button ref={closeButtonRef} type="button" aria-label="상세 닫기" onClick={onClose}><X size={20} /></button>
        </header>
        <div className="realtime-theme-drawer-body">
          {loading ? <div className="realtime-theme-drawer-state"><span className="realtime-theme-drawer-spinner" />실시간 Snapshot을 불러오는 중...</div> : null}
          {error && !loading ? <div className="realtime-theme-drawer-state is-error"><span>{error}</span><button type="button" className="btn btn-secondary" onClick={onRetry}>다시 시도</button></div> : null}
          {data && !loading && !error ? <div className="realtime-theme-stock-table-wrap">
            <div className="realtime-theme-stock-table" role="table" aria-label={`${data.theme_name} 연결 종목`}>
              <div className="realtime-theme-stock-row is-header" role="row">
                <span role="columnheader">종목</span><span role="columnheader">실시간등락률</span><span role="columnheader">분봉</span><span role="columnheader">일봉</span><span role="columnheader">주봉</span><span role="columnheader">월봉</span>
              </div>
              {data.stocks.map((stock) => {
                const stockCode = normalizeNaverStockCode(stock.stock_code);
                return <div className="realtime-theme-stock-row" role="row" key={stock.stock_id}>
                  <div className="realtime-theme-stock-name" role="cell"><strong>{stock.stock_name || stock.stock_code}</strong><span>{stockCode || stock.stock_code}</span>{stock.memo?.trim() ? <small title={stock.memo}>{stock.memo}</small> : null}</div>
                  <strong className={`realtime-theme-stock-rate ${rateClass(stock.change_rate)}`} role="cell">{formatRate(stock.change_rate)}</strong>
                  <div className="realtime-theme-stock-chart" role="cell"><RealtimeIntradayChart stockCode={stockCode} stockName={stock.stock_name} timestamp={intradayChartTimestamp} onOpen={setZoomedChart} /></div>
                  {(["day", "week", "month"] as const).map((period, index) => <div className="realtime-theme-stock-chart" role="cell" key={period}><ThemeLinkedStockChart stockCode={stockCode} stockName={stock.stock_name} period={period} label={["일봉", "주봉", "월봉"][index]} sidcode={chartSidcode} onOpen={setZoomedChart} variant="detail" /></div>)}
                </div>;
              })}
            </div>
            {!data.stocks.length ? <p className="realtime-theme-drawer-empty">연결 종목이 없습니다.</p> : null}
          </div> : null}
        </div>
      </aside>
    </div>
    {zoomedChart ? <NaverStockChartModal chart={zoomedChart} onClose={() => setZoomedChart(null)} /> : null}
  </>;
}
