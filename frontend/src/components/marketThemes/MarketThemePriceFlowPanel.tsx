import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { repositories } from "@/services";
import type {
  MarketThemePriceFlowChartResponse,
  MarketThemePriceFlowPeriod,
  MarketThemePriceFlowSeriesItem,
  MarketThemePriceFlowUnit,
  MarketThemePriceFlowView,
} from "@/types/marketTheme";

type SeriesKey = "price" | "individual" | "foreign" | "institution" | "program";

const SERIES: Array<{ key: SeriesKey; label: string; color: string; dashed?: boolean }> = [
  { key: "price", label: "주가", color: "#111827" },
  { key: "individual", label: "개인", color: "#2563eb" },
  { key: "foreign", label: "외국인", color: "#dc2626" },
  { key: "institution", label: "기관", color: "#f59e0b" },
  { key: "program", label: "프로그램", color: "#16a34a", dashed: true },
];

const VALUE_FIELDS: Record<SeriesKey, keyof MarketThemePriceFlowSeriesItem> = {
  price: "price_return_pct",
  individual: "individual_cumulative",
  foreign: "foreign_cumulative",
  institution: "institution_cumulative",
  program: "program_cumulative",
};

const NORMALIZED_FIELDS: Record<SeriesKey, keyof MarketThemePriceFlowSeriesItem> = {
  price: "normalized_price",
  individual: "normalized_individual",
  foreign: "normalized_foreign",
  institution: "normalized_institution",
  program: "normalized_program",
};

const DAILY_FIELDS: Record<Exclude<SeriesKey, "price">, keyof MarketThemePriceFlowSeriesItem> = {
  individual: "individual_daily",
  foreign: "foreign_daily",
  institution: "institution_daily",
  program: "program_daily",
};

function finiteValue(value: unknown): number | null {
  const number = Number(value);
  return value == null || !Number.isFinite(number) ? null : number;
}

function domain(values: Array<number | null>, includeZero = false): [number, number] {
  const valid = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (includeZero) valid.push(0);
  if (!valid.length) return [-1, 1];
  let min = Math.min(...valid);
  let max = Math.max(...valid);
  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1);
    min -= pad;
    max += pad;
  } else {
    const pad = (max - min) * 0.08;
    min -= pad;
    max += pad;
  }
  return [min, max];
}

function pathSegments(values: Array<number | null>, x: (index: number) => number, y: (value: number) => number): string[] {
  const segments: string[] = [];
  let points: string[] = [];
  values.forEach((value, index) => {
    if (value == null) {
      if (points.length) segments.push(points.join(" "));
      points = [];
      return;
    }
    points.push(`${points.length ? "L" : "M"}${x(index).toFixed(2)},${y(value).toFixed(2)}`);
  });
  if (points.length) segments.push(points.join(" "));
  return segments;
}

function formatPct(value: number | null): string {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatFlow(value: number | null, unit: MarketThemePriceFlowUnit): string {
  if (value == null) return "-";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  if (unit === "AMOUNT") {
    if (absolute >= 100_000_000) return `${sign}${(absolute / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`;
    if (absolute >= 10_000) return `${sign}${(absolute / 10_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만원`;
    return `${sign}${absolute.toLocaleString("ko-KR")}원`;
  }
  return `${sign}${absolute.toLocaleString("ko-KR")}주`;
}

function streakLabel(streak: number): string {
  if (!streak) return "연속 흐름 없음";
  return `${Math.abs(streak)}일 연속 ${streak > 0 ? "순매수" : "순매도"}`;
}

const STATUS_LABELS: Record<MarketThemePriceFlowChartResponse["data_quality"]["status"], string> = {
  ENOUGH: "충분",
  PERIOD_SHORT: "기간 부족",
  PARTIAL: "일부 누락",
  LATEST_MISMATCH: "최신일 불일치",
  EMPTY: "데이터 없음",
};

function Segmented<T extends string>({ values, value, onChange }: { values: Array<{ value: T; label: string }>; value: T; onChange: (value: T) => void }) {
  return (
    <div className="price-flow-segmented">
      {values.map((item) => (
        <button key={item.value} type="button" className={value === item.value ? "is-active" : ""} onClick={() => onChange(item.value)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default function MarketThemePriceFlowPanel({ stockId, themeId, focusDate }: { stockId: number; themeId: number; focusDate?: string | null }) {
  const [period, setPeriod] = useState<MarketThemePriceFlowPeriod>("3M");
  const [unit, setUnit] = useState<MarketThemePriceFlowUnit>("QUANTITY");
  const [view, setView] = useState<MarketThemePriceFlowView>("ACTUAL");
  const [data, setData] = useState<MarketThemePriceFlowChartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryKey, setRetryKey] = useState(0);
  const [hidden, setHidden] = useState<Set<SeriesKey>>(() => new Set());
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    repositories.marketThemes.getStockPriceFlowChart(stockId, { period, unit, view, theme_id: themeId })
      .then((response) => {
        if (!active) return;
        setData(response);
        setSelectedIndex(null);
        setHoveredIndex(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setData(null);
        setError(reason instanceof Error ? reason.message : "가격·수급 차트를 불러오지 못했습니다.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [stockId, themeId, focusDate, period, unit, view, retryKey]);

  const eventByDate = useMemo(() => new Map((data?.events ?? []).map((event) => [event.event_date, event])), [data]);
  const activeIndex = hoveredIndex ?? selectedIndex;
  const selectedRow = selectedIndex == null ? null : data?.series[selectedIndex] ?? null;
  const selectedEvent = selectedRow ? eventByDate.get(selectedRow.trade_date) ?? null : null;

  const chart = useMemo(() => {
    const rows = data?.series ?? [];
    const width = 920;
    const height = 390;
    const plot = { left: 64, top: 28, right: 70, bottom: 52 };
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const x = (index: number) => plot.left + (rows.length <= 1 ? plotWidth / 2 : index / (rows.length - 1) * plotWidth);
    const valueOf = (row: MarketThemePriceFlowSeriesItem, key: SeriesKey) => finiteValue(row[view === "NORMALIZED" ? NORMALIZED_FIELDS[key] : VALUE_FIELDS[key]]);
    const priceDomain: [number, number] = view === "NORMALIZED" ? [-100, 100] : domain(rows.map((row) => valueOf(row, "price")), true);
    const flowDomain: [number, number] = view === "NORMALIZED"
      ? [-100, 100]
      : domain(rows.flatMap((row) => SERIES.slice(1).map((series) => valueOf(row, series.key))), true);
    const yFor = (key: SeriesKey, value: number) => {
      const [min, max] = key === "price" ? priceDomain : flowDomain;
      return plot.top + (max - value) / (max - min) * plotHeight;
    };
    return { rows, width, height, plot, plotWidth, plotHeight, x, valueOf, priceDomain, flowDomain, yFor };
  }, [data, view]);

  const toggleSeries = (key: SeriesKey) => setHidden((before) => {
    const next = new Set(before);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  const selectFromPointer = (clientX: number, element: SVGSVGElement, hoverOnly = false) => {
    if (!chart.rows.length) return;
    const rect = element.getBoundingClientRect();
    const svgX = (clientX - rect.left) / rect.width * chart.width;
    const ratio = Math.max(0, Math.min(1, (svgX - chart.plot.left) / chart.plotWidth));
    const index = Math.round(ratio * (chart.rows.length - 1));
    if (hoverOnly) {
      setHoveredIndex(index);
    } else {
      setSelectedIndex((before) => before === index ? null : index);
    }
  };

  return (
    <section className="market-theme-price-flow-section">
      <div className="market-theme-stock-section-heading price-flow-heading">
        <div>
          <h4 className="market-theme-stock-section-title">투자주체별 누적 수급</h4>
          <p>저장된 거래일 기준 가격과 개인·외국인·기관·프로그램 순매수를 비교합니다.</p>
        </div>
        {data ? <span className={`price-flow-quality is-${data.data_quality.status.toLowerCase()}`}>{STATUS_LABELS[data.data_quality.status]}</span> : null}
      </div>

      <div className="price-flow-controls">
        <div><span>기간</span><Segmented value={period} onChange={setPeriod} values={[{ value: "1M", label: "1M" }, { value: "3M", label: "3M" }, { value: "6M", label: "6M" }]} /></div>
        <div><span>보기</span><Segmented value={view} onChange={setView} values={[{ value: "ACTUAL", label: "실제 누적" }, { value: "NORMALIZED", label: "패턴 비교" }]} /></div>
        <div><span>단위</span><Segmented value={unit} onChange={setUnit} values={[{ value: "QUANTITY", label: "수량" }, { value: "AMOUNT", label: "금액" }]} /></div>
      </div>

      {loading ? <div className="price-flow-loading">가격·수급 데이터를 계산하는 중입니다.</div> : null}
      {!loading && error ? (
        <div className="price-flow-empty is-error"><strong>차트를 불러오지 못했습니다.</strong><span>{error}</span><button type="button" onClick={() => setRetryKey((value) => value + 1)}><RefreshCw size={13} /> 다시 시도</button></div>
      ) : null}
      {!loading && !error && data?.data_quality.status === "EMPTY" ? (
        <div className="price-flow-empty"><strong>수집된 투자주체별 수급 데이터가 없습니다.</strong><span>시장 테마 관리의 테마 등락률·수급 갱신을 실행하면 활성 연결 종목의 가격과 수급 데이터가 수집됩니다.</span></div>
      ) : null}

      {!loading && !error && data && data.series.length > 0 ? (
        <>
          <div className="price-flow-data-status">
            <span>기간 {data.period.start_date} ~ {data.period.end_date}</span>
            <span>가격 {data.latest_dates.price ?? "-"}</span>
            <span>투자자 {data.latest_dates.investor ?? "-"}</span>
            <span>프로그램 {data.latest_dates.program ?? "-"}</span>
            <span>비교 기준 {data.latest_dates.common ?? "-"}</span>
            <strong>유효 {data.data_quality.valid_days}/{data.period.requested_trading_days}일</strong>
          </div>

          <div className="price-flow-summary-grid">
            <div><span>기간 수익률</span><strong>{formatPct(data.summary.price_return_pct)}</strong><small>{data.period.actual_trading_days}거래일</small></div>
            {SERIES.slice(1).map((series) => {
              const cumulative = finiteValue(data.summary[`${series.key}_cumulative` as keyof typeof data.summary]);
              const positive = Number(data.summary[`${series.key}_positive_days` as keyof typeof data.summary]);
              const streak = Number(data.summary[`${series.key}_streak` as keyof typeof data.summary]);
              return <div key={series.key}><span>{series.label} 누적</span><strong style={{ color: series.color }}>{formatFlow(cumulative, unit)}</strong><small>{positive}/{data.period.actual_trading_days}일 순매수 · {streakLabel(streak)}</small></div>;
            })}
          </div>

          {view === "NORMALIZED" ? <p className="price-flow-normalized-note">패턴 비교는 각 선의 방향과 전환 시점을 비교하기 위해 기간 내 최대 절댓값을 -100~+100으로 독립 정규화한 값입니다. 실제 규모는 요약 카드에서 확인하세요.</p> : null}

          <div className="price-flow-legend">
            {SERIES.map((series) => <button type="button" key={series.key} className={hidden.has(series.key) ? "is-hidden" : ""} onClick={() => toggleSeries(series.key)}><i style={{ borderColor: series.color, borderStyle: series.dashed ? "dashed" : "solid" }} />{series.label}</button>)}
          </div>

          <div className="price-flow-chart-wrap">
            <svg
              className="price-flow-chart"
              viewBox={`0 0 ${chart.width} ${chart.height}`}
              role="img"
              aria-label="주가와 투자주체별 누적 수급 통합 차트"
              onMouseMove={(event) => selectFromPointer(event.clientX, event.currentTarget, true)}
              onMouseLeave={() => setHoveredIndex(null)}
              onClick={(event) => selectFromPointer(event.clientX, event.currentTarget)}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => <line key={ratio} x1={chart.plot.left} x2={chart.plot.left + chart.plotWidth} y1={chart.plot.top + ratio * chart.plotHeight} y2={chart.plot.top + ratio * chart.plotHeight} className={ratio === 0.5 && view === "NORMALIZED" ? "price-flow-zero-line" : "price-flow-grid-line"} />)}
              {view === "ACTUAL" ? <line x1={chart.plot.left} x2={chart.plot.left + chart.plotWidth} y1={chart.yFor("individual", 0)} y2={chart.yFor("individual", 0)} className="price-flow-zero-line" /> : null}
              {[0, Math.floor((chart.rows.length - 1) / 2), chart.rows.length - 1].map((index) => <text key={index} x={chart.x(index)} y={chart.height - 18} textAnchor={index === 0 ? "start" : index === chart.rows.length - 1 ? "end" : "middle"} className="price-flow-axis-label">{chart.rows[index]?.trade_date.slice(5)}</text>)}
              <text x={chart.plot.left} y={15} className="price-flow-axis-title">{view === "NORMALIZED" ? "정규화 지수" : "주가 수익률(%)"}</text>
              <text x={chart.plot.left + chart.plotWidth} y={15} textAnchor="end" className="price-flow-axis-title">{view === "NORMALIZED" ? "-100 ~ +100" : unit === "QUANTITY" ? "누적 순매수(주)" : "누적 순매수(원)"}</text>
              {data.events.map((event) => {
                const index = chart.rows.findIndex((row) => row.trade_date === event.event_date);
                if (index < 0) return null;
                const eventIndex = index;
                return <g key={event.event_date} className={`price-flow-event ${event.is_current_theme ? "is-current" : ""}`} onClick={(mouseEvent) => { mouseEvent.stopPropagation(); setSelectedIndex((before) => before === eventIndex ? null : eventIndex); }}><line x1={chart.x(index)} x2={chart.x(index)} y1={chart.plot.top} y2={chart.plot.top + chart.plotHeight} /><circle cx={chart.x(index)} cy={chart.plot.top + 8} r={event.event_count > 1 ? 8 : 6} /><text x={chart.x(index)} y={chart.plot.top + 11} textAnchor="middle">{event.event_count}</text><title>{`${event.event_date} · 수급 기록 ${event.event_count}건`}</title></g>;
              })}
              {SERIES.map((series) => {
                if (hidden.has(series.key)) return null;
                const values = chart.rows.map((row) => chart.valueOf(row, series.key));
                return <g key={series.key}>{pathSegments(values, chart.x, (value) => chart.yFor(series.key, value)).map((path, index) => <path key={index} d={path} fill="none" stroke={series.color} strokeWidth={series.key === "price" ? 3 : 2.2} strokeDasharray={series.dashed ? "7 5" : undefined} strokeLinecap="round" strokeLinejoin="round" />)}</g>;
              })}
              {activeIndex != null ? <line x1={chart.x(activeIndex)} x2={chart.x(activeIndex)} y1={chart.plot.top} y2={chart.plot.top + chart.plotHeight} className="price-flow-crosshair" /> : null}
            </svg>
            {selectedRow && selectedIndex != null ? (
              <div className="price-flow-tooltip" style={{ left: `${Math.min(78, Math.max(8, chart.x(selectedIndex) / chart.width * 100))}%` }}>
                <strong>{selectedRow.trade_date}</strong>
                <span>종가 {selectedRow.close_price?.toLocaleString("ko-KR") ?? "-"}원 · 일간 {formatPct(selectedRow.daily_return_pct)} · 기간 {formatPct(selectedRow.price_return_pct)}</span>
                {SERIES.slice(1).map((series) => <span key={series.key} style={{ color: series.color }}>{series.label} {formatFlow(finiteValue(selectedRow[DAILY_FIELDS[series.key as Exclude<SeriesKey, "price">]]), unit)} / 누적 {formatFlow(finiteValue(selectedRow[VALUE_FIELDS[series.key]]), unit)}</span>)}
              </div>
            ) : null}
          </div>

          {selectedRow ? (
            <div className="price-flow-selected-detail">
              <div><strong>{selectedRow.trade_date}</strong><span>종가 {selectedRow.close_price?.toLocaleString("ko-KR") ?? "-"}원</span><span>일간 {formatPct(selectedRow.daily_return_pct)}</span><span>기간 {formatPct(selectedRow.price_return_pct)}</span></div>
              {selectedEvent ? <div className="price-flow-event-detail"><strong>수급 기록 {selectedEvent.event_count}건</strong>{selectedEvent.items.map((item, index) => <p key={`${item.theme_id}-${index}`} className={item.is_current_theme ? "is-current" : ""}><span>{item.theme_name ?? "연결 테마 없음"}{item.is_current_theme ? " · 현재 테마" : ""}</span>{item.memo ? <em>{item.memo}</em> : null}</p>)}</div> : <span className="price-flow-no-event">이 날짜의 수급 기록·종목 메모가 없습니다.</span>}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
