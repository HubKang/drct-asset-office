import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Info, RefreshCw } from "lucide-react";
import { repositories } from "@/services";
import {
  buildBreadthIndexSeries, buildCumulativeSeries, buildStrengthIndexSeries, calculateAdaptiveYAxisDomain,
  getStablePaletteColor, normalizeThemeFlowSeries, sortByLatestCumulative,
} from "@/utils/themeFlowNormalization";
import type {
  MarketThemeFlowTrendActor, MarketThemeFlowTrendAttribution, MarketThemeFlowTrendCell,
  MarketThemeFlowTrendMetric, MarketThemeFlowTrendResponse, MarketThemeFlowTrendTheme,
} from "@/types/marketTheme";

const ACTORS: Array<{ value: MarketThemeFlowTrendActor; label: string }> = [
  { value: "FOREIGN", label: "외국인" }, { value: "INSTITUTION", label: "기관" },
  { value: "FOREIGN_INSTITUTION", label: "외국인+기관" }, { value: "INDIVIDUAL", label: "개인" },
  { value: "PROGRAM", label: "프로그램" },
];
const METRICS: Array<{ value: MarketThemeFlowTrendMetric; label: string }> = [
  { value: "FLOW_STRENGTH", label: "수급 강도" }, { value: "NET_AMOUNT", label: "순매수 금액" },
  { value: "BREADTH", label: "연결종목 확산도" },
];
const ATTRIBUTIONS: Array<{ value: MarketThemeFlowTrendAttribution; label: string }> = [
  { value: "FRACTIONAL", label: "중복테마별 1/n" }, { value: "FULL", label: "중복테마별 1" },
];
const ACTOR_LABEL: Record<MarketThemeFlowTrendActor, string> = Object.fromEntries(ACTORS.map((item) => [item.value, item.label])) as Record<MarketThemeFlowTrendActor, string>;
const METRIC_LABEL: Record<MarketThemeFlowTrendMetric, string> = Object.fromEntries(METRICS.map((item) => [item.value, item.label])) as Record<MarketThemeFlowTrendMetric, string>;
const ATTRIBUTION_LABEL: Record<MarketThemeFlowTrendAttribution, string> = Object.fromEntries(ATTRIBUTIONS.map((item) => [item.value, item.label])) as Record<MarketThemeFlowTrendAttribution, string>;
const FLOW_LINE_COLORS = [
  "#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2", "#4f46e5", "#be123c",
  "#65a30d", "#7c3aed", "#0f766e", "#c2410c", "#0369a1", "#a21caf", "#15803d", "#b91c1c",
];
type AmountScaleMode = "normalized" | "raw";
const FLOW_COLORS = ["#2563EB", "#60A5FA", "#93C5FD", "#DBEAFE", "#E5E7EB", "#FEE2E2", "#FCA5A5", "#F87171", "#DC2626"];
const FLOW_NEAR_ZERO_NEGATIVE_COLOR = "#EFF6FF";
const FLOW_NEAR_ZERO_POSITIVE_COLOR = "#FFF1F2";
const BREADTH_BUCKETS = [
  { label: "0~10%", color: "#1D4ED8" }, { label: "10~20%", color: "#2563EB" },
  { label: "20~30%", color: "#60A5FA" }, { label: "30~40%", color: "#93C5FD" },
  { label: "40~50%", color: "#DBEAFE" }, { label: "50~60%", color: "#FEE2E2" },
  { label: "60~70%", color: "#FCA5A5" }, { label: "70~80%", color: "#F87171" },
  { label: "80~90%", color: "#EF4444" }, { label: "90~100%", color: "#B91C1C" },
] as const;
const EMPTY_CELL_COLOR = "#f8fafc";
const CACHE_TTL = 60_000;
const flowTrendCache = new Map<string, { expires: number; value: MarketThemeFlowTrendResponse }>();
export const invalidateMarketThemeFlowTrendFrontendCache = () => flowTrendCache.clear();

const amount = (value: number | null, suffix = true) => {
  if (value == null) return "-";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${sign}${(absolute / 1_000_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조${suffix ? "원" : ""}`;
  return `${sign}${(absolute / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억${suffix ? "원" : ""}`;
};
const pct = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const qualityLabel = (value: string) => value === "ENOUGH" ? "충분" : value === "PARTIAL" ? "일부 부족" : value === "INSUFFICIENT" ? "부족" : "수급 없음";
const streak = (value: number) => value > 0 ? `${value}일 연속 순매수` : value < 0 ? `${Math.abs(value)}일 연속 순매도` : "연속 흐름 없음";

function strengthColor(value: number | null) {
  if (value == null) return EMPTY_CELL_COLOR;
  if (value <= -20) return FLOW_COLORS[0]; if (value <= -15) return FLOW_COLORS[1];
  if (value <= -10) return FLOW_COLORS[2]; if (value <= -5) return FLOW_COLORS[3];
  if (value < 0) return FLOW_NEAR_ZERO_NEGATIVE_COLOR;
  if (value === 0) return FLOW_COLORS[4]; if (value < 5) return FLOW_NEAR_ZERO_POSITIVE_COLOR;
  if (value < 10) return FLOW_COLORS[5]; if (value < 15) return FLOW_COLORS[6];
  if (value < 20) return FLOW_COLORS[7]; return FLOW_COLORS[8];
}
function breadthColor(value: number | null) {
  if (value == null) return EMPTY_CELL_COLOR;
  if (value <= 10) return BREADTH_BUCKETS[0].color; if (value <= 20) return BREADTH_BUCKETS[1].color;
  if (value <= 30) return BREADTH_BUCKETS[2].color; if (value <= 40) return BREADTH_BUCKETS[3].color;
  if (value <= 50) return BREADTH_BUCKETS[4].color; if (value <= 60) return BREADTH_BUCKETS[5].color;
  if (value <= 70) return BREADTH_BUCKETS[6].color; if (value <= 80) return BREADTH_BUCKETS[7].color;
  if (value < 90) return BREADTH_BUCKETS[8].color; return BREADTH_BUCKETS[9].color;
}
function amountColor(value: number | null, cap: number) {
  if (value == null) return EMPTY_CELL_COLOR;
  if (value === 0) return FLOW_COLORS[4];
  const opacity = Math.min(.88, .14 + Math.abs(value) / Math.max(cap, 1) * .74);
  return value > 0 ? `rgba(220,38,38,${opacity})` : `rgba(37,99,235,${opacity})`;
}

function colorChannels(color: string) {
  const hex = color.match(/^#([0-9a-f]{6})$/i);
  if (hex) return [0, 2, 4].map((offset) => Number.parseInt(hex[1].slice(offset, offset + 2), 16));
  const rgba = color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/i);
  if (!rgba) return [248, 250, 252];
  const alpha = rgba[4] == null ? 1 : Number(rgba[4]);
  return [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])].map((channel) => Math.round(channel * alpha + 255 * (1 - alpha)));
}
function heatmapTextColor(background: string) {
  const luminance = colorChannels(background).map((channel) => {
    const value = channel / 255;
    return value <= .03928 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
  }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  const darkLuminance = .009;
  return 1.05 / (luminance + .05) >= (luminance + .05) / (darkLuminance + .05) ? "#ffffff" : "#0f172a";
}

function splitLineSegments(points: Array<{ x: number; y: number } | null>) {
  const segments: Array<Array<{ x: number; y: number }>> = [];
  let current: Array<{ x: number; y: number }> = [];
  points.forEach((point) => {
    if (point) current.push(point);
    else if (current.length) { segments.push(current); current = []; }
  });
  if (current.length) segments.push(current);
  return segments;
}

const linePath = (points: Array<{ x: number; y: number }>) => points.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");

const metricValue = (cell: MarketThemeFlowTrendCell, metric: MarketThemeFlowTrendMetric) => {
  const value = metric === "FLOW_STRENGTH" ? cell.flow_strength : metric === "NET_AMOUNT" ? cell.net_buy_amount : cell.breadth_ratio;
  return value == null || !Number.isFinite(Number(value)) ? null : Number(value);
};

const metricText = (value: number | null, metric: MarketThemeFlowTrendMetric) => {
  if (value == null) return "-";
  if (metric === "NET_AMOUNT") return amount(value);
  return `${value > 0 && metric === "FLOW_STRENGTH" ? "+" : ""}${value.toFixed(metric === "BREADTH" ? 1 : 2)}%`;
};

const normalizedScoreText = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
const normalizedAxisText = (value: number) => `${value > 0 ? "+" : ""}${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}`;

const normalizedScoreInterpretation = (value: number) => {
  if (value >= 3) return "매우 이례적인 강한 수급";
  if (value >= 2) return "매우 강한 수급";
  if (value >= 1) return "평소보다 강한 수급";
  if (value >= 0) return "일반~완만한 강세 수급";
  if (value > -1) return "일반~완만한 약세 수급";
  if (value > -2) return "평소보다 약한 수급";
  if (value > -3) return "강한 약세 수급";
  return "매우 이례적인 약세 수급";
};

function ThemeFlowTrendLineChart({
  themes, dates, actor, metric, attribution, amountScaleMode,
}: {
  themes: MarketThemeFlowTrendTheme[]; dates: string[]; actor: MarketThemeFlowTrendActor;
  metric: MarketThemeFlowTrendMetric; attribution: MarketThemeFlowTrendAttribution; amountScaleMode: AmountScaleMode;
}) {
  const chartWidth = 840;
  const chartHeight = 500;
  const margin = { top: 24, right: 18, bottom: 34, left: 64 };
  const innerWidth = chartWidth - margin.left - margin.right;
  const innerHeight = chartHeight - margin.top - margin.bottom;
  const [hoveredThemeId, setHoveredThemeId] = useState<number | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<{
    themeName: string; date: string; cumulativeValue: number; rawValue: number; normalizedDaily: number | null;
    cell: MarketThemeFlowTrendCell; x: number; y: number;
  } | null>(null);
  const isNormalizedAmount = metric === "NET_AMOUNT" && amountScaleMode === "normalized";
  const isIndexMetric = metric === "FLOW_STRENGTH" || metric === "BREADTH";
  const referenceValue = isIndexMetric ? 100 : 0;
  const series = useMemo(() => themes.map((theme) => {
    const cellMap = new Map(theme.cells.map((cell) => [cell.trade_date, cell]));
    const rawPoints = dates.map((date) => {
      const cell = cellMap.get(date) ?? null;
      return { date, cell, rawValue: cell ? metricValue(cell, metric) : null };
    });
    const normalization = metric === "NET_AMOUNT" ? normalizeThemeFlowSeries(rawPoints.map(({ date, rawValue }) => ({ date, rawValue }))) : null;
    const normalizedDailyValues = normalization?.points.map((point) => point.normalizedValue) ?? rawPoints.map(() => null);
    const dailyCalculationValues = isNormalizedAmount ? normalizedDailyValues : rawPoints.map((point) => point.rawValue);
    const cumulativeValues = metric === "FLOW_STRENGTH"
      ? buildStrengthIndexSeries(rawPoints.map((point) => point.rawValue))
      : metric === "BREADTH"
        ? buildBreadthIndexSeries(rawPoints.map((point) => point.rawValue))
        : buildCumulativeSeries(dailyCalculationValues);
    const values = rawPoints.map((point, pointIndex) => ({
      ...point,
      normalizedDaily: normalizedDailyValues[pointIndex],
      cumulativeValue: cumulativeValues[pointIndex],
    }));
    const latest = [...values].reverse().find((item) => item.cumulativeValue != null)?.cumulativeValue ?? null;
    const latestRaw = [...values].reverse().find((item) => item.rawValue != null)?.rawValue ?? null;
    const latestNormalizedDaily = [...values].reverse().find((item) => item.normalizedDaily != null)?.normalizedDaily ?? null;
    return { theme, color: getStablePaletteColor(theme.theme_id, FLOW_LINE_COLORS), values, latest, latestRaw, latestNormalizedDaily };
  }), [themes, dates, metric, isNormalizedAmount]);
  const sortedLegendSeries = useMemo(() => sortByLatestCumulative(series), [series]);
  const plottedValues = series.flatMap((item) => item.values.map((point) => point.cumulativeValue).filter((value): value is number => value != null));
  if (!dates.length || !plottedValues.length) return <div className="theme-return-line-empty">선그래프로 표시할 거래일 데이터가 없습니다.</div>;
  const allValues = [referenceValue, ...plottedValues];

  const yDomain = calculateAdaptiveYAxisDomain({ values: allValues, baseline: referenceValue, targetTicks: 7, paddingRatio: .06 });
  const { min: yMin, max: yMax, ticks: yTicks } = yDomain;
  const targetXTickCount = Math.min(7, Math.max(2, dates.length));
  const xTickIndexes = new Set(Array.from({ length: targetXTickCount }, (_, index) => Math.round(index * (dates.length - 1) / Math.max(targetXTickCount - 1, 1))));
  const xTicks = dates.filter((_, index) => xTickIndexes.has(index));
  const xScale = (pointIndex: number) => margin.left + innerWidth * pointIndex / Math.max(dates.length, 1);
  const yScale = (value: number) => margin.top + innerHeight - (value - yMin) / (yMax - yMin) * innerHeight;
  const referenceY = referenceValue >= yMin && referenceValue <= yMax ? yScale(referenceValue) : null;
  const style = { "--theme-return-line-chart-height": `${chartHeight}px`, "--theme-return-line-plot-top": `${margin.top}px`, "--theme-return-line-plot-bottom": `${margin.bottom}px` } as CSSProperties;
  const indexText = (value: number | null) => value == null ? "-" : value.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 2 });
  const valueText = (value: number | null) => isIndexMetric ? indexText(value) : isNormalizedAmount ? (value == null ? "-" : normalizedAxisText(value)) : metricText(value, metric);
  const summaryText = (item: typeof series[number]) => isNormalizedAmount
    ? `누적 표준화 ${normalizedScoreText(item.latest)} · 최근 표준화 ${normalizedScoreText(item.latestNormalizedDaily)} · 실제 최근 ${amount(item.latestRaw)}`
    : metric === "NET_AMOUNT"
    ? `30일 누적 ${amount(item.latest)} · 최근 ${amount(item.latestRaw)}`
    : metric === "BREADTH"
      ? `누적지수 ${indexText(item.latest)} · 최근 ${metricText(item.latestRaw, metric)}`
      : `누적지수 ${indexText(item.latest)} · 최근 ${metricText(item.latestRaw, metric)}`;
  const badgeMode = metric === "NET_AMOUNT" ? (isNormalizedAmount ? "표준화 누적" : "누적금액") : "누적지수";

  return <div className="theme-return-line-panel theme-flow-line-panel" style={style}>
    <div className="theme-return-line-header"><div><strong>테마별 30일 누적 수급 선그래프</strong><span>히트맵의 일별 수급값을 지표별 누적 방식으로 변환하여 최근 30일 흐름을 비교합니다. 선의 기울기는 해당 날짜의 수급 변화폭을 나타냅니다.</span></div><small>{ACTOR_LABEL[actor]} · {METRIC_LABEL[metric]} · {badgeMode} · {ATTRIBUTION_LABEL[attribution]}</small></div>
    <div className="theme-return-line-body">
      <div className="theme-return-line-chart theme-flow-line-chart">
        <svg className="theme-return-line-svg" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" role="img" aria-label={`테마별 ${METRIC_LABEL[metric]} 추이 선그래프`}>
          {yTicks.map((tick) => { const y = yScale(tick); return <g key={tick}><line className="theme-return-line-grid" x1={margin.left} x2={chartWidth - margin.right} y1={y} y2={y} /><text className="theme-return-line-axis-label theme-return-line-y-label" x={margin.left - 10} y={y + 3} textAnchor="end">{valueText(tick)}</text></g>; })}
          {referenceY != null ? <line className="theme-return-line-zero" x1={margin.left} x2={chartWidth - margin.right} y1={referenceY} y2={referenceY} /> : null}
          {xTicks.map((date) => { const x = xScale(dates.indexOf(date) + 1); return <g key={date}><line className="theme-return-line-grid theme-return-line-grid--vertical" x1={x} x2={x} y1={margin.top} y2={margin.top + innerHeight} /><text className="theme-return-line-axis-label theme-return-line-x-label" x={x} y={chartHeight - 12} textAnchor="middle">{date.slice(5).replace("-", ".")}</text></g>; })}
          <line className="theme-return-line-axis-line" x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + innerHeight} /><line className="theme-return-line-axis-line" x1={margin.left} x2={chartWidth - margin.right} y1={margin.top + innerHeight} y2={margin.top + innerHeight} />
          {series.map((item) => {
            const points = [{ x: xScale(0), y: yScale(referenceValue) }, ...item.values.map((point, index) => point.cumulativeValue == null ? null : { x: xScale(index + 1), y: yScale(point.cumulativeValue) })];
            const active = hoveredThemeId === item.theme.theme_id; const muted = hoveredThemeId != null && !active;
            return <g key={item.theme.theme_id} className={muted ? "theme-flow-line-series is-muted" : active ? "theme-flow-line-series is-active" : "theme-flow-line-series"}>
              {splitLineSegments(points).filter((segment) => segment.length > 1).map((segment, index) => <path key={index} className="theme-return-line-path" d={linePath(segment)} fill="none" stroke={item.color} onMouseEnter={() => setHoveredThemeId(item.theme.theme_id)} onMouseLeave={() => { setHoveredThemeId(null); setHoveredPoint(null); }} />)}
              {item.values.map((point, index) => point.cumulativeValue == null || point.rawValue == null || !point.cell ? null : <circle key={point.date} className="theme-flow-line-point" cx={xScale(index + 1)} cy={yScale(point.cumulativeValue)} r="7" fill="transparent" tabIndex={0} onMouseEnter={() => { setHoveredThemeId(item.theme.theme_id); setHoveredPoint({ themeName: item.theme.theme_name, date: point.date, cumulativeValue: point.cumulativeValue!, rawValue: point.rawValue!, normalizedDaily: point.normalizedDaily, cell: point.cell!, x: xScale(index + 1), y: yScale(point.cumulativeValue!) }); }} onMouseLeave={() => setHoveredPoint(null)} onFocus={() => { setHoveredThemeId(item.theme.theme_id); setHoveredPoint({ themeName: item.theme.theme_name, date: point.date, cumulativeValue: point.cumulativeValue!, rawValue: point.rawValue!, normalizedDaily: point.normalizedDaily, cell: point.cell!, x: xScale(index + 1), y: yScale(point.cumulativeValue!) }); }} onBlur={() => { setHoveredPoint(null); setHoveredThemeId(null); }}><title>{`${item.theme.theme_name} ${point.date} · 당일 ${metricText(point.rawValue, metric)} · 누적 ${valueText(point.cumulativeValue)}`}</title></circle>)}
            </g>;
          })}
        </svg>
        {hoveredPoint ? <div className="theme-flow-line-tooltip" style={{ left: `${hoveredPoint.x / chartWidth * 100}%`, top: `${hoveredPoint.y / chartHeight * 100}%` }}><strong>{hoveredPoint.themeName}</strong><span>{hoveredPoint.date}</span>{metric === "FLOW_STRENGTH" ? <><span>당일 수급강도 <b>{pct(hoveredPoint.rawValue)}</b></span><span>30일 누적지수 <b>{indexText(hoveredPoint.cumulativeValue)}</b></span><span>기준 100</span></> : metric === "BREADTH" ? <><span>당일 확산도 <b>{metricText(hoveredPoint.rawValue, metric)}</b></span><span>확산 종목 {hoveredPoint.cell.positive_stock_count} / {hoveredPoint.cell.actor_data_stock_count}</span><span>중립 대비 <b>{hoveredPoint.rawValue - 50 > 0 ? "+" : ""}{(hoveredPoint.rawValue - 50).toFixed(1)}%p</b></span><span>30일 누적 확산지수 <b>{indexText(hoveredPoint.cumulativeValue)}</b></span><span>기준 100</span></> : isNormalizedAmount ? <><span>당일 실제 순매수 <b>{amount(hoveredPoint.rawValue)}</b></span><span>당일 표준화 <b>{normalizedScoreText(hoveredPoint.normalizedDaily)}</b></span><span>30일 누적 표준화 <b>{normalizedScoreText(hoveredPoint.cumulativeValue)}</b></span>{hoveredPoint.normalizedDaily != null ? <em>최근 기간 기준 · {normalizedScoreInterpretation(hoveredPoint.normalizedDaily)}</em> : null}</> : <><span>당일 순매수 <b>{amount(hoveredPoint.rawValue)}</b></span><span>30일 누적 순매수 <b>{amount(hoveredPoint.cumulativeValue)}</b></span></>}<span>종목 반영: {ATTRIBUTION_LABEL[attribution]}</span></div> : null}
      </div>
      <div className="theme-return-line-legend-shell" onMouseLeave={() => setHoveredThemeId(null)}><div className="theme-return-line-legend">{sortedLegendSeries.map((item) => { const active = hoveredThemeId === item.theme.theme_id; const muted = hoveredThemeId != null && !active; return <button key={item.theme.theme_id} type="button" className={`theme-return-line-legend-item ${active ? "theme-return-line-legend-item-active" : ""} ${muted ? "theme-return-line-legend-item-muted" : ""}`} onMouseEnter={() => setHoveredThemeId(item.theme.theme_id)} onFocus={() => setHoveredThemeId(item.theme.theme_id)} onBlur={() => setHoveredThemeId(null)}><span className="theme-return-line-legend-color" style={{ background: item.color }} /><span className="theme-return-line-legend-text"><strong>{item.theme.theme_name}</strong><em>{summaryText(item)}</em></span></button>; })}</div></div>
    </div>
  </div>;
}

function Segmented<T extends string>({ label, value, items, onChange }: { label: string; value: T; items: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return <div className="theme-flow-filter-group"><span>{label}</span><div className="theme-flow-segmented">{items.map((item) => <button type="button" key={item.value} className={value === item.value ? "active" : ""} aria-pressed={value === item.value} onClick={() => onChange(item.value)}>{item.label}</button>)}</div></div>;
}

type Props = {
  endDate: string; onEndDateChange: (value: string) => void;
  themeGroupId: string; onThemeGroupChange: (value: string) => void;
  keyword: string; onKeywordChange: (value: string) => void;
  limit: string; onLimitChange: (value: string) => void;
  themeGroups: Array<{ id: number; theme_name: string }>;
  onCellClick: (theme: MarketThemeFlowTrendTheme, date: string, actor: MarketThemeFlowTrendActor, metric: MarketThemeFlowTrendMetric, attribution: MarketThemeFlowTrendAttribution) => void;
};

export default function MarketThemeFlowTrendPanel(props: Props) {
  const [viewMode, setViewMode] = useState<"heatmap" | "line">("heatmap");
  const [amountScaleMode, setAmountScaleMode] = useState<AmountScaleMode>("normalized");
  const [metricInfoOpen, setMetricInfoOpen] = useState(false);
  const [actor, setActor] = useState<MarketThemeFlowTrendActor>("FOREIGN");
  const [metric, setMetric] = useState<MarketThemeFlowTrendMetric>("FLOW_STRENGTH");
  const [attribution, setAttribution] = useState<MarketThemeFlowTrendAttribution>("FRACTIONAL");
  const [data, setData] = useState<MarketThemeFlowTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [highlightedThemeId, setHighlightedThemeId] = useState<number | null>(null);
  const requestSequence = useRef(0);
  const handledRefreshKey = useRef(0);
  const rowRefs = useRef(new Map<number, HTMLDivElement>());
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const metricInfoRef = useRef<HTMLDivElement | null>(null);

  const paramsKey = [props.endDate, props.themeGroupId, props.keyword.trim(), props.limit, actor, metric, attribution].join("|");
  useEffect(() => {
    const sequence = ++requestSequence.current;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const forceRefresh = refreshKey > handledRefreshKey.current;
      if (forceRefresh) handledRefreshKey.current = refreshKey;
      const cached = flowTrendCache.get(paramsKey);
      if (!forceRefresh && cached && cached.expires > Date.now()) {
        setData(cached.value); setError(""); setLoading(false); return;
      }
      setLoading(true); setError("");
      repositories.marketThemes.getThemeFlowTrend({
        end_date: props.endDate, recent_days: 30, actor, metric, attribution,
        theme_group_id: props.themeGroupId === "all" ? undefined : Number(props.themeGroupId),
        search: props.keyword.trim() || undefined, limit: props.limit === "all" ? 100 : Number(props.limit),
        refresh: forceRefresh, signal: controller.signal,
      }).then((response) => {
        if (sequence !== requestSequence.current || controller.signal.aborted) return;
        flowTrendCache.set(paramsKey, { expires: Date.now() + CACHE_TTL, value: response });
        setData(response);
      }).catch((reason: unknown) => {
        if (controller.signal.aborted || sequence !== requestSequence.current) return;
        setData(null); setError(reason instanceof Error ? reason.message : "테마 수급 데이터를 불러오지 못했습니다.");
      }).finally(() => { if (sequence === requestSequence.current && !controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [paramsKey, refreshKey]);
  useEffect(() => () => { if (highlightTimer.current) clearTimeout(highlightTimer.current); }, []);
  useEffect(() => {
    if (!metricInfoOpen) return;
    const closeOutside = (event: MouseEvent) => { if (!metricInfoRef.current?.contains(event.target as Node)) setMetricInfoOpen(false); };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setMetricInfoOpen(false); };
    document.addEventListener("mousedown", closeOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", closeOutside); window.removeEventListener("keydown", closeOnEscape); };
  }, [metricInfoOpen]);

  const validAmounts = useMemo(() => (data?.themes ?? []).flatMap((theme) => theme.cells.map((cell) => Math.abs(cell.net_buy_amount ?? 0))).filter((value) => value > 0).sort((a, b) => a - b), [data]);
  const amountCap = validAmounts.length ? validAmounts[Math.min(validAmounts.length - 1, Math.floor(validAmounts.length * .95))] : 1;
  const cellValue = (cell: MarketThemeFlowTrendCell) => metric === "FLOW_STRENGTH" ? (cell.flow_strength == null ? "-" : `${cell.flow_strength > 0 ? "+" : ""}${cell.flow_strength.toFixed(1)}`) : metric === "NET_AMOUNT" ? amount(cell.net_buy_amount, false) : cell.breadth_ratio == null ? "-" : `${Math.round(cell.breadth_ratio)}`;
  const cellColor = (cell: MarketThemeFlowTrendCell) => metric === "FLOW_STRENGTH" ? strengthColor(cell.flow_strength) : metric === "NET_AMOUNT" ? amountColor(cell.net_buy_amount, amountCap) : breadthColor(cell.breadth_ratio);
  const cellTone = (cell: MarketThemeFlowTrendCell) => {
    const value = metric === "FLOW_STRENGTH" ? cell.flow_strength : metric === "NET_AMOUNT" ? cell.net_buy_amount : cell.breadth_ratio == null ? null : cell.breadth_ratio - 50;
    return value == null || value === 0 ? "is-neutral" : value > 0 ? "is-positive" : "is-negative";
  };
  const tooltip = (theme: MarketThemeFlowTrendTheme, cell: MarketThemeFlowTrendCell) => [
    theme.theme_name, cell.trade_date, "", `${ACTOR_LABEL[actor]} 순매수: ${amount(cell.net_buy_amount)}`,
    `수급 강도: ${pct(cell.flow_strength)}`, `연결종목 확산도: ${cell.actor_data_stock_count ? `${cell.positive_stock_count}/${cell.actor_data_stock_count}종목 · ${cell.breadth_ratio?.toFixed(1)}%` : "-"}`,
    `테마 등락률: ${pct(cell.theme_return_pct)}`, `테마 거래대금: ${amount(cell.trading_value)}`,
    "", "상위 수급 기여 종목", ...cell.top_contributors.map((item, index) => `${index + 1}. ${item.stock_name} ${amount(item.net_buy_amount)}`),
    "", `수급 데이터: ${cell.actor_data_stock_count}/${cell.connected_stock_count}종목 · ${cell.data_quality}`,
    `종목 반영 기준: ${attribution === "FRACTIONAL" ? "중복테마별 1/n" : "중복테마별 1"}`,
    ...(actor === "PROGRAM" ? ["프로그램 수급은 외국인·기관 수급과 중복될 수 있습니다."] : []),
  ].join("\n");

  const scrollToTheme = (themeId: number) => {
    rowRefs.current.get(themeId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightedThemeId(themeId);
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    highlightTimer.current = setTimeout(() => setHighlightedThemeId(null), 1400);
  };
  const topCards = data ? [
    { label: `오늘 ${ACTOR_LABEL[actor]} 유입 1위`, item: data.summary.top_today, value: pct(data.summary.top_today?.flow_strength ?? null) },
    { label: `5일 ${ACTOR_LABEL[actor]} 누적 1위`, item: data.summary.top_five_day, value: amount(data.summary.top_five_day?.net_buy_amount ?? null) },
    { label: `${ACTOR_LABEL[actor]} 연결종목 확산도 1위`, item: data.summary.top_breadth, value: data.summary.top_breadth?.breadth_ratio == null ? "-" : `${data.summary.top_breadth.positive_stock_count}/${data.summary.top_breadth.actor_data_stock_count}종목 · ${Math.round(data.summary.top_breadth.breadth_ratio)}%` },
    { label: `${ACTOR_LABEL[actor]} 순매수 지속 1위`, item: data.summary.top_streak, value: data.summary.top_streak ? streak(data.summary.top_streak.current_streak) : "-" },
  ] : [];

  return <div className="theme-flow-trend-panel">
    <div className="theme-return-trend-toolbar">
      <input className="input-control" type="date" value={props.endDate} onChange={(event) => props.onEndDateChange(event.target.value)} />
      <select className="select-control" value={props.themeGroupId} onChange={(event) => props.onThemeGroupChange(event.target.value)}><option value="all">테마그룹 전체</option>{props.themeGroups.map((group) => <option key={group.id} value={group.id}>{group.theme_name}</option>)}</select>
      <input className="input-control" placeholder="테마명 검색" value={props.keyword} onChange={(event) => props.onKeywordChange(event.target.value)} />
      <select className="select-control" value={props.limit} onChange={(event) => props.onLimitChange(event.target.value)}><option value="10">상위 10개</option><option value="20">상위 20개</option><option value="30">상위 30개</option><option value="all">전체</option></select>
      <button type="button" className="btn btn-secondary market-theme-refresh-button" title="저장된 테마 수급 데이터를 다시 조회합니다. 외부 수급 수집은 실행하지 않습니다." onClick={() => { flowTrendCache.clear(); setRefreshKey((value) => value + 1); }} disabled={loading}>{loading ? "조회 중..." : "새로고침"}</button>
      <div className="theme-return-view-toggle" aria-label="테마수급추이 보기 선택"><button type="button" className={viewMode === "heatmap" ? "active" : ""} onClick={() => setViewMode("heatmap")}>히트맵</button><button type="button" className={viewMode === "line" ? "active" : ""} onClick={() => setViewMode("line")}>선그래프</button></div>
    </div>
    <div className="theme-flow-filter-row">
      <Segmented label="투자주체" value={actor} items={ACTORS} onChange={setActor} />
      <div className="theme-flow-filter-group theme-flow-metric-filter" ref={metricInfoRef}>
        <span className="theme-flow-filter-label">표시 지표 <button type="button" className="theme-flow-metric-info-button" aria-label="표시 지표 누적 계산 기준" aria-expanded={metricInfoOpen} aria-controls="theme-flow-metric-info" onClick={() => setMetricInfoOpen((value) => !value)}><Info size={13} /></button></span>
        <div className="theme-flow-segmented">{METRICS.map((item) => <button type="button" key={item.value} className={metric === item.value ? "active" : ""} aria-pressed={metric === item.value} onClick={() => setMetric(item.value)}>{item.label}</button>)}</div>
        {metricInfoOpen ? <div id="theme-flow-metric-info" className="theme-flow-metric-popover" role="dialog" aria-labelledby="theme-flow-metric-info-title">
          <strong id="theme-flow-metric-info-title">표시 지표 · 30일 누적 계산 기준</strong>
          <div className="theme-flow-metric-popover-grid">
            <section><h4>수급 강도</h4><b>100 기준 복리 누적지수</b><code>전일 지수 × (1 + 당일 강도 / 100)</code><p>100 초과는 양의 수급강도, 100 미만은 음의 수급강도가 누적 우세함을 의미합니다.</p><small>100 → +10% → 110 → +10% → 121</small></section>
            <section><h4>순매수 금액</h4><b>일별 값 단순 누적</b><code>누적값 + 당일 순매수</code><p>원금액은 실제 자금 누적액, 표준화는 테마별 일별 Robust Z-score의 누적합입니다.</p><small>+300억 → -100억 → +500억 = +700억</small></section>
            <section><h4>연결종목 확산도</h4><b>50% 중립 · 100 기준 복리</b><code>전일 지수 × (1 + (확산도 - 50) / 100)</code><p>100 초과는 폭넓은 확산, 100 미만은 제한적인 확산이 누적 우세함을 의미합니다.</p><small>60% → +10% 기여 → 100에서 110</small></section>
          </div>
          <footer>히트맵은 일별 실제값을 표시하고, 선그래프는 위 기준의 최근 30일 누적 흐름을 표시합니다. 선의 기울기는 해당 날짜의 수급 변화폭입니다.</footer>
        </div> : null}
      </div>
      {viewMode === "line" && metric === "NET_AMOUNT" ? <Segmented label="금액 보기" value={amountScaleMode} items={[{ value: "normalized", label: "표준화" }, { value: "raw", label: "원금액" }]} onChange={setAmountScaleMode} /> : null}
      <Segmented label="종목 반영 기준" value={attribution} items={ATTRIBUTIONS} onChange={setAttribution} />
    </div>
    {actor === "PROGRAM" ? <p className="theme-flow-program-notice">프로그램은 독립 투자주체가 아닌 매매 방식 수급이며 외국인·기관 거래와 일부 중복될 수 있습니다.</p> : null}
    <p className="theme-flow-basis">집계 기준: 현재 활성 연결 종목 · {attribution === "FRACTIONAL" ? "중복테마별 1/n" : "중복테마별 1"} <span>과거 수급은 현재 활성 연결 종목 기준으로 계산됩니다.</span></p>
    {error ? <div className="theme-flow-state is-error"><strong>테마 수급 데이터를 불러오지 못했습니다.</strong><span>{error}</span><button type="button" onClick={() => setRefreshKey((value) => value + 1)}><RefreshCw size={13} /> 다시 시도</button></div> : null}
    {!error && topCards.length ? <div className="theme-flow-top-grid">{topCards.map((card) => <button type="button" key={card.label} disabled={!card.item} onClick={() => card.item && scrollToTheme(card.item.theme_id)}><span>{card.label}</span><strong>{card.item?.theme_name ?? "-"}</strong><em>{card.value}</em></button>)}</div> : null}
    {!error && viewMode === "heatmap" && metric === "FLOW_STRENGTH" ? <div className="theme-return-legend">{["-20% 이하", "-15%", "-10%", "-5%", "0%", "+5%", "+10%", "+15%", "+20% 이상"].map((label, index) => <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: FLOW_COLORS[index] }} />{label}</span>)}</div> : null}
    {!error && viewMode === "heatmap" && metric === "BREADTH" ? <div className="theme-return-legend">{BREADTH_BUCKETS.map((bucket) => <span key={bucket.label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: bucket.color }} />{bucket.label}</span>)}</div> : null}
    {!error && viewMode === "heatmap" && metric === "NET_AMOUNT" ? <p className="theme-flow-amount-legend">순매수 금액 색상은 현재 응답의 절대값 95 percentile을 상한으로 사용하며 실제 표시 금액은 변경하지 않습니다.</p> : null}
    {!error && viewMode === "line" && !loading && data?.themes.length ? <ThemeFlowTrendLineChart themes={data.themes} dates={data.dates} actor={actor} metric={metric} attribution={attribution} amountScaleMode={amountScaleMode} /> : null}
    {!error && viewMode === "heatmap" ? <div className="theme-return-heatmap-wrap theme-flow-heatmap-wrap">
      <div className="theme-return-heatmap theme-flow-heatmap" style={{ gridTemplateColumns: `var(--theme-flow-theme-column-width) repeat(${Math.max(data?.dates.length ?? 0, 1)}, minmax(var(--theme-flow-date-cell-min-width), 1fr))`, minWidth: `calc(var(--theme-flow-theme-column-width) + ${Math.max(data?.dates.length ?? 0, 1)} * var(--theme-flow-date-cell-min-width))` }}>
        <div className="theme-return-heatmap__theme-cell theme-return-heatmap__header-cell">테마</div>
        {(data?.dates ?? []).map((day) => <div key={day} className="theme-return-heatmap__date-cell" title={day}>{day.slice(8)}</div>)}
        {loading ? <div className="theme-return-heatmap__empty-row">테마수급추이를 조회 중입니다.</div> : null}
        {!loading && (!data || !data.themes.length) ? <div className="theme-flow-state"><strong>수집된 테마 수급 데이터가 없습니다.</strong><span>‘테마 등락률&수급 갱신’을 실행하면 현재 활성 연결 종목의 수급 데이터를 수집할 수 있습니다.</span></div> : null}
        {!loading && data?.themes.map((theme) => <Fragment key={theme.theme_id}>
          <div ref={(node) => { if (node) rowRefs.current.set(theme.theme_id, node); else rowRefs.current.delete(theme.theme_id); }} className={`theme-return-heatmap__theme-cell theme-flow-theme-cell ${highlightedThemeId === theme.theme_id ? "is-highlighted" : ""}`}>
            <div className="theme-flow-theme-heading"><strong>{theme.theme_name}</strong><em className={`theme-flow-quality-badge is-${theme.twenty_day_summary.data_quality.toLowerCase()}`} title={`수급 완전성 ${theme.twenty_day_summary.actor_data_stock_count}/${theme.connected_stock_count}종목 · ${(theme.twenty_day_summary.completeness_ratio * 100).toFixed(0)}%`}>{qualityLabel(theme.twenty_day_summary.data_quality)}</em></div>
            <span>20일 {amount(theme.twenty_day_summary.cumulative_net_buy_amount, false)} | 강도 {pct(theme.twenty_day_summary.flow_strength)}</span>
            <span>{streak(theme.twenty_day_summary.current_streak)} | 연결종목 확산 {theme.twenty_day_summary.positive_stock_count}/{theme.twenty_day_summary.actor_data_stock_count}</span>
          </div>
          {theme.cells.map((cell) => { const background = cellColor(cell); const description = tooltip(theme, cell); return <button type="button" key={`${theme.theme_id}-${cell.trade_date}`} className={`theme-return-heatmap__value-cell theme-flow-value-cell ${cellTone(cell)} ${cell.actor_data_stock_count ? "" : "theme-return-heatmap__value-cell--empty"}`} style={{ background, color: heatmapTextColor(background) }} title={description} aria-label={description.split("\n").join(", ")} onClick={() => cell.actor_data_stock_count && props.onCellClick(theme, cell.trade_date, actor, metric, attribution)}><span>{cellValue(cell)}</span></button>; })}
        </Fragment>)}
      </div>
    </div> : null}
  </div>;
}
