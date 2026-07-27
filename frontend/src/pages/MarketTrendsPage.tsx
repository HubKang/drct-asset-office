import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CSSProperties, DragEvent } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { buildTreemapLayout, getTreemapLabelClass, getTreemapTextMetrics } from "@/utils/treemapLayout";
import {
  buildNaverKoreaMarketChartUrl,
  buildNaverStockCandleChartUrl,
  createNaverChartSidcode,
  normalizeNaverStockCode as normalizeStockCode,
} from "@/utils/naverChart";
import { repositories } from "@/services";
import type {
  AddMarketEventThemeLinkRequest,
  DailyThemeFlowStock,
  DailyThemeFlowSummary,
  KiwoomConditionItem,
  KiwoomConditionResultItem,
  ExistingMarketEventTheme,
  KiwoomMarketEventItem,
  MarketEventThemeLink,
  MonthlyThemeFlowCalendarTheme,
  MonthlyThemeFlowCalendarDay,
  MonthlySupplySummary30d,
  SupplyTopStockReturnTrendResponse,
  MonthlyThemeFlowTrendPoint,
  MonthlyThemeFlowTrendResponse,
} from "@/types/marketTrend";
import type { MarketTheme } from "@/types/marketTheme";
import type { Stock } from "@/types/stock";
import type { StockTrackingGroup } from "@/types/stockTracking";

type ActiveTab = "kiwoom" | "flow" | "monthly";
type SortOrder = "asc" | "desc";
type ConditionOrderMode = "number" | "name";
type ResultSortKey = "stock_code" | "stock_name" | "current_price" | "change_rate" | "volume" | "estimated_trading_value";
type ThemeFlowViewMode = "THEME" | "THEME_GROUP";
type SelectedDayDetailTab = "themes" | "memos";
type TrackingRegisterSource = "saved-candidates" | "condition-results";
type MarketTrendThemeOption = Pick<MarketTheme, "id" | "theme_name" | "latest_return">;
type MonthlyThemeFlowView = "heatmap" | "treemap";
type MonthlySupplyHeatmapRow = {
  marketThemeId: number;
  themeName: string;
  themeGroupName: string | null;
  avgChangeRate: number | null;
  stockCount: number;
  eventCount: number;
  dailyMap: Map<string, MonthlyThemeFlowTrendPoint>;
};
type MonthlyThemeTreemapItem = {
  marketThemeId: number;
  themeName: string;
  viewMode: ThemeFlowViewMode;
  themeGroupId: number | null;
  themeGroupName: string | null;
  childThemeCount: number;
  topChildThemes: string[];
  scoreSum: number;
  stockCount: number;
  eventCount: number;
  relatedStocks: string[];
  rank: number;
  sourceDates: string[];
  latestDate: string | null;
  supplyValueSum: number;
  latestFinalRank: number | null;
};
type ManualCandidateForm = {
  trade_date: string;
  change_rate: string;
  trading_value: string;
  volume: string;
  theme_id: string;
  memo: string;
};

const fmtNumber = (value: number | null | undefined) => (value == null ? "-" : value.toLocaleString("ko-KR"));
const fmtPct = (value: number | null | undefined) => (value == null ? "-" : `${value.toFixed(2)}%`);
const fmtSignedPct = (value: number | null | undefined) => (value == null ? "-" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`);
const fmtScore = (value: number | null | undefined) => (value == null ? "0.0" : value.toLocaleString("ko-KR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
const fmtEokShort = (value: number | null | undefined) => (value == null ? "-" : `${(value / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`);
const fmtEok2 = (value: number | null | undefined) => (value == null ? "-" : (value / 100000000).toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const toErr = (e: unknown, fallback: string) => {
  if (e instanceof Error) {
    const msg = e.message || "";
    if (msg.toLowerCase().includes("failed to fetch")) {
      return "백엔드 API 서버 연결에 실패했습니다. 백엔드 실행 상태와 VITE_API_BASE_URL 설정을 확인해 주세요.";
    }
    return msg || fallback;
  }
  return fallback;
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).replace("T", " ").slice(0, 10);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const getNaverChartImageUrl = (stockCode: string, period: "day" | "week" | "month", sidcode: number) => {
  return buildNaverStockCandleChartUrl(stockCode, period, sidcode);
};

const getNaverMarketChartImageUrl = (market: "KOSPI" | "KOSDAQ", sidcode: number) =>
  buildNaverKoreaMarketChartUrl(market, sidcode);

const estimatedTradingValue = (item: { estimated_trading_value?: number | null; current_price?: number | null; volume?: number | null; trading_value?: number | null }) => {
  if (item.estimated_trading_value != null) return item.estimated_trading_value;
  if (item.current_price != null && item.volume != null) return Math.max(0, item.current_price) * Math.max(0, item.volume);
  if (item.trading_value != null) return item.trading_value;
  return null;
};

const changeRateClass = (value: number | null | undefined) => {
  const n = Number(value ?? 0);
  if (n > 0) return "rate-positive";
  if (n < 0) return "rate-negative";
  return "";
};

const heatmapReturnClass = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "is-empty";
  const n = Number(value);
  if (n <= -10) return "negative-strong";
  if (n <= -5) return "negative-medium";
  if (n < 0) return "negative-soft";
  if (n >= 10) return "positive-strong";
  if (n >= 5) return "positive-medium";
  if (n > 0) return "positive-soft";
  return "neutral";
};

const fmtHeatmapPct = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}`;
};

type MonthlySupplyHeatmapProps = {
  rows: MonthlySupplyHeatmapRow[];
  dates: string[];
  onSelectDate: (date: string) => void;
};

const MonthlySupplyHeatmap = memo(function MonthlySupplyHeatmap({
  rows,
  dates,
  onSelectDate,
}: MonthlySupplyHeatmapProps) {
  return (
    <div className="monthly-supply-heatmap-wrap">
      <div className="monthly-supply-heatmap-legend">
        <span><i className="negative-strong" />-10% 이하</span>
        <span><i className="negative-medium" />-5%</span>
        <span><i className="neutral" />0%</span>
        <span><i className="positive-medium" />+5%</span>
        <span><i className="positive-strong" />+10% 이상</span>
      </div>
      <div className="monthly-supply-heatmap-scroll">
        <div className="monthly-supply-heatmap" style={{ gridTemplateColumns: `minmax(130px, 180px) repeat(${Math.max(dates.length, 1)}, minmax(0, 1fr))` }}>
          <div className="monthly-supply-heatmap-theme-cell monthly-supply-heatmap-header-cell">테마</div>
          {dates.map((date) => (
            <div key={`heat-date-${date}`} className="monthly-supply-heatmap-date-cell" title={date}>{date.slice(8, 10)}</div>
          ))}
          {rows.map((row) => (
            <Fragment key={`heat-row-${row.marketThemeId}`}>
              <div className="monthly-supply-heatmap-theme-cell" title={row.themeGroupName ? `${row.themeGroupName} / ${row.themeName}` : row.themeName}>
                <strong>{row.themeName}</strong>
                <span>출현 {row.dailyMap.size}일 · {row.stockCount}종목</span>
              </div>
              {dates.map((date) => {
                const dayTheme = row.dailyMap.get(date);
                const value = dayTheme?.avg_change_rate ?? null;
                return (
                  <button
                    key={`heat-cell-${row.marketThemeId}-${date}`}
                    type="button"
                    className={`monthly-supply-heatmap-cell ${heatmapReturnClass(value)}`}
                    title={dayTheme ? `${date} ${row.themeName} 평균 ${fmtSignedPct(value)} · ${dayTheme.stock_count}종목` : `${date} 데이터 없음`}
                    onClick={() => onSelectDate(date)}
                  >
                    <span>{fmtHeatmapPct(value)}</span>
                  </button>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
});
const STOCK_RETURN_COLORS = [
  "#dc2626", "#2563eb", "#16a34a", "#ea580c", "#7c3aed",
  "#0891b2", "#db2777", "#4f46e5", "#65a30d", "#d97706",
  "#0f766e", "#9333ea", "#be123c", "#0284c7", "#15803d",
  "#c2410c", "#6d28d9", "#0369a1", "#a16207", "#475569",
];

type SupplyTopStockReturnChartProps = {
  data: SupplyTopStockReturnTrendResponse | null;
  loading: boolean;
  error: string;
  collecting: boolean;
  collectionMessage: string;
  onRetry: () => void;
  onRefreshPrices: () => void;
};

const SupplyTopStockReturnChart = memo(function SupplyTopStockReturnChart({
  data,
  loading,
  error,
  collecting,
  collectionMessage,
  onRetry,
  onRefreshPrices,
}: SupplyTopStockReturnChartProps) {
  const [hoveredStockId, setHoveredStockId] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(860);
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
 useEffect(() => {
    const element = chartContainerRef.current;
    if (!element) return undefined;
    const updateWidth = () => setChartWidth(Math.max(620, Math.round(element.clientWidth)));
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, [data, loading]);
  const width = chartWidth;
  const height = 430;
  const margin = { top: 24, right: 16, bottom: 42, left: 54 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const dates = data?.trade_dates ?? [];
  const stocks = data?.stocks ?? [];
  const plottedStocks = stocks.filter((stock) => stock.has_sufficient_price_data);
  const values = plottedStocks.flatMap((stock) => stock.points.map((point) => point.cumulative_return).filter((value): value is number => value != null));
  const rawMin = Math.min(0, ...(values.length ? values : [0]));
  const rawMax = Math.max(0, ...(values.length ? values : [0]));
  const span = Math.max(rawMax - rawMin, 10);
  const yMin = rawMin - span * 0.08;
  const yMax = rawMax + span * 0.08;
  const xOf = (index: number) => margin.left + (dates.length <= 1 ? plotWidth / 2 : (index / (dates.length - 1)) * plotWidth);
  const yOf = (value: number) => margin.top + ((yMax - value) / Math.max(yMax - yMin, 1)) * plotHeight;
  const colorByStock = new Map(stocks.map((stock, index) => [stock.stock_id, STOCK_RETURN_COLORS[index % STOCK_RETURN_COLORS.length]]));
  const yTicks = Array.from({ length: 6 }, (_, index) => yMax - ((yMax - yMin) * index) / 5);
  const xTickIndexes = Array.from(new Set([0, Math.floor((dates.length - 1) / 2), dates.length - 1])).filter((index) => index >= 0);

  const segmentsFor = (stock: (typeof stocks)[number]) => {
    const pointMap = new Map(stock.points.map((point) => [point.trade_date, point.cumulative_return]));
    const segments: Array<Array<{ index: number; value: number; date: string }>> = [];
    let current: Array<{ index: number; value: number; date: string }> = [];
    dates.forEach((date, index) => {
      const value = pointMap.get(date);
      if (value == null) {
        if (current.length) segments.push(current);
        current = [];
      } else {
        current.push({ index, value, date });
      }
    });
    if (current.length) segments.push(current);
    return segments;
  };

  return (
    <section className="monthly-supply-stock-return-card" aria-labelledby="monthly-supply-stock-return-title">
      <div className="monthly-supply-stock-return-header">
        <div>
          <h3 id="monthly-supply-stock-return-title">최근 30일 수급 TOP20 종목 누적등락률</h3>
          <p>수급 출현일 수 기준 상위 종목의 기간 시작 전 종가 대비 누적등락률입니다. 가격이 없는 거래일은 선을 연결하지 않습니다.</p>
        </div>
                {data ? (
          <div className="monthly-supply-stock-return-actions">
            <span className="monthly-supply-stock-return-badge">최근 가격 수집일 {data.last_price_collection_date ?? "-"}</span>
            <button
              type="button"
              className="monthly-supply-price-collect-button"
              disabled={collecting || stocks.length === 0}
              onClick={onRefreshPrices}
            >
              {collecting ? "TOP20 가격 갱신 중..." : "TOP20 가격 갱신"}
            </button>

          </div>
        ) : null}
      </div>
      {loading ? (
        <div className="monthly-supply-stock-return-state">누적등락률을 불러오는 중입니다.</div>
      ) : error ? (
        <div className="monthly-supply-stock-return-state error"><span>{error}</span><button type="button" onClick={onRetry}>다시 시도</button></div>
      ) : !data || stocks.length === 0 ? (
        <div className="monthly-supply-stock-return-state">최근 30일 수급 종목 데이터가 없습니다.</div>
      ) : (
        <div className="monthly-supply-stock-return-body">
          <div className="monthly-supply-stock-return-plot" ref={chartContainerRef}>
            {plottedStocks.length === 0 ? (
              <div className="monthly-supply-stock-return-empty">누적등락률을 계산할 수 있는 가격 데이터가 없습니다.</div>
            ) : (
              <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="수급 TOP20 종목 누적등락률 선그래프" onMouseLeave={() => setHoveredStockId(null)}>
                {yTicks.map((tick) => (
                  <g key={`y-${tick}`}>
                    <line x1={margin.left} x2={width - margin.right} y1={yOf(tick)} y2={yOf(tick)} className={Math.abs(tick) < span / 50 ? "zero" : ""} />
                    <text x={margin.left - 10} y={yOf(tick) + 4} textAnchor="end">{tick.toFixed(0)}%</text>
                  </g>
                ))}
                {xTickIndexes.map((index) => <text key={`x-${index}`} x={xOf(index)} y={height - 13} textAnchor={index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle"}>{dates[index]?.slice(5).replace("-", ".")}</text>)}
                {plottedStocks.map((stock) => {
                  const color = colorByStock.get(stock.stock_id) ?? "#475569";
                  const isDimmed = hoveredStockId != null && hoveredStockId !== stock.stock_id;
                  return (
                    <g key={`stock-line-${stock.stock_id}`} className={isDimmed ? "dimmed" : ""} onMouseEnter={() => setHoveredStockId(stock.stock_id)}>
                      {segmentsFor(stock).map((segment, segmentIndex) => {
                        const d = segment.map((point, index) => `${index ? "L" : "M"}${xOf(point.index)},${yOf(point.value)}`).join(" ");
                        return <path key={`${stock.stock_id}-${segmentIndex}`} d={d} fill="none" stroke={color} className={hoveredStockId === stock.stock_id ? "active" : ""}><title>{stock.rank}위 {stock.stock_name} · 수급 {stock.appearance_count}회 · 최신 누적 {fmtSignedPct(stock.latest_cumulative_return)}</title></path>;
                      })}
                      {stock.points.filter((point) => point.cumulative_return != null && dates.includes(point.trade_date)).map((point) => {
                        const dateIndex = dates.indexOf(point.trade_date);
                        return <circle key={`${stock.stock_id}-${point.trade_date}`} cx={xOf(dateIndex)} cy={yOf(point.cumulative_return as number)} r="5" fill="transparent"><title>{point.trade_date} · {stock.stock_name} · 종가 {fmtNumber(point.close)}원 · 일간 {fmtSignedPct(point.daily_return)} · 누적 {fmtSignedPct(point.cumulative_return)}{point.is_supply_date ? " · 수급 출현일" : ""}</title></circle>;
                      })}
                    </g>
                  );
                })}
              </svg>
            )}
          </div>
          <ol className="monthly-supply-stock-return-legend" aria-label="수급 TOP20 종목 범례">
            {stocks.map((stock) => {
              const color = colorByStock.get(stock.stock_id) ?? "#475569";
              const isDimmed = hoveredStockId != null && hoveredStockId !== stock.stock_id;
              return (
                <li
                  key={`stock-legend-${stock.stock_id}`}
                  className={`${isDimmed ? "dimmed" : ""} ${hoveredStockId === stock.stock_id ? "active" : ""}`}
                  title={`${stock.price_data_status_name} · 관측 ${stock.price_observation_count}/${stock.expected_trade_date_count}일 · 기준 종가일 ${stock.base_price_date ?? "-"} · 최근 가격일 ${stock.latest_price_date ?? "-"} · 커버리지 ${stock.price_coverage_rate}% · ${stock.has_sufficient_price_data ? "그래프 표시 가능" : "가격 관측 부족"} · ${stock.price_data_reason}`}
                  onMouseEnter={() => setHoveredStockId(stock.stock_id)}
                  onMouseLeave={() => setHoveredStockId(null)}
                >
                  <span className="monthly-supply-stock-return-rank">{stock.rank}</span>
                  <i style={{ backgroundColor: stock.has_sufficient_price_data ? color : "#cbd5e1" }} />
                  <span className="monthly-supply-stock-return-name" title={`${stock.stock_name} (${stock.stock_code})`}>{stock.stock_name}</span>
                  <span className="monthly-supply-stock-return-count">출현 {stock.appearance_count}회{stock.price_data_status === "READY_WITH_FALLBACK" ? " · 첫 종가 기준" : ""}</span>
                  <strong className={!stock.has_sufficient_price_data ? "insufficient" : (stock.latest_cumulative_return ?? 0) >= 0 ? "positive" : "negative"}>
                    {stock.has_sufficient_price_data ? fmtSignedPct(stock.latest_cumulative_return) : stock.price_data_status_name}
                  </strong>
                </li>
              );
            })}
          </ol>
        </div>
      )}
      {collectionMessage ? <p className="monthly-supply-price-collect-message">{collectionMessage}</p> : null}
      {data?.price_data_end_date ? <p className="monthly-supply-stock-return-footnote">가격 기준일 {data.price_data_end_date} · 기준 종가: 기간 시작 전 최근 거래일(없으면 기간 내 첫 종가)</p> : null}
    </section>
  );
});
const getResultRowKey = (row: KiwoomConditionResultItem) => `${row.stock_code || "NA"}|${row.stock_name || "NA"}|${row.detected_at || "NA"}|${row.source_api || "NA"}`;
const escapeMarkdownCell = (value: string | number | null | undefined) => String(value ?? "-").replace(/\|/g, "\\|").replace(/\r?\n/g, " ").trim() || "-";
const getConditionResultMarket = (row: KiwoomConditionResultItem) => {
  const raw = row.raw ?? {};
  const candidates = ["market", "market_type", "stex_tp", "mrkt_tp", "시장", "시장구분"];
  for (const key of candidates) {
    const value = raw[key];
    if (value != null && String(value).trim()) return String(value).trim();
  }
  return "-";
};
const getMonthInput = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
const shiftMonthInput = (month: string, offset: number) => {
  const [year, monthNumber] = month.split("-").map(Number);
  const next = new Date(year, monthNumber - 1 + offset, 1);
  return getMonthInput(next);
};
const formatInputDate = (d: Date) => {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const todayInKst = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
const shiftDate = (dateText: string, diffDays: number) => {
  const [y, m, dValue] = dateText.split("-").map(Number);
  const d = y && m && dValue ? new Date(y, m - 1, dValue) : new Date(dateText);
  if (Number.isNaN(d.getTime())) return dateText;
  d.setDate(d.getDate() + diffDays);
  return formatInputDate(d);
};

const subtractOneMonth = (baseDate: string) => {
  const [year, month, day] = baseDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, (month ?? 1) - 1, day ?? 1));
  date.setUTCMonth(date.getUTCMonth() - 1);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC" }).format(date);
};

const getMonthKey = (date: string) => date.slice(0, 7);

const getDateKeysBetween = (startDate: string, endDate: string) => {
  const start = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];
  const keys: string[] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    keys.push(new Intl.DateTimeFormat("sv-SE", { timeZone: "UTC" }).format(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return keys;
};

const buildMonthlyThemeTreemapItems = (
  monthlyResponses: MonthlyThemeFlowTrendResponse[],
  startDate: string,
  endDate: string,
  viewMode: ThemeFlowViewMode,
): MonthlyThemeTreemapItem[] => {
  const map = new Map<number, Omit<MonthlyThemeTreemapItem, "rank">>();
  monthlyResponses.forEach((response) => {
    (response.themes ?? []).forEach((theme) => {
      const current = map.get(theme.market_theme_id) ?? {
        marketThemeId: theme.market_theme_id,
        themeName: theme.theme_name,
        viewMode,
        themeGroupId: theme.theme_group_id ?? null,
        themeGroupName: theme.theme_group_name ?? null,
        childThemeCount: theme.child_theme_count ?? 0,
        topChildThemes: theme.top_child_themes ?? [],
        scoreSum: 0,
        stockCount: 0,
        eventCount: 0,
        relatedStocks: theme.related_stocks ?? [],
        sourceDates: [],
        latestDate: null,
        supplyValueSum: 0,
        latestFinalRank: null,
      };
      current.viewMode = viewMode;
      current.themeGroupId = theme.theme_group_id ?? current.themeGroupId;
      current.themeGroupName = theme.theme_group_name ?? current.themeGroupName;
      current.childThemeCount = Math.max(current.childThemeCount, theme.child_theme_count ?? 0);
      current.topChildThemes = Array.from(new Set([...current.topChildThemes, ...(theme.top_child_themes ?? [])])).slice(0, 3);
      current.relatedStocks = Array.from(new Set([...current.relatedStocks, ...(theme.related_stocks ?? [])])).slice(0, 8);
      theme.series
        .filter((point) => point.trade_date >= startDate && point.trade_date <= endDate)
        .forEach((point) => {
          const dailyScore = Number(point.daily_score || 0);
          if (dailyScore <= 0) return;
          current.scoreSum += dailyScore;
          current.stockCount = Math.max(current.stockCount, Number(point.stock_count || 0));
          current.eventCount += Number(point.event_count || 0);
          current.supplyValueSum += Number(point.estimated_trading_value_sum || 0);
          current.sourceDates.push(point.trade_date);
          if (!current.latestDate || point.trade_date > current.latestDate) {
            current.latestDate = point.trade_date;
            current.latestFinalRank = point.final_rank;
          }
        });
      map.set(theme.market_theme_id, current);
    });
  });

  return Array.from(map.values())
    .filter((item) => item.scoreSum > 0)
    .sort((a, b) => b.scoreSum - a.scoreSum || a.themeName.localeCompare(b.themeName, "ko"))
    .map((item, idx) => ({
      ...item,
      sourceDates: Array.from(new Set(item.sourceDates)).sort(),
      rank: idx + 1,
    }));
};

const getThemeTreemapSizeClass = (item: MonthlyThemeTreemapItem, maxScore: number) => {
  const ratio = maxScore > 0 ? item.scoreSum / maxScore : 0;
  if (item.rank === 1 || ratio >= 0.72) return "large";
  if (item.rank <= 5 || ratio >= 0.36) return "medium";
  if (ratio >= 0.15) return "small";
  return "tiny";
};
const buildCalendarCells = (month: string, days: MonthlyThemeFlowCalendarDay[]) => {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const last = new Date(y, m, 0);
  const offset = first.getDay();
  const cells: Array<{ date: string | null; day: MonthlyThemeFlowCalendarDay | null }> = [];
  for (let i = 0; i < offset; i += 1) cells.push({ date: null, day: null });
  const map = Object.fromEntries(days.map((d) => [d.trade_date, d] as const));
  for (let d = 1; d <= last.getDate(); d += 1) {
    const key = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({ date: key, day: map[key] ?? null });
  }
  while (cells.length % 7 !== 0) cells.push({ date: null, day: null });
  return cells;
};

function MarketTrendsPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<ActiveTab>("kiwoom");

  const [conditions, setConditions] = useState<KiwoomConditionItem[]>([]);
  const [selectedConditionSeq, setSelectedConditionSeq] = useState("");
  const [selectedConditionName, setSelectedConditionName] = useState("");
  const [results, setResults] = useState<KiwoomConditionResultItem[]>([]);
  const [checkedMap, setCheckedMap] = useState<Record<string, boolean>>({});

  const [events, setEvents] = useState<KiwoomMarketEventItem[]>([]);
  const [eventThemeLinksMap, setEventThemeLinksMap] = useState<Record<number, MarketEventThemeLink[]>>({});
  const [eventDrafts, setEventDrafts] = useState<Record<number, { theme_status: string; user_memo: string; selected_theme_id: string }>>({});
  const [eventThemeSearchMap, setEventThemeSearchMap] = useState<Record<number, string>>({});
  const [existingThemePopoverEventId, setExistingThemePopoverEventId] = useState<number | null>(null);
  const [marketThemes, setMarketThemes] = useState<MarketTrendThemeOption[]>([]);

  const [tradeDate, setTradeDate] = useState(() => todayInKst());
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [resultPanelStatus, setResultPanelStatus] = useState("");
  const [conditionsRefreshing, setConditionsRefreshing] = useState(false);

  const [conditionOrderMode, setConditionOrderMode] = useState<ConditionOrderMode>("number");
  const [resultSort, setResultSort] = useState<{ key: ResultSortKey; order: SortOrder }>({ key: "change_rate", order: "desc" });

  const [flowSummaries, setFlowSummaries] = useState<DailyThemeFlowSummary[]>([]);
  const [flowStocks, setFlowStocks] = useState<DailyThemeFlowStock[]>([]);
  const [selectedFlowTheme, setSelectedFlowTheme] = useState<{ id: number; name: string } | null>(null);
  const [flowLoading, setFlowLoading] = useState(false);
  const [flowStocksLoading, setFlowStocksLoading] = useState(false);
  const [rankEditMode, setRankEditMode] = useState(false);
  const [rankDraftMap, setRankDraftMap] = useState<Record<number, string>>({});
  const [rankDraftItems, setRankDraftItems] = useState<DailyThemeFlowSummary[]>([]);
  const [draggingThemeId, setDraggingThemeId] = useState<number | null>(null);
  const [flowRankInfoOpen, setFlowRankInfoOpen] = useState(false);
  const [chartSidcode, setChartSidcode] = useState<number>(createNaverChartSidcode());
  const [brokenCharts, setBrokenCharts] = useState<Record<string, boolean>>({});
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string } | null>(null);
  const [monthlyBaseMonth, setMonthlyBaseMonth] = useState<string>(getMonthInput());
  const [monthlyCalendarDays, setMonthlyCalendarDays] = useState<MonthlyThemeFlowCalendarDay[]>([]);
  const [monthlySummary30d, setMonthlySummary30d] = useState<MonthlySupplySummary30d | null>(null);
  const [topStockReturnTrend, setTopStockReturnTrend] = useState<SupplyTopStockReturnTrendResponse | null>(null);
  const [topStockReturnLoading, setTopStockReturnLoading] = useState(false);
  const [topStockReturnError, setTopStockReturnError] = useState("");
  const [topStockPriceCollecting, setTopStockPriceCollecting] = useState(false);
  const [topStockPriceCollectionMessage, setTopStockPriceCollectionMessage] = useState("");
  const [monthlyTrendResponses, setMonthlyTrendResponses] = useState<MonthlyThemeFlowTrendResponse[]>([]);
  const [selectedMonthlyTreemapId, setSelectedMonthlyTreemapId] = useState<number | null>(null);
  const [monthlyTreemapTooltip, setMonthlyTreemapTooltip] = useState<{ x: number; y: number; item: MonthlyThemeTreemapItem; share: number } | null>(null);
  const [monthlyTrendViewMode, setMonthlyTrendViewMode] = useState<ThemeFlowViewMode>("THEME");
  const [monthlyThemeFlowView, setMonthlyThemeFlowView] = useState<MonthlyThemeFlowView>("heatmap");
  const [monthlyStartDate, setMonthlyStartDate] = useState<string>("");
  const [monthlyEndDate, setMonthlyEndDate] = useState<string>("");
  const [selectedMonthlyDate, setSelectedMonthlyDate] = useState<string>("");
  const [selectedDayDetailTab, setSelectedDayDetailTab] = useState<SelectedDayDetailTab>("themes");
  const [monthlyLoading, setMonthlyLoading] = useState<boolean>(false);
  const monthlyRequestIdRef = useRef(0);
  const monthlyRecentTrendKeyRef = useRef("");
  const topStockReturnPeriodKeyRef = useRef("");
  const topStockReturnRequestIdRef = useRef(0);
  const monthlyBaseMonthRef = useRef(monthlyBaseMonth);
  const monthlyApplyMonthRef = useRef<(nextMonth: string) => Promise<boolean>>(async () => false);
  const [eventNameSortOrder, setEventNameSortOrder] = useState<SortOrder>("asc");
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [manualStockKeyword, setManualStockKeyword] = useState("");
  const [manualStockResults, setManualStockResults] = useState<Stock[]>([]);
  const [manualSelectedStock, setManualSelectedStock] = useState<Stock | null>(null);
  const [manualStockLoading, setManualStockLoading] = useState(false);
  const [manualSaving, setManualSaving] = useState(false);
  const [selectedTrackingCandidateIds, setSelectedTrackingCandidateIds] = useState<number[]>([]);
  const [trackingGroups, setTrackingGroups] = useState<StockTrackingGroup[]>([]);
  const [trackingRegisterOpen, setTrackingRegisterOpen] = useState(false);
  const [trackingRegisterSource, setTrackingRegisterSource] = useState<TrackingRegisterSource>("saved-candidates");
  const [trackingGroupId, setTrackingGroupId] = useState("");
  const [trackingRegisterSaving, setTrackingRegisterSaving] = useState(false);
  const [trackingRegisterCompleted, setTrackingRegisterCompleted] = useState(false);
  const [manualForm, setManualForm] = useState<ManualCandidateForm>({
    trade_date: tradeDate,
    change_rate: "",
    trading_value: "",
    volume: "",
    theme_id: "",
    memo: "",
  });

  const toggleSort = <T extends string,>(prev: { key: T; order: SortOrder }, key: T): { key: T; order: SortOrder } => {
    if (prev.key === key) {
      return { key, order: prev.order === "asc" ? "desc" : "asc" };
    }
    return { key, order: "asc" };
  };

  const sortedConditions = useMemo(() => {
    const arr = [...conditions];
    arr.sort((a, b) => {
      if (conditionOrderMode === "name") {
        return a.condition_name.localeCompare(b.condition_name, "ko");
      }
      const aNum = Number(a.condition_seq);
      const bNum = Number(b.condition_seq);
      const aNumOk = Number.isFinite(aNum);
      const bNumOk = Number.isFinite(bNum);
      if (aNumOk && bNumOk) return aNum - bNum;
      return a.condition_seq.localeCompare(b.condition_seq, "ko");
    });
    return arr;
  }, [conditions, conditionOrderMode]);

  const sortedResults = useMemo(() => {
    const arr = [...results];
    arr.sort((a, b) => {
      const num = (v: number | null | undefined) => (v == null ? Number.NEGATIVE_INFINITY : v);
      let cmp = 0;
      switch (resultSort.key) {
        case "stock_code": cmp = (a.stock_code || "").localeCompare(b.stock_code || ""); break;
        case "stock_name": cmp = (a.stock_name || "").localeCompare(b.stock_name || "", "ko"); break;
        case "current_price": cmp = num(a.current_price) - num(b.current_price); break;
        case "change_rate": cmp = num(a.change_rate) - num(b.change_rate); break;
        case "volume": cmp = num(a.volume) - num(b.volume); break;
        case "estimated_trading_value": cmp = num(estimatedTradingValue(a)) - num(estimatedTradingValue(b)); break;
      }
      return resultSort.order === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [results, resultSort]);

  const selectedItems = useMemo(() => sortedResults.filter((r) => checkedMap[getResultRowKey(r)]), [checkedMap, sortedResults]);
  const selectedConditionLabel = selectedConditionSeq ? `${selectedConditionSeq} / ${selectedConditionName}` : "조건식을 선택해 주세요.";
  const conditionResultMeta = selectedConditionSeq
    ? resultPanelStatus.includes("조회 중")
      ? resultPanelStatus
      : `조회 결과 ${sortedResults.length}건 / 선택 ${selectedItems.length}건`
    : "조건식을 선택하면 결과를 조회할 수 있습니다.";
  const allResultChecked = useMemo(
    () => sortedResults.length > 0 && sortedResults.every((r) => Boolean(checkedMap[getResultRowKey(r)])),
    [sortedResults, checkedMap],
  );
  const sortedEvents = useMemo(() => {
    const arr = [...events];
    arr.sort((a, b) => {
      const cmp = (a.stock_name || "").localeCompare(b.stock_name || "", "ko");
      return eventNameSortOrder === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [events, eventNameSortOrder]);
  const selectedTrackingCandidateSet = useMemo(() => new Set(selectedTrackingCandidateIds), [selectedTrackingCandidateIds]);
  const allTrackingCandidatesChecked = useMemo(
    () => sortedEvents.length > 0 && sortedEvents.every((item) => selectedTrackingCandidateSet.has(item.event_id)),
    [sortedEvents, selectedTrackingCandidateSet],
  );
  const flowSummaryStats = useMemo(() => {
    const top = flowSummaries[0];
    const maxChange = flowSummaries.reduce((max, item) => {
      const value = item.max_change_rate ?? Number.NEGATIVE_INFINITY;
      return value > max ? value : max;
    }, Number.NEGATIVE_INFINITY);
    return {
      savedCandidates: flowSummaries.reduce((sum, item) => sum + (item.event_count ?? 0), 0),
      themeCount: flowSummaries.length,
      topTheme: top?.theme_name ?? "없음",
      maxChangeRate: Number.isFinite(maxChange) ? maxChange : null,
      unclassified: "-",
    };
  }, [flowSummaries]);
  const visibleFlowSummaries = rankEditMode ? rankDraftItems : flowSummaries;
  const selectedThemeMeta = useMemo(() => {
    if (!selectedFlowTheme) return null;
    const summary = flowSummaries.find((x) => x.market_theme_id === selectedFlowTheme.id);
    const stockCount = flowStocks.length;
    const rep = summary?.representative_stocks?.[0] ?? "-";
    return { stockCount, representative: rep };
  }, [selectedFlowTheme, flowSummaries, flowStocks]);
  const sortMark = (active: boolean, order: SortOrder) => (active ? (order === "asc" ? " ▲" : " ▼") : "");

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExistingThemePopoverEventId(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const loadConditions = async () => {
    setError("");
    try {
      const res = await repositories.marketTrends.getKiwoomConditions();
      const fresh = Array.isArray(res.items) ? [...res.items] : [];
      setConditions(fresh);
      if (fresh.length === 0) {
        setSelectedConditionSeq("");
        setSelectedConditionName("");
        return;
      }
      const keep = fresh.find((x) => x.condition_seq === selectedConditionSeq);
      if (keep) {
        setSelectedConditionName(keep.condition_name);
        return;
      }
      setSelectedConditionSeq(fresh[0].condition_seq);
      setSelectedConditionName(fresh[0].condition_name);
    } catch (e) {
      setError(toErr(e, "조건검색 목록을 불러오지 못했습니다."));
    }
  };

  const refreshConditions = async () => {
    setError("");
    setMessage("");
    setConditionsRefreshing(true);
    try {
      const sync = await repositories.marketTrends.refreshKiwoomConditions();
      await loadConditions();
      if (!sync.success || sync.condition_count <= 0) {
        setError(
          sync.message || "조건검색 목록 응답은 받았지만 조건식 목록을 파싱하지 못했습니다.",
        );
        return;
      }
      setMessage(
        `조건검색 목록 갱신 완료: condition_count ${sync.condition_count}, inserted ${sync.inserted}, updated ${sync.updated}, total ${sync.total}`,
      );
    } catch (e) {
      setError(toErr(e, "조건검색 목록 새로고침에 실패했습니다. Kiwoom REST 토큰/연결 상태를 확인해 주세요."));
    } finally {
      setConditionsRefreshing(false);
    }
  };

  const loadConditionResults = async () => {
    if (!selectedConditionSeq) {
      setError("조건식을 먼저 선택해 주세요.");
      return;
    }
    setError("");
    setResultPanelStatus("조건검색 결과 조회 중...");
    try {
      const res = await repositories.marketTrends.previewKiwoomConditionResults(selectedConditionSeq, {
        condition_name: selectedConditionName || null,
        header_mode: "auth-only",
        login_mode: "message-token",
        search_type: "0",
        stex_tp: "K",
      });
      setResults(res.items ?? []);
      setCheckedMap({});
      if (res.parsing_error) {
        setResultPanelStatus("");
        setError("조건검색 응답은 수신했지만 결과 종목을 해석하지 못했습니다.");
      } else if ((res.item_count ?? 0) === 0) setResultPanelStatus("조회 결과 0건 · 선택 0건");
      else setResultPanelStatus(`조회 결과 ${res.item_count}건 · 선택 0건`);
    } catch (e) {
      setResultPanelStatus("");
      setError(toErr(e, "조건검색 결과 조회에 실패했습니다. Kiwoom REST 연결 상태를 확인해 주세요."));
    }
  };

  const saveSelectedAsEvents = async () => {
    if (!selectedConditionSeq) {
      setError("조건식을 먼저 선택해 주세요.");
      return;
    }
    if (selectedItems.length === 0) {
      setError("수급 이벤트 후보로 저장할 종목을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const res = await repositories.marketTrends.saveKiwoomMarketEvents({
        condition_seq: selectedConditionSeq,
        condition_name: selectedConditionName,
        detected_date: tradeDate,
        source: "kiwoom_rest",
        items: selectedItems,
      });
      setMessage("수급 이벤트 후보로 저장되었습니다.");
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 저장에 실패했습니다."));
    }
  };

  const buildIssueSummaryPrompt = () => {
    const hasSelected = selectedItems.length > 0;
    const sourceRows = hasSelected ? selectedItems : sortedResults;
    if (sourceRows.length === 0) return "";
    const limitedRows = hasSelected ? sourceRows : sourceRows.slice(0, 30);
    const selectedKeys = new Set(selectedItems.map((row) => getResultRowKey(row)));
    const conditionLabel = selectedConditionSeq
      ? `${selectedConditionSeq}${selectedConditionName ? ` · ${selectedConditionName}` : ""}`
      : selectedConditionName || "-";
    const limitNotice = !hasSelected && sourceRows.length > limitedRows.length
      ? `\n※ 조건검색 결과가 많아 상위 ${limitedRows.length}개 종목만 포함했습니다. 필요한 종목은 체크 후 다시 복사하세요.\n`
      : "";
    const tableRows = limitedRows
      .map((row, index) => {
        const selectedLabel = selectedKeys.has(getResultRowKey(row)) ? "선택" : "-";
        return `| ${index + 1} | ${escapeMarkdownCell(row.stock_name || "-")} | ${escapeMarkdownCell(normalizeStockCode(row.stock_code) || row.stock_code || "-")} | ${escapeMarkdownCell(getConditionResultMarket(row))} | ${escapeMarkdownCell(fmtNumber(row.current_price))} | ${escapeMarkdownCell(fmtPct(row.change_rate))} | ${escapeMarkdownCell(fmtNumber(row.volume))} | ${escapeMarkdownCell(fmtEok2(estimatedTradingValue(row)))} | ${selectedLabel} |`;
      })
      .join("\n");

    return `[DrCT에셋 조건검색 결과 오늘 이슈 정리 요청]

당신은 종목 추천자가 아니라, 당일 조건검색에 포착된 종목들이 어떤 이슈로 시장의 관심을 받았는지 정리하는 분석 보조자입니다.

아래 종목들은 오늘 키움 조건검색식에 포착된 종목입니다.
각 종목이 오늘 주목받은 이유를 뉴스, 공시, 테마, 수급, 업종 이슈 관점에서 확인해 주세요.

주의사항:
- 매수·매도 추천은 하지 마세요.
- 목표가를 제시하지 마세요.
- 확인되지 않은 내용을 단정하지 마세요.
- 오늘 이슈가 명확하지 않으면 “확인 필요”라고 표시하세요.
- 같은 테마로 묶이는 종목은 테마를 통일해서 정리해 주세요.
- 결과는 표로 작성해 주세요.

정리할 표 컬럼:
1. 순번
2. 종목명
3. 종목코드
4. 등락률
5. 거래대금
6. 추정 테마
7. 오늘 주목받은 이슈
8. 근거 유형
9. 이슈 강도
10. 확인 필요 사항
11. DrCT 후보 판단 메모

이슈 강도 기준:
- 높음: 당일 뉴스·공시·정책·수주·실적·테마 확산이 명확하고 거래대금도 큰 경우
- 중간: 테마 또는 업종 흐름은 있으나 개별 기업 이슈가 약한 경우
- 낮음: 단순 동반 상승, 기술적 반등, 명확한 뉴스 부족
- 확인 필요: 현재 정보만으로 이유를 특정하기 어려운 경우

근거 유형은 다음 중 하나 이상으로 표시하세요.
- 뉴스
- 공시
- 정책
- 테마
- 수급
- 업종
- 실적
- 수주/계약
- 단순 급등
- 확인 필요

조건식명:
${conditionLabel}

조회일:
${tradeDate || todayInKst()}
${limitNotice}
종목 목록:
| 순번 | 종목명 | 종목코드 | 시장 | 현재가 | 등락률 | 거래량 | 거래대금(억) | 선택 여부 |
|---|---|---|---|---:|---:|---:|---:|---|
${tableRows}

추가 요청:
위 종목별 이슈 정리를 마친 뒤, 마지막에는 전체 종목을 상위 테마로 압축해서 다시 정리해 주세요.

상위 테마 압축 기준:
- 너무 세부적인 키워드로 쪼개지 말고, 시장에서 실제로 묶어서 볼 수 있는 큰 흐름으로 정리해 주세요.
- 유사한 이슈는 하나의 상위 테마로 묶어 주세요.
- 가능한 경우 6~8개 이내의 상위 테마로 압축해 주세요.
- 각 상위 테마별로 포함 종목을 함께 적어 주세요.
- 특정 테마로 묶기 어려운 종목은 “개별 이슈”로 분류해 주세요.
- 확인되지 않은 테마는 단정하지 말고 “확인 필요”로 표시해 주세요.

상위 테마 압축 표 컬럼:
1. 상위 테마
2. 포함 종목
3. 핵심 이슈 요약
4. 테마 강도
5. 확인 필요 사항

상위 테마 예시:
| 상위 테마 | 포함 종목 | 핵심 이슈 요약 | 테마 강도 | 확인 필요 사항 |
|---|---|---|---|---|
| AI 반도체 | SK하이닉스, 제주반도체, 파두 | AI 반도체와 HBM 관련 기대감으로 묶이는 종목군 | 높음 | 실제 개별 뉴스·공시 확인 |
| 반도체 장비·부품 | 피에스케이, 테스, 원익IPS | 반도체 장비 및 부품 수요 기대와 연결되는 종목군 | 중간 | 당일 상승 원인 확인 |
| 유리기판 | 제이앤티씨 | 유리기판 관련 시장 관심 종목 | 중간 | 구체 뉴스 확인 |
| AI 인프라·로봇 | LG전자, LG씨엔에스 | AI 인프라 또는 로봇 관련 기대감으로 분류 가능 | 중간 | 실제 사업 연결성 확인 |
| 지분가치·벌크업 | SK스퀘어, 삼성물산 | 지분가치 또는 그룹 구조 변화 기대감과 연결 가능 | 중간 | 구체 촉매 확인 |
| 개별 이슈 | 카카오게임즈, 현대약품 | 공통 테마보다 개별 뉴스 또는 개별 수급 확인이 필요한 종목 | 확인 필요 | 종목별 뉴스 확인 |
`;
  };

  const copyTextToClipboard = async (text: string) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(textarea);
    if (!copied) throw new Error("clipboard_copy_failed");
  };

  const copyIssueSummaryPrompt = async () => {
    const prompt = buildIssueSummaryPrompt();
    if (!prompt) {
      setError("복사할 조건검색 결과가 없습니다.");
      return;
    }
    setError("");
    try {
      await copyTextToClipboard(prompt);
      const targetCount = selectedItems.length > 0 ? selectedItems.length : Math.min(sortedResults.length, 30);
      setMessage(`GPT 이슈정리 요청문이 복사되었습니다. ${targetCount}개 종목을 GPT에 붙여넣어 오늘의 이슈를 표로 정리하세요.`);
    } catch (e) {
      setError(toErr(e, "클립보드 복사에 실패했습니다. 다시 시도해 주세요."));
    }
  };
  const loadEvents = async (targetDate?: string) => {
    setError("");
    try {
      const baseDate = targetDate || tradeDate;
      const res = await repositories.marketTrends.getKiwoomMarketEvents(baseDate, 200);
      const fetchedEvents = [...(res.items ?? [])];
      setEvents(fetchedEvents);
      const draftMap: Record<number, { theme_status: string; user_memo: string; selected_theme_id: string }> = {};
      for (const item of fetchedEvents) {
        draftMap[item.event_id] = {
          theme_status: item.theme_status || "unassigned",
          user_memo: item.user_memo || "",
          selected_theme_id: "",
        };
      }
      setSelectedTrackingCandidateIds([]);
      setEventDrafts(draftMap);
      setEventThemeSearchMap(Object.fromEntries(fetchedEvents.map((item) => [item.event_id, ""])));

      const linkEntries = await Promise.all(
        fetchedEvents.map(async (item) => {
          const linkRes = await repositories.marketTrends.getKiwoomMarketEventThemes(item.event_id);
          return [item.event_id, linkRes.items] as const;
        }),
      );
      setEventThemeLinksMap(Object.fromEntries(linkEntries));
    } catch (e) {
      setError(toErr(e, "저장된 수급 이벤트 후보를 불러오지 못했습니다."));
    }
  };

  const loadMarketThemes = async () => {
    try {
      const items = await repositories.marketThemes.list({ is_active: 1, theme_level: "THEME", limit: 500 });
      const sortedItems = [...items].sort((a, b) => {
        const aRate = a.latest_return?.avg_change_rate ?? Number.NEGATIVE_INFINITY;
        const bRate = b.latest_return?.avg_change_rate ?? Number.NEGATIVE_INFINITY;
        if (aRate !== bRate) return bRate - aRate;
        return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      });
      setMarketThemes(sortedItems.map((x) => ({ id: x.id, theme_name: x.theme_name, latest_return: x.latest_return ?? null })));
    } catch {
      setMarketThemes([]);
    }
  };

  const toggleTrackingCandidate = (eventId: number, checked: boolean) => {
    setSelectedTrackingCandidateIds((prev) => {
      if (checked) return prev.includes(eventId) ? prev : [...prev, eventId];
      return prev.filter((id) => id !== eventId);
    });
  };

  const toggleAllTrackingCandidates = (checked: boolean) => {
    setSelectedTrackingCandidateIds(checked ? sortedEvents.map((item) => item.event_id) : []);
  };

  const loadActiveTrackingGroupsForModal = async () => {
    const rows = await repositories.stockTracking.listGroups({ active_only: true });
    setTrackingGroups(rows);
    setTrackingGroupId(rows[0] ? String(rows[0].id) : "");
    setTrackingRegisterOpen(true);
  };

  const openTrackingRegisterModal = async () => {
    if (selectedTrackingCandidateIds.length === 0) {
      setError("종목트래킹에 등록할 후보를 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setTrackingRegisterSource("saved-candidates");
    setTrackingRegisterCompleted(false);
    await loadActiveTrackingGroupsForModal();
  };

  const openConditionResultTrackingRegisterModal = async () => {
    if (selectedItems.length === 0) {
      setError("종목트래킹에 등록할 조건검색 결과 종목을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setTrackingRegisterSource("condition-results");
    setTrackingRegisterCompleted(false);
    await loadActiveTrackingGroupsForModal();
  };
  const registerTrackingCandidates = async () => {
    if (!trackingGroupId) {
      setError("등록할 그룹을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setTrackingRegisterSaving(true);
    try {
      const groupId = Number(trackingGroupId);
      if (trackingRegisterSource === "condition-results") {
        const res = await repositories.stockTracking.registerFromConditionResults({
          group_id: groupId,
          condition_no: selectedConditionSeq || null,
          condition_name: selectedConditionName || null,
          detected_date: tradeDate || todayInKst(),
          items: selectedItems.map((row) => {
            const market = getConditionResultMarket(row);
            return {
              stock_code: normalizeStockCode(row.stock_code) || row.stock_code,
              stock_name: row.stock_name ?? null,
              market: market === "-" ? null : market,
              current_price: row.current_price ?? null,
              change_rate: row.change_rate ?? null,
              volume: row.volume ?? null,
              trading_value: estimatedTradingValue(row),
            };
          }),
        });
        setMessage(res.message || `조건검색 결과에서 선택한 종목을 종목트래킹에 등록했습니다. 신규 ${res.created_count}건, 중복 ${res.skipped_count}건`);
        setCheckedMap({});
      } else {
        const res = await repositories.stockTracking.registerFromCandidates({
          group_id: groupId,
          candidate_ids: selectedTrackingCandidateIds,
        });
        setMessage(res.message || `종목트래킹 등록 완료: 신규 ${res.created_count}건, 중복 제외 ${res.skipped_count}건`);
        setSelectedTrackingCandidateIds([]);
      }
      setTrackingRegisterCompleted(true);
      setTrackingRegisterOpen(false);
    } catch (e) {
      setError(toErr(e, "종목트래킹 등록에 실패했습니다."));
    } finally {
      setTrackingRegisterSaving(false);
    }
  };
  const openManualCandidateModal = () => {
    setManualModalOpen(true);
    setManualStockKeyword("");
    setManualStockResults([]);
    setManualSelectedStock(null);
    setManualForm({
      trade_date: tradeDate,
      change_rate: "",
      trading_value: "",
      volume: "",
      theme_id: "",
      memo: "",
    });
  };

  const searchManualCandidateStocks = async () => {
    const keyword = manualStockKeyword.trim();
    if (!keyword) {
      setError("종목명 또는 종목코드를 입력해 주세요.");
      return;
    }
    setError("");
    setManualStockLoading(true);
    try {
      const rows = await repositories.stocks.list({ keyword, is_active: 1, limit: 20, offset: 0 });
      setManualStockResults(rows);
      if (rows.length === 0) setError("검색 결과가 없습니다. 종목명 또는 종목코드를 다시 확인해 주세요.");
    } catch (e) {
      setError(toErr(e, "종목 검색에 실패했습니다."));
      setManualStockResults([]);
    } finally {
      setManualStockLoading(false);
    }
  };

  const saveManualCandidate = async () => {
    if (!manualSelectedStock) {
      setError("직접등록할 종목을 선택해 주세요.");
      return;
    }
    if (!manualForm.trade_date) {
      setError("감지일을 선택해 주세요.");
      return;
    }
    const toOptionalNumber = (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) return null;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : Number.NaN;
    };
    const changeRate = toOptionalNumber(manualForm.change_rate);
    const tradingValue = toOptionalNumber(manualForm.trading_value);
    const volume = toOptionalNumber(manualForm.volume);
    if (Number.isNaN(changeRate) || Number.isNaN(tradingValue) || Number.isNaN(volume)) {
      setError("등락률, 거래대금, 거래량은 숫자로 입력해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setManualSaving(true);
    try {
      const res = await repositories.marketTrends.createManualSupplyEventCandidate({
        trade_date: manualForm.trade_date,
        stock_id: manualSelectedStock.id,
        stock_code: manualSelectedStock.stock_code,
        change_rate: changeRate,
        trading_value: tradingValue == null ? null : Math.round(tradingValue),
        volume: volume == null ? null : Math.round(volume),
        theme_id: manualForm.theme_id ? Number(manualForm.theme_id) : null,
        memo: manualForm.memo.trim(),
      });
      setMessage(res.message || "수급 이벤트 후보를 직접 등록했습니다.");
      setManualModalOpen(false);
      setTradeDate(manualForm.trade_date);
      await Promise.all([loadEvents(manualForm.trade_date), loadFlow(manualForm.trade_date)]);
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 직접등록에 실패했습니다."));
    } finally {
      setManualSaving(false);
    }
  };

  const saveEventNote = async (eventId: number) => {
    const draft = eventDrafts[eventId];
    if (!draft) return;
    setError("");
    setMessage("");
    try {
      const res = await repositories.marketTrends.updateKiwoomMarketEvent(eventId, {
        theme_status: draft.theme_status,
        user_memo: draft.user_memo,
      });
      setMessage(`메모 저장 완료: event_id=${res.item.event_id}`);
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "메모 저장에 실패했습니다."));
    }
  };

  const applyExistingTheme = (eventId: number, theme: ExistingMarketEventTheme) => {
    setExistingThemePopoverEventId(null);
    setEventThemeSearchMap((prev) => ({ ...prev, [eventId]: theme.theme_name }));
    setEventDrafts((prev) => ({
      ...prev,
      [eventId]: {
        ...(prev[eventId] ?? { theme_status: "unassigned", user_memo: "", selected_theme_id: "" }),
        selected_theme_id: String(theme.theme_id),
      },
    }));
  };

  const addThemeLink = async (eventId: number, searchTextOverride?: string) => {
    const draft = eventDrafts[eventId];
    const searchText = (searchTextOverride ?? eventThemeSearchMap[eventId] ?? "").trim();
    const normalizedSearchText = searchText.toLowerCase();
    const selectedTheme = draft?.selected_theme_id
      ? marketThemes.find((theme) => String(theme.id) === draft.selected_theme_id)
      : null;
    const matchedTheme = selectedTheme
      ?? marketThemes.find((theme) => theme.theme_name === searchText)
      ?? marketThemes.find((theme) => theme.theme_name.toLowerCase() === normalizedSearchText);

    if (!matchedTheme) {
      setError("\uCD94\uAC00 \uC5F0\uACB0\uD560 \uD14C\uB9C8\uB97C \uC120\uD0DD\uD574 \uC8FC\uC138\uC694. \uD14C\uB9C8\uBA85 \uC77C\uBD80\uB97C \uC785\uB825\uD55C \uB4A4 \uBAA9\uB85D\uC5D0\uC11C \uD14C\uB9C8\uB97C \uC120\uD0DD\uD574\uC57C \uD569\uB2C8\uB2E4.");
      return;
    }

    setError("");
    setMessage("");
    try {
      const payload: AddMarketEventThemeLinkRequest = {
        market_theme_id: matchedTheme.id,
        user_memo: draft?.user_memo || null,
      };
      await repositories.marketTrends.addKiwoomMarketEventTheme(eventId, payload);
      const links = await repositories.marketTrends.getKiwoomMarketEventThemes(eventId);
      setEventThemeLinksMap((prev) => ({ ...prev, [eventId]: links.items }));
      setEventDrafts((prev) => ({
        ...prev,
        [eventId]: {
          ...(prev[eventId] ?? { theme_status: "unassigned", user_memo: "", selected_theme_id: "" }),
          selected_theme_id: "",
        },
      }));
      setEventThemeSearchMap((prev) => ({ ...prev, [eventId]: "" }));
      await loadFlow();
      setMessage("\uD14C\uB9C8\uB97C \uCD94\uAC00 \uC5F0\uACB0\uD588\uC2B5\uB2C8\uB2E4.");
    } catch (e) {
      setError(toErr(e, "\uD14C\uB9C8 \uCD94\uAC00 \uC5F0\uACB0\uC5D0 \uC2E4\uD328\uD588\uC2B5\uB2C8\uB2E4."));
    }
  };

  const removeThemeLink = async (eventId: number, linkId: number) => {
    setError("");
    setMessage("");
    try {
      await repositories.marketTrends.removeKiwoomMarketEventTheme(eventId, linkId);
      const links = await repositories.marketTrends.getKiwoomMarketEventThemes(eventId);
      setEventThemeLinksMap((prev) => ({ ...prev, [eventId]: links.items }));
      await loadFlow();
      setMessage("테마 연결을 해제했습니다.");
    } catch (e) {
      setError(toErr(e, "테마 연결 해제에 실패했습니다."));
    }
  };

  const deleteEvent = async (eventId: number) => {
    const ok = window.confirm("이 수급 이벤트 후보를 삭제하시겠습니까? 연결된 테마 기록도 함께 해제될 수 있습니다.");
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      await repositories.marketTrends.deleteKiwoomMarketEvent(eventId);
      setMessage(`삭제 완료: event_id=${eventId}`);
      await Promise.all([loadEvents(), loadFlow()]);
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 삭제에 실패했습니다."));
    }
  };

  const loadFlow = async (targetDate?: string) => {
    setError("");
    setMessage("");
    setFlowLoading(true);
    setSelectedFlowTheme(null);
    setFlowStocks([]);
    try {
      const baseDate = targetDate || tradeDate;
      const res = await repositories.marketTrends.getExternalDailyThemeFlow(baseDate);
      const items = res.items ?? [];
      setFlowSummaries(items);
      setRankDraftItems(items);
      setRankDraftMap(
        Object.fromEntries(items.map((x) => [x.market_theme_id, x.manual_rank != null ? String(x.manual_rank) : ""])),
      );
      if ((res.items ?? []).length === 0) setMessage("해당일에 테마가 연결된 수급 이벤트 후보가 없습니다.");
    } catch (e) {
      setError(toErr(e, "일별 테마 수급 흐름 조회에 실패했습니다."));
      setFlowSummaries([]);
    } finally {
      setFlowLoading(false);
    }
  };

  const loadFlowStocks = async (theme: DailyThemeFlowSummary) => {
    setSelectedFlowTheme({ id: theme.market_theme_id, name: theme.theme_name });
    setFlowStocksLoading(true);
    setChartSidcode(createNaverChartSidcode());
    setBrokenCharts({});
    try {
      const res = await repositories.marketTrends.getExternalDailyThemeFlowStocks(tradeDate, theme.market_theme_id);
      setFlowStocks(res.items ?? []);
    } catch (e) {
      setError(toErr(e, "선택 테마 상세 종목 조회에 실패했습니다."));
      setFlowStocks([]);
    } finally {
      setFlowStocksLoading(false);
    }
  };

  const onChartError = (key: string) => setBrokenCharts((prev) => ({ ...prev, [key]: true }));
  const applyFlowDate = async (nextDate: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(nextDate)) return;
    const parsed = new Date(nextDate);
    if (Number.isNaN(parsed.getTime())) return;
    setTradeDate(nextDate);
    await Promise.all([loadEvents(nextDate), loadFlow(nextDate)]);
  };

  const loadTopStockReturnTrend = async (periodStartDate: string, periodEndDate: string, force = false) => {
    const periodKey = `${periodStartDate}:${periodEndDate}`;
    if (!force && topStockReturnPeriodKeyRef.current === periodKey && topStockReturnTrend) return;
    const requestId = topStockReturnRequestIdRef.current + 1;
    topStockReturnRequestIdRef.current = requestId;
    setTopStockReturnLoading(true);
    setTopStockReturnError("");
    try {
      const response = await repositories.marketTrends.getSupplyTopStockReturnTrend(periodStartDate, periodEndDate, 20);
      if (requestId !== topStockReturnRequestIdRef.current) return;
      topStockReturnPeriodKeyRef.current = periodKey;
      setTopStockReturnTrend(response);
    } catch (e) {
      if (requestId !== topStockReturnRequestIdRef.current) return;
      setTopStockReturnError(toErr(e, "TOP20 종목 누적등락률 조회에 실패했습니다."));
    } finally {
      if (requestId === topStockReturnRequestIdRef.current) setTopStockReturnLoading(false);
    }
  };
  const refreshTopStockPrices = async () => {
    if (!topStockReturnTrend || topStockPriceCollecting) return;
    setTopStockPriceCollecting(true);
    setTopStockPriceCollectionMessage("");
    try {
      const result = await repositories.marketTrends.refreshSupplyTopStockPrices({
        period_start_date: topStockReturnTrend.period_start_date,
        period_end_date: topStockReturnTrend.period_end_date,
        limit: 20,
      });
      const summary = result.failed_count === 0
        ? `TOP20 가격 갱신이 완료되었습니다. 성공 ${result.success_count}종목`
        : `TOP20 가격 갱신 일부 완료: 성공 ${result.success_count}종목, 실패 ${result.failed_count}종목`;
      setTopStockPriceCollectionMessage(summary);
      await loadTopStockReturnTrend(result.period_start_date, result.period_end_date, true);
    } catch (e) {
      setTopStockPriceCollectionMessage(toErr(e, "TOP20 가격 갱신에 실패했습니다."));
    } finally {
      setTopStockPriceCollecting(false);
    }
  };
  const loadMonthlyFlow = async (
    targetMonth = monthlyBaseMonth,
    options: { refreshCalendar?: boolean; refreshRecentTrend?: boolean } = {},
  ): Promise<boolean> => {
    if (!targetMonth) {
      setError("기준 월(YYYY-MM)을 선택해 주세요.");
      return false;
    }
    const requestId = monthlyRequestIdRef.current + 1;
    monthlyRequestIdRef.current = requestId;
    const refreshCalendar = options.refreshCalendar ?? true;
    setError("");
    setMessage("");
    setMonthlyLoading(true);
    try {
      const today = todayInKst();
      const treemapStartDate = subtractOneMonth(today);
      const recentTrendKey = `${monthlyTrendViewMode}:${treemapStartDate}:${today}`;
      const refreshRecentTrend = options.refreshRecentTrend
        || monthlyRecentTrendKeyRef.current !== recentTrendKey;
      const [calendarRes, recentTrendRes] = await Promise.all([
        refreshCalendar
          ? repositories.marketTrends.getExternalMonthlyThemeFlowCalendar(targetMonth)
          : Promise.resolve(null),
        refreshRecentTrend
          ? repositories.marketTrends.getExternalMonthlyThemeFlowTrend(getMonthKey(today), {
            view_mode: monthlyTrendViewMode,
            start_date: treemapStartDate,
            end_date: today,
          })
          : Promise.resolve(null),
      ]);
      if (requestId !== monthlyRequestIdRef.current) return false;
      if (calendarRes) {
        setMonthlyCalendarDays(calendarRes.days ?? []);
        setMonthlySummary30d(calendarRes.summary_30d ?? null);
        setMonthlyStartDate(calendarRes.start_date);
        setMonthlyEndDate(calendarRes.end_date);
        setSelectedMonthlyDate(calendarRes.end_date);
        const summaryPeriod = calendarRes.summary_30d;
        void loadTopStockReturnTrend(summaryPeriod.period_start_date, summaryPeriod.period_end_date);
      }
      if (recentTrendRes) {
        monthlyRecentTrendKeyRef.current = recentTrendKey;
        setMonthlyTrendResponses([recentTrendRes]);
        setSelectedMonthlyTreemapId(null);
      }
      return true;
    } catch (e) {
      if (requestId !== monthlyRequestIdRef.current) return false;
      if (refreshCalendar) {
        setMonthlyCalendarDays([]);
        setMonthlySummary30d(null);
      }
      setError(toErr(e, "월간 테마 수급 흐름 조회에 실패했습니다."));
      return false;
    } finally {
      if (requestId === monthlyRequestIdRef.current) setMonthlyLoading(false);
    }
  };
  const applyMonthlyFlowMonth = async (nextMonth: string): Promise<boolean> => {
    if (!/^\d{4}-\d{2}$/.test(nextMonth)) return false;
    monthlyBaseMonthRef.current = nextMonth;
    setMonthlyBaseMonth(nextMonth);
    return loadMonthlyFlow(nextMonth);
  };
  monthlyApplyMonthRef.current = applyMonthlyFlowMonth;

  const selectMonthlyHeatmapDate = useCallback((date: string) => {
    const dateMonth = getMonthKey(date);
    if (dateMonth !== monthlyBaseMonthRef.current) {
      void monthlyApplyMonthRef.current(dateMonth).then((loaded) => {
        if (!loaded) return;
        setSelectedMonthlyDate(date);
        setSelectedDayDetailTab("themes");
      });
      return;
    }
    setSelectedMonthlyDate(date);
    setSelectedDayDetailTab("themes");
  }, []);
  const beginRankEdit = () => {
    if (flowSummaries.length === 0) return;
    setRankDraftItems(flowSummaries);
    setDraggingThemeId(null);
    setRankEditMode(true);
  };

  const cancelRankEdit = () => {
    setRankDraftItems(flowSummaries);
    setDraggingThemeId(null);
    setRankEditMode(false);
  };

  const moveRankDraftItem = (sourceId: number, targetId: number) => {
    if (sourceId === targetId) return;
    setRankDraftItems((prev) => {
      const sourceIndex = prev.findIndex((x) => x.market_theme_id === sourceId);
      const targetIndex = prev.findIndex((x) => x.market_theme_id === targetId);
      if (sourceIndex < 0 || targetIndex < 0) return prev;
      const next = [...prev];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
  };

  const handleRankDragStart = (event: DragEvent<HTMLButtonElement>, themeId: number) => {
    setDraggingThemeId(themeId);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(themeId));
  };

  const handleRankDragOver = (event: DragEvent<HTMLButtonElement>, targetId: number) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const raw = event.dataTransfer.getData("text/plain");
    const sourceId = Number(raw || draggingThemeId);
    if (Number.isFinite(sourceId)) moveRankDraftItem(sourceId, targetId);
  };

  const handleRankDrop = (event: DragEvent<HTMLButtonElement>, targetId: number) => {
    event.preventDefault();
    const sourceId = Number(event.dataTransfer.getData("text/plain") || draggingThemeId);
    if (Number.isFinite(sourceId)) moveRankDraftItem(sourceId, targetId);
    setDraggingThemeId(null);
  };

  const saveDailyRanks = async () => {
    const itemsToSave = rankDraftItems.length > 0 ? rankDraftItems : flowSummaries;
    if (itemsToSave.length === 0) return;
    setError("");
    try {
      const res = await repositories.marketTrends.updateDailyThemeRanks({
        trade_date: tradeDate,
        items: itemsToSave.map((x, index) => ({
          market_theme_id: x.market_theme_id,
          manual_rank: index + 1,
        })),
      });
      setFlowSummaries(res.items ?? []);
      setRankDraftItems(res.items ?? []);
      setRankDraftMap(
        Object.fromEntries((res.items ?? []).map((x) => [x.market_theme_id, x.manual_rank != null ? String(x.manual_rank) : ""])),
      );
      setMessage(`테마 순위를 저장했습니다. (${res.updated_count}건)`);
      setRankEditMode(false);
    } catch (e) {
      setError(toErr(e, "일별 테마 순위 저장에 실패했습니다."));
    }
  };

  const resetDailyRanks = async () => {
    if (flowSummaries.length === 0) return;
    setError("");
    try {
      const res = await repositories.marketTrends.updateDailyThemeRanks({
        trade_date: tradeDate,
        items: flowSummaries.map((x) => ({ market_theme_id: x.market_theme_id, manual_rank: null })),
      });
      setFlowSummaries(res.items ?? []);
      setRankDraftItems(res.items ?? []);
      setRankDraftMap(Object.fromEntries((res.items ?? []).map((x) => [x.market_theme_id, ""])));
      setMessage("자동 산정 순위로 초기화했습니다.");
      setRankEditMode(false);
    } catch (e) {
      setError(toErr(e, "수동 순위 초기화에 실패했습니다."));
    }
  };

  useEffect(() => {
    void loadConditions();
    void loadMarketThemes();
    void loadEvents();
  }, []);

  useEffect(() => {
    if (activeTab === "monthly" && monthlyCalendarDays.length === 0 && !monthlyLoading) {
      void loadMonthlyFlow();
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "monthly" && monthlyCalendarDays.length > 0 && !monthlyLoading) {
      void loadMonthlyFlow(monthlyBaseMonth, { refreshCalendar: false, refreshRecentTrend: true });
    }
  }, [monthlyTrendViewMode]);

  useEffect(() => {
    if (activeTab !== "flow") return;
    const today = todayInKst();
    if (tradeDate !== today) setTradeDate(today);
    void Promise.all([loadEvents(today), loadFlow(today)]);
  }, [activeTab]);

  useEffect(() => {
    setSelectedDayDetailTab("themes");
  }, [selectedMonthlyDate]);

  useEffect(() => {
    if (activeTab === "kiwoom") {
      void loadEvents(tradeDate);
    }
  }, [tradeDate, activeTab]);

  const monthlyCells = useMemo(() => buildCalendarCells(monthlyBaseMonth, monthlyCalendarDays), [monthlyBaseMonth, monthlyCalendarDays]);
  const monthlyTopThemes = useMemo(() => {
    const totals = new Map<number, { marketThemeId: number; themeName: string; score: number }>();
    monthlyCalendarDays.forEach((day) => {
      day.themes.forEach((theme) => {
        const current = totals.get(theme.market_theme_id) ?? {
          marketThemeId: theme.market_theme_id,
          themeName: theme.theme_name,
          score: 0,
        };
        current.score += Number(theme.rank_score ?? 0);
        totals.set(theme.market_theme_id, current);
      });
    });
    return Array.from(totals.values()).sort((a, b) => b.score - a.score || a.themeName.localeCompare(b.themeName, "ko"));
  }, [monthlyCalendarDays]);
  const monthlyTrendEntityLabel = monthlyTrendViewMode === "THEME_GROUP" ? "테마그룹" : "테마";
  const monthlyMaxDayScore = useMemo(
    () => Math.max(1, ...monthlyCalendarDays.map((d) => d.themes.reduce((sum, t) => sum + (t.rank_score ?? 0), 0))),
    [monthlyCalendarDays],
  );
  const selectedMonthlyDay = useMemo(
    () => monthlyCalendarDays.find((d) => d.trade_date === selectedMonthlyDate) ?? null,
    [monthlyCalendarDays, selectedMonthlyDate],
  );
  const selectedMonthlyThemes = useMemo(() => {
    if (!selectedMonthlyDay) return [];
    return [...selectedMonthlyDay.themes]
      .map((theme) => ({
        ...theme,
        stocks: [...(theme.stocks ?? [])].sort((a, b) => (a.stock_name || "").localeCompare(b.stock_name || "", "ko")),
      }))
      .sort((a, b) => {
        const scoreDiff = Number(b.rank_score || 0) - Number(a.rank_score || 0);
        if (scoreDiff !== 0) return scoreDiff;
        return (a.theme_name || "").localeCompare(b.theme_name || "", "ko");
      });
  }, [selectedMonthlyDay]);
  const todayDate = useMemo(() => todayInKst(), []);
  const monthlyTreemapPeriodStart = useMemo(() => subtractOneMonth(todayDate), [todayDate]);
  const monthlyTreemapItems = useMemo(
    () => buildMonthlyThemeTreemapItems(monthlyTrendResponses, monthlyTreemapPeriodStart, todayDate, monthlyTrendViewMode),
    [monthlyTrendResponses, monthlyTreemapPeriodStart, todayDate, monthlyTrendViewMode],
  );
  const monthlyTreemapMaxScore = useMemo(() => Math.max(1, ...monthlyTreemapItems.map((item) => item.scoreSum)), [monthlyTreemapItems]);
  const monthlyTreemapRects = useMemo(
    () => buildTreemapLayout(monthlyTreemapItems.map((item) => ({ id: `${item.viewMode}-${item.marketThemeId}`, value: item.scoreSum }))),
    [monthlyTreemapItems],
  );
  const monthlyTreemapRectMap = useMemo(
    () => new Map(monthlyTreemapRects.map((rect) => [rect.id, rect])),
    [monthlyTreemapRects],
  );
  const selectedMonthlyTreemapItem = useMemo(
    () => monthlyTreemapItems.find((item) => item.marketThemeId === selectedMonthlyTreemapId) ?? monthlyTreemapItems[0] ?? null,
    [monthlyTreemapItems, selectedMonthlyTreemapId],
  );
  const monthlyTreemapSummaryRows = useMemo(() => {
    const totalScore = monthlyTreemapItems.reduce((sum, item) => sum + item.scoreSum, 0);
    return monthlyTreemapItems.slice(0, 5).map((item) => ({
      ...item,
      share: totalScore > 0 ? Math.round((item.scoreSum / totalScore) * 1000) / 10 : 0,
    }));
  }, [monthlyTreemapItems]);

  const monthlyTreemapTotalScore = useMemo(
    () => monthlyTreemapItems.reduce((sum, item) => sum + item.scoreSum, 0),
    [monthlyTreemapItems],
  );
  const monthlyHeatmapDates = useMemo(
    () => getDateKeysBetween(monthlyTreemapPeriodStart, todayDate),
    [monthlyTreemapPeriodStart, todayDate],
  );
  const monthlySupplyHeatmapRows = useMemo<MonthlySupplyHeatmapRow[]>(() => {
    const map = new Map<number, MonthlySupplyHeatmapRow & { changeRateSum: number; changeRateCount: number }>();
    monthlyTrendResponses.forEach((response) => {
      (response.themes ?? []).forEach((theme) => {
        const current = map.get(theme.market_theme_id) ?? {
          marketThemeId: theme.market_theme_id,
          themeName: theme.theme_name,
          themeGroupName: theme.theme_group_name ?? null,
          avgChangeRate: null,
          stockCount: 0,
          eventCount: 0,
          dailyMap: new Map<string, MonthlyThemeFlowTrendPoint>(),
          changeRateSum: 0,
          changeRateCount: 0,
        };
        current.themeGroupName = theme.theme_group_name ?? current.themeGroupName;
        (theme.series ?? [])
          .filter((point) => point.trade_date >= monthlyTreemapPeriodStart && point.trade_date <= todayDate)
          .forEach((point) => {
            if (Number(point.daily_score || 0) <= 0 && Number(point.event_count || 0) <= 0) return;
            current.stockCount += Number(point.stock_count || 0);
            current.eventCount += Number(point.event_count || 0);
            current.dailyMap.set(point.trade_date, point);
            if (point.avg_change_rate != null && Number.isFinite(Number(point.avg_change_rate))) {
              current.changeRateSum += Number(point.avg_change_rate);
              current.changeRateCount += 1;
            }
          });
        map.set(theme.market_theme_id, current);
      });
    });
    return Array.from(map.values())
      .map((row) => ({
        marketThemeId: row.marketThemeId,
        themeName: row.themeName,
        themeGroupName: row.themeGroupName,
        avgChangeRate: row.changeRateCount > 0 ? row.changeRateSum / row.changeRateCount : null,
        stockCount: row.stockCount,
        eventCount: row.eventCount,
        dailyMap: row.dailyMap,
      }))
      .sort((a, b) => {
        const appearanceDiff = b.dailyMap.size - a.dailyMap.size;
        if (appearanceDiff !== 0) return appearanceDiff;
        const eventDiff = b.eventCount - a.eventCount;
        if (eventDiff !== 0) return eventDiff;
        const stockDiff = b.stockCount - a.stockCount;
        if (stockDiff !== 0) return stockDiff;
        const aValue = a.avgChangeRate ?? Number.NEGATIVE_INFINITY;
        const bValue = b.avgChangeRate ?? Number.NEGATIVE_INFINITY;
        if (aValue !== bValue) return bValue - aValue;
        return a.themeName.localeCompare(b.themeName, "ko");
      })
      ;
  }, [monthlyTrendResponses, monthlyTreemapPeriodStart, todayDate]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="시장 수급 테마(종목)"
        description="조건검색 결과 수급 이벤트 후보를 저장하고 테마/종목 단위 수급 흐름을 분석합니다."
        action={(
          <button
            type="button"
            className="btn btn-secondary"
            title="핀업 테마로그를 새 창으로 엽니다."
            onClick={() => {
              window.open(
                "https://finance.finup.co.kr/lab/themelog/popup?Fullscreen=true",
                "_blank",
                "noopener,noreferrer",
              );
            }}
          >
            핀업 테마 열기
          </button>
        )}
      />
      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="">
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap items-center gap-6">
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "kiwoom"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("kiwoom")}
            >
              키움 조건검색
            </button>
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "flow"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("flow")}
            >
              일별 수급 테마(종목)
            </button>
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "monthly"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("monthly")}
            >
              월별 수급 테마(종목)
            </button>
          </nav>
        </div>
      </SectionCard>

      {activeTab === "kiwoom" ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4">
            <SectionCard title="">
              <div className="market-trends-panel-header">
                <div>
                  <div className="market-trends-panel-title-row">
                    <h3 className="market-trends-panel-title">키움 조건식 목록</h3>
                    <span className="market-trends-panel-info" title="키움 REST API에서 조건검색식을 조회합니다. 새로고침 시 최신 조건식 목록을 다시 불러옵니다.">i</span>
                  </div>
                  <p className="market-trends-panel-subtitle">조건식을 선택해 결과를 조회합니다.</p>
                </div>
              </div>
              <div className="market-trends-action-row market-trends-condition-toolbar">
                <button type="button" className="btn btn-secondary" onClick={() => void refreshConditions()} disabled={conditionsRefreshing}>
                  {conditionsRefreshing ? "새로고침 중..." : "조건식 새로고침"}
                </button>
                <select
                  className="select-control market-trend-condition-order"
                  aria-label="조건식 정렬"
                  title="조건식 정렬"
                  value={conditionOrderMode}
                  onChange={(e) => setConditionOrderMode(e.target.value as ConditionOrderMode)}
                >
                  <option value="number">번호순</option>
                  <option value="name">조건식명순</option>
                </select>
              </div>
              <div className="market-trend-condition-list">
                {sortedConditions.map((c) => {
                  const selected = selectedConditionSeq === c.condition_seq;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      className={`market-trend-condition-item ${selected ? "selected" : ""}`}
                      onClick={() => { setSelectedConditionSeq(c.condition_seq); setSelectedConditionName(c.condition_name); }}
                      title={c.condition_name}
                    >
                      <strong>[{c.condition_seq.padStart(2, "0")}]</strong>
                      <span>{c.condition_name}</span>
                    </button>
                  );
                })}
              </div>
            </SectionCard>

            <SectionCard title="">
              <div className="market-trends-panel-header">
                <div>
                  <div className="market-trends-panel-title-row">
                    <h3 className="market-trends-panel-title">조건검색 결과</h3>
                    <span className="market-trends-panel-info" title="선택한 조건식의 현재 검색 결과입니다. 체크한 종목만 수급 이벤트 후보로 저장됩니다.">i</span>
                  </div>
                  <p className="market-trends-panel-subtitle">선택한 조건식의 종목 결과를 확인하고 후보로 저장합니다.</p>
                </div>
              </div>
              <div className="market-trends-result-head">
                <div className="market-trends-panel-meta">
                  <strong>{selectedConditionLabel}</strong>
                  <span>{conditionResultMeta}</span>
                </div>
                <div className="market-trend-result-actions">
                  <div className="market-trend-result-actions-left">
                    <button type="button" className="btn btn-secondary" onClick={() => void loadConditionResults()} disabled={!selectedConditionSeq}>결과 조회</button>
                    <button type="button" className="btn btn-primary" onClick={() => void saveSelectedAsEvents()} disabled={selectedItems.length === 0}>선택 후보 저장</button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void openConditionResultTrackingRegisterModal()}
                      disabled={selectedItems.length === 0}
                      title={selectedItems.length === 0 ? "등록할 조건검색 결과 종목을 선택해 주세요." : "선택한 조건검색 결과 종목을 종목트래킹 그룹에 바로 등록합니다."}
                    >
                      {selectedItems.length > 0 ? `선택 ${selectedItems.length}건 트래킹 등록` : "종목트래킹 등록"}
                    </button>
                  </div>
                  <div className="market-trend-result-actions-right">
                    <button type="button" className="btn btn-secondary condition-issue-copy-button" onClick={() => void copyIssueSummaryPrompt()} disabled={sortedResults.length === 0}>GPT 이슈정리 복사</button>
                  </div>
                </div>
              </div>
              <div className="table-shell max-h-[420px] overflow-auto market-trends-table-wrap">
                <table className="data-table compact-table condition-result-table market-trends-table">
                  <colgroup>
                    <col className="condition-result-col-check" />
                    <col className="condition-result-col-stock" />
                    <col className="condition-result-col-price" />
                    <col className="condition-result-col-rate" />
                    <col className="condition-result-col-volume" />
                    <col className="condition-result-col-value" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="condition-result-check-cell">
                        <label className="inline-flex items-center gap-1">
                          <input
                            type="checkbox"
                            checked={allResultChecked}
                            onChange={(e) => {
                              const next: Record<string, boolean> = {};
                              for (const row of sortedResults) next[getResultRowKey(row)] = e.target.checked;
                              setCheckedMap(next);
                            }}
                          />
                          <span>체크</span>
                        </label>
                      </th>
                      <th className="cursor-pointer condition-result-stock-cell" onClick={() => setResultSort((p) => toggleSort(p, "stock_name"))}>종목{sortMark(resultSort.key === "stock_name", resultSort.order)}</th>
                      <th className="cursor-pointer condition-result-number-cell" onClick={() => setResultSort((p) => toggleSort(p, "current_price"))}>현재가{sortMark(resultSort.key === "current_price", resultSort.order)}</th>
                      <th className="cursor-pointer condition-result-number-cell" onClick={() => setResultSort((p) => toggleSort(p, "change_rate"))}>등락률{sortMark(resultSort.key === "change_rate", resultSort.order)}</th>
                      <th className="cursor-pointer condition-result-number-cell" onClick={() => setResultSort((p) => toggleSort(p, "volume"))}>거래량{sortMark(resultSort.key === "volume", resultSort.order)}</th>
                      <th className="cursor-pointer condition-result-number-cell" onClick={() => setResultSort((p) => toggleSort(p, "estimated_trading_value"))}>거래대금(억){sortMark(resultSort.key === "estimated_trading_value", resultSort.order)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedResults.length === 0 ? (
                      <tr><td colSpan={6} className="text-center text-muted">조회 결과가 없습니다.</td></tr>
                    ) : null}
                    {sortedResults.map((r) => {
                      const key = getResultRowKey(r);
                      return (
                        <tr key={key}>
                          <td className="condition-result-check-cell"><input type="checkbox" checked={Boolean(checkedMap[key])} onChange={(e) => setCheckedMap((prev) => ({ ...prev, [key]: e.target.checked }))} /></td>
                          <td className="condition-result-stock-cell">
                            <div className="stock-cell">
                              <strong>{r.stock_name || "-"}</strong>
                              <span>{r.stock_code || "-"}</span>
                            </div>
                          </td>
                          <td className="condition-result-number-cell">{fmtNumber(r.current_price)}</td>
                          <td className={`condition-result-number-cell ${changeRateClass(r.change_rate)}`}>{fmtPct(r.change_rate)}</td>
                          <td className="condition-result-number-cell">{fmtNumber(r.volume)}</td>
                          <td className="condition-result-number-cell">{fmtEok2(estimatedTradingValue(r))}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>

          <SectionCard title="">
            <div className="market-trends-panel-header">
              <div>
                <div className="market-trends-panel-title-row">
                  <h3 className="market-trends-panel-title">저장된 수급 이벤트 후보</h3>
                  <span className="market-trends-panel-info" title="저장된 후보는 일별·월별 테마 수급 흐름 분석의 기초 데이터로 활용됩니다.">i</span>
                </div>
                <p className="market-trends-panel-subtitle">저장된 후보를 테마 수급 흐름 분석과 종목트래킹 등록에 활용합니다.</p>
              </div>
            </div>
            <div className="theme-event-candidate-toolbar market-trends-action-row">
              <div className="candidate-date-nav calendar-period-nav">
                <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => void applyFlowDate(shiftDate(tradeDate, -1))} aria-label="이전 날짜">&lt;</button>
                <input
                  className="input-control candidate-date-input calendar-period-input"
                  type="date"
                  value={tradeDate}
                  onChange={(e) => void applyFlowDate(e.target.value)}
                  onBlur={(e) => void applyFlowDate(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void applyFlowDate((e.target as HTMLInputElement).value);
                    }
                  }}
                  aria-label="수급 이벤트 후보 날짜"
                />
                <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => void applyFlowDate(shiftDate(tradeDate, 1))} aria-label="다음 날짜">&gt;</button>
                <button type="button" className="btn btn-primary calendar-today-button" onClick={() => void applyFlowDate(todayInKst())}>오늘</button>
              </div>
              <div className="theme-event-candidate-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={selectedTrackingCandidateIds.length === 0}
                  title={selectedTrackingCandidateIds.length === 0 ? "등록할 후보를 선택해 주세요." : "선택한 후보를 종목트래킹 그룹에 등록합니다."}
                  onClick={() => void openTrackingRegisterModal()}
                >
                  {selectedTrackingCandidateIds.length > 0 ? "선택 " + selectedTrackingCandidateIds.length + "건 트래킹 등록" : "종목트래킹 등록"}
                </button>
                {trackingRegisterCompleted ? <button type="button" className="btn btn-secondary" onClick={() => navigate("/stock-tracking")}>종목 트래킹으로 이동</button> : null}
                <button type="button" className="btn btn-primary" onClick={openManualCandidateModal}>+ 후보 직접등록</button>
              </div>
            </div>
            <div className="table-shell market-trends-table-wrap">
              <table className="data-table compact-table theme-event-candidate-table market-trends-table">
                <thead>
                  <tr>
                    <th className="condition-result-check-cell"><input type="checkbox" checked={allTrackingCandidatesChecked} onChange={(ev) => toggleAllTrackingCandidates(ev.target.checked)} aria-label="전체 후보 선택" /></th>
                    <th>감지일</th><th className="cursor-pointer" onClick={() => setEventNameSortOrder((p) => (p === "asc" ? "desc" : "asc"))}>종목{sortMark(true, eventNameSortOrder)}</th><th>시장</th><th className="text-right">등락률</th><th>연결 테마</th><th>메모</th><th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedEvents.length === 0 ? (
                    <tr><td colSpan={8} className="text-center text-muted">저장된 후보가 없습니다.</td></tr>
                  ) : null}
                  {sortedEvents.map((e) => {
                    const draft = eventDrafts[e.event_id] ?? { theme_status: "unassigned", user_memo: "", selected_theme_id: "" };
                    const links = eventThemeLinksMap[e.event_id] ?? [];
                    const themeSearchText = eventThemeSearchMap[e.event_id] ?? "";
                    const themeSearchKeyword = themeSearchText.trim().toLowerCase();
                    const selectedTheme = marketThemes.find((t) => String(t.id) === draft.selected_theme_id);
                    const themeInputValue = themeSearchText || selectedTheme?.theme_name || "";
                    const filteredThemeOptions = (themeSearchKeyword
                      ? marketThemes.filter((t) => t.theme_name.toLowerCase().includes(themeSearchKeyword))
                      : marketThemes.slice(0, 10)
                    ).slice(0, 10);
                    const themeListId = `event-theme-list-${e.event_id}`;
                    return (
                      <tr key={e.event_id}>
                        <td><input type="checkbox" checked={selectedTrackingCandidateSet.has(e.event_id)} onChange={(ev) => toggleTrackingCandidate(e.event_id, ev.target.checked)} aria-label="후보 선택" /></td>
                        <td>{formatDate(e.detected_at)}</td>
                        <td>
                          <div className="saved-candidate-stock-cell" title={e.stock_code || undefined}>
                            <div className="saved-candidate-stock-name-row">
                              <strong className="saved-candidate-stock-name">{e.stock_name || "-"}</strong>
                              {e.detection_source === "manual" ? <span className="manual-candidate-badge">{"\uC9C1\uC811\uB4F1\uB85D"}</span> : null}
                            </div>
                            <div className="saved-candidate-theme-chips">
                              {(e.existing_themes || []).length === 0 ? <span className="existing-theme-empty">{"\uAE30\uC874 \uD14C\uB9C8 \uC5C6\uC74C"}</span> : null}
                              {(e.existing_themes || []).slice(0, 3).map((theme) => (
                                <button
                                  key={`${e.event_id}-${theme.theme_id}`}
                                  type="button"
                                  className="existing-theme-chip"
                                  onClick={() => applyExistingTheme(e.event_id, theme)}
                                  title={theme.theme_group_name ? `${theme.theme_group_name} \u00B7 ${theme.theme_name}` : theme.theme_name}
                                >
                                  {theme.theme_name}
                                </button>
                              ))}
                              {(e.existing_themes || []).length > 3 ? (
                                <span className="existing-theme-more-wrap">
                                  <button
                                    type="button"
                                    className="existing-theme-chip more"
                                    onClick={() => setExistingThemePopoverEventId((prev) => (prev === e.event_id ? null : e.event_id))}
                                  >
                                    +{(e.existing_themes || []).length - 3}
                                  </button>
                                  {existingThemePopoverEventId === e.event_id ? (
                                    <div className="existing-theme-popover">
                                      <strong>{e.stock_name || "-"} {"\uAE30\uC874 \uC5F0\uACB0 \uD14C\uB9C8"}</strong>
                                      <div className="existing-theme-popover-list">
                                        {(e.existing_themes || []).map((theme) => (
                                          <button key={`popover-${e.event_id}-${theme.theme_id}`} type="button" className="existing-theme-chip" onClick={() => applyExistingTheme(e.event_id, theme)}>
                                            {theme.theme_name}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  ) : null}
                                </span>
                              ) : null}
                            </div>
                          </div>
                        </td>
                        <td>{e.market_type || "-"}</td><td className="text-right">{fmtPct(e.change_rate)}</td>
                        <td className="align-top">
                          <div className="min-w-[260px]">
                            <div className="flex gap-1 items-center">
                              <div className="theme-event-theme-picker">
                                <input
                                  className="input-control theme-event-theme-search"
                                  value={themeInputValue}
                                  list={themeListId}
                                  placeholder={"\uD14C\uB9C8\uBA85 \uAC80\uC0C9"}
                                  onChange={(ev) => {
                                    const value = ev.target.value;
                                    const matchedTheme = marketThemes.find((t) => t.theme_name === value)
                                      ?? marketThemes.find((t) => t.theme_name.toLowerCase() === value.trim().toLowerCase());
                                    setEventThemeSearchMap((prev) => ({ ...prev, [e.event_id]: value }));
                                    setEventDrafts((prev) => ({
                                      ...prev,
                                      [e.event_id]: {
                                        ...(prev[e.event_id] ?? draft),
                                        selected_theme_id: matchedTheme ? String(matchedTheme.id) : "",
                                      },
                                    }));
                                  }}
                                  onBlur={(ev) => {
                                    const value = ev.currentTarget.value;
                                    const matchedTheme = marketThemes.find((t) => t.theme_name === value)
                                      ?? marketThemes.find((t) => t.theme_name.toLowerCase() === value.trim().toLowerCase());
                                    if (matchedTheme) {
                                      setEventDrafts((prev) => ({
                                        ...prev,
                                        [e.event_id]: { ...(prev[e.event_id] ?? draft), selected_theme_id: String(matchedTheme.id) },
                                      }));
                                    }
                                  }}
                                  onKeyDown={(ev) => {
                                    if (ev.key === "Enter") {
                                      ev.preventDefault();
                                      void addThemeLink(e.event_id, ev.currentTarget.value);
                                    }
                                  }}
                                />
                                <datalist id={themeListId}>
                                  {filteredThemeOptions.map((t) => <option key={t.id} value={t.theme_name} />)}
                                </datalist>
                              </div>
                              <button
                                type="button"
                                className="btn btn-secondary theme-event-inline-button whitespace-nowrap"
                                onClick={() => {
                                  void addThemeLink(e.event_id, themeInputValue);
                                }}
                              >
                                {"\uD14C\uB9C8 \uCD94\uAC00"}
                              </button>
                            </div>
                            {links.length > 0 ? (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {links.map((l) => <button key={l.link_id} type="button" className="btn btn-secondary theme-event-inline-button theme-event-theme-chip" onClick={() => void removeThemeLink(e.event_id, l.link_id)} title="테마 연결 해제">{l.theme_name} ×</button>)}
                              </div>
                            ) : null}
                          </div>
                        </td>
                        <td className="align-top">
                          <textarea
                            className="input-control theme-event-memo-textarea"
                            value={draft.user_memo}
                            onChange={(ev) => setEventDrafts((prev) => ({ ...prev, [e.event_id]: { ...(prev[e.event_id] ?? draft), user_memo: ev.target.value } }))}
                            placeholder="메모"
                          />
                        </td>
                        <td className="align-top"><div className="flex gap-1"><button type="button" className="btn btn-secondary theme-event-inline-button whitespace-nowrap" onClick={() => void saveEventNote(e.event_id)}>메모 저장</button><button type="button" className="btn btn-danger theme-event-inline-button" onClick={() => void deleteEvent(e.event_id)}>삭제</button></div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {trackingRegisterOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card tracking-register-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>종목트래킹 등록</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setTrackingRegisterOpen(false)}>닫기</button>
            </div>
            <p className="text-sm text-muted mb-3">{trackingRegisterSource === "condition-results" ? "선택한 조건검색 결과 종목을 후보 저장 없이 바로 종목트래킹 그룹에 등록합니다." : "선택한 후보 종목을 종목트래킹 그룹에 등록합니다."}</p>
            <div className="tracking-register-count">{trackingRegisterSource === "condition-results" ? `선택 결과: ${selectedItems.length}건` : `선택 후보: ${selectedTrackingCandidateIds.length}건`}</div>
            <label className="manual-candidate-field">
              <span>등록 그룹</span>
              <select className="input-control" value={trackingGroupId} onChange={(e) => setTrackingGroupId(e.target.value)}>
                {trackingGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
              </select>
            </label>
            {trackingGroups.length === 0 ? (
              <div className="tracking-register-empty">
                <p className="text-sm text-danger mt-2">등록 가능한 종목트래킹 그룹이 없습니다. 먼저 종목 관리 &gt; 종목 트래킹에서 그룹을 등록해 주세요.</p>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => navigate("/stock-tracking")}>종목 트래킹 화면으로 이동</button>
              </div>
            ) : null}
            <p className="tracking-register-help">가격 갱신, 차트 확인, 메모 및 이미지는 종목 관리 &gt; 종목 트래킹 화면에서 관리합니다.</p>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setTrackingRegisterOpen(false)}>닫기</button>
              <button type="button" className="btn btn-primary" disabled={trackingRegisterSaving || trackingGroups.length === 0} onClick={() => void registerTrackingCandidates()}>{trackingRegisterSaving ? "등록 중..." : "등록"}</button>
            </div>
          </div>
        </div>
      ) : null}

      {manualModalOpen ? (
        <div className="modal-backdrop" onClick={() => setManualModalOpen(false)}>
          <div className="modal-card manual-candidate-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>수급 이벤트 후보 직접등록</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setManualModalOpen(false)}>
                닫기
              </button>
            </div>
            <p className="text-sm text-muted mb-3">
              직접등록 후보는 관심종목 Pool에 추가하지 않고, 현재 수급 이벤트 후보 데이터에만 저장됩니다.
            </p>

            <div className="manual-candidate-grid">
              <label className="manual-candidate-field">
                <span>감지일</span>
                <input
                  className="input-control"
                  type="date"
                  value={manualForm.trade_date}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, trade_date: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>테마 선택</span>
                <select
                  className="input-control"
                  value={manualForm.theme_id}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, theme_id: e.target.value }))}
                >
                  <option value="">테마 미지정</option>
                  {marketThemes.map((theme) => (
                    <option key={theme.id} value={theme.id}>{theme.theme_name}</option>
                  ))}
                </select>
              </label>
            </div>

            <form
              className="manual-candidate-search"
              onSubmit={(e) => {
                e.preventDefault();
                void searchManualCandidateStocks();
              }}
            >
              <input
                className="input-control"
                placeholder="종목명 또는 종목코드 입력"
                value={manualStockKeyword}
                onChange={(e) => setManualStockKeyword(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" disabled={manualStockLoading}>
                {manualStockLoading ? "검색 중..." : "검색"}
              </button>
            </form>

            {manualSelectedStock ? (
              <div className="manual-candidate-selected">
                <strong>{manualSelectedStock.stock_name}</strong>
                <span>{normalizeStockCode(manualSelectedStock.stock_code)} · {manualSelectedStock.market || "-"}</span>
              </div>
            ) : null}

            {manualStockResults.length > 0 ? (
              <div className="manual-candidate-stock-list">
                {manualStockResults.map((stock) => {
                  const selected = manualSelectedStock?.id === stock.id;
                  return (
                    <button
                      key={stock.id}
                      type="button"
                      className={`manual-candidate-stock-item ${selected ? "selected" : ""}`}
                      onClick={() => setManualSelectedStock(stock)}
                    >
                      <strong>{stock.stock_name}</strong>
                      <span>{normalizeStockCode(stock.stock_code)} · {stock.market || "-"}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}

            <div className="manual-candidate-grid mt-3">
              <label className="manual-candidate-field">
                <span>등락률(%)</span>
                <input
                  className="input-control"
                  inputMode="decimal"
                  placeholder="예: 12.5"
                  value={manualForm.change_rate}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, change_rate: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>거래대금(원)</span>
                <input
                  className="input-control"
                  inputMode="numeric"
                  placeholder="예: 50000000000"
                  value={manualForm.trading_value}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, trading_value: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>거래량</span>
                <input
                  className="input-control"
                  inputMode="numeric"
                  placeholder="선택 입력"
                  value={manualForm.volume}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, volume: e.target.value }))}
                />
              </label>
            </div>

            <label className="manual-candidate-field mt-3">
              <span>메모</span>
              <textarea
                className="input-control manual-candidate-memo"
                placeholder="메모를 입력해 주세요. (선택)"
                value={manualForm.memo}
                onChange={(e) => setManualForm((prev) => ({ ...prev, memo: e.target.value }))}
              />
            </label>

            <div className="manual-candidate-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setManualModalOpen(false)}>
                취소
              </button>
              <button type="button" className="btn btn-primary" disabled={manualSaving} onClick={() => void saveManualCandidate()}>
                {manualSaving ? "저장 중..." : "직접등록 저장"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === "flow" ? (
        <div className="space-y-4">
          <SectionCard title="" className="daily-theme-flow-section">
            <div className="watchlist-card-title-wrap">
              <h3 className="section-title m-0">일별 수급 테마(종목)</h3>
              <button
                type="button"
                className="hint-icon hint-icon-button"
                aria-expanded={flowRankInfoOpen}
                aria-label="테마 순위 산정 기준"
                onClick={() => setFlowRankInfoOpen((prev) => !prev)}
              >
                i
              </button>
              {flowRankInfoOpen ? (
                <div className="daily-flow-rank-popover" role="dialog" aria-label="테마 순위 산정 기준">
                  <strong>오늘의 테마 순위 산정 기준</strong>
                  <p>Theme Strength Score는 저장된 수급 후보를 기준으로 테마별 강도를 0~100점으로 계산합니다.</p>
                  <p>최종 점수 = 평균등락률 50% + 거래대금 35% + 종목확산 15%</p>
                  <dl>
                    <div><dt>평균등락률</dt><dd>평균 상승률 10% 이상을 100점으로 제한합니다.</dd></div>
                    <div><dt>거래대금</dt><dd>테마별 거래대금을 log 정규화해 자금 유입 강도를 비교합니다.</dd></div>
                    <div><dt>종목확산</dt><dd>상승 종목 수 8개 이상을 100점으로 제한합니다.</dd></div>
                  </dl>
                  <p>이 순위는 매수 추천이 아니라 오늘 시장에서 상대적으로 강하게 움직인 테마를 정렬하기 위한 참고 지표입니다.</p>
                </div>
              ) : null}
            </div>
            <div className="daily-flow-toolbar">
              <div className="daily-flow-controls calendar-period-nav">
                <button type="button" className="btn btn-secondary btn-table-sm calendar-nav-button" onClick={() => void applyFlowDate(shiftDate(tradeDate, -1))} aria-label="이전 날짜">◀</button>
                <input
                  className="input-control"
                  type="date"
                  value={tradeDate}
                  onChange={(e) => void applyFlowDate(e.target.value)}
                  onBlur={(e) => void applyFlowDate(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void applyFlowDate((e.target as HTMLInputElement).value);
                    }
                  }}
                />
                <button type="button" className="btn btn-secondary btn-table-sm calendar-nav-button" onClick={() => void applyFlowDate(shiftDate(tradeDate, 1))} aria-label="다음 날짜">▶</button>
                <button type="button" className="btn btn-secondary calendar-today-button" onClick={() => void applyFlowDate(todayInKst())}>오늘</button>
                {!rankEditMode ? <button type="button" className="btn btn-secondary" title="카드를 드래그해서 체감 주도 테마 순서를 직접 조정합니다." onClick={beginRankEdit}>순위 편집</button> : null}
                {rankEditMode ? <button type="button" className="btn btn-primary" onClick={() => void saveDailyRanks()}>순위 저장</button> : null}
                {rankEditMode ? <button type="button" className="btn btn-secondary" onClick={cancelRankEdit}>취소</button> : null}
                {rankEditMode ? <button type="button" className="btn btn-secondary" onClick={() => void resetDailyRanks()}>자동순위로 초기화</button> : null}
              </div>

              <div className="daily-flow-compact-stats">
                <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">저장 후보</p><strong className="watchlist-top-stat-value">{flowSummaryStats.savedCandidates}건</strong></div>
                <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">등장 테마</p><strong className="watchlist-top-stat-value">{flowSummaryStats.themeCount}개</strong></div>
                <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">1위 테마</p><strong className="watchlist-top-stat-value">{flowSummaryStats.topTheme}</strong></div>
                <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">최고 등락률</p><strong className="watchlist-top-stat-value">{fmtPct(flowSummaryStats.maxChangeRate)}</strong></div>
                <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">미분류</p><strong className="watchlist-top-stat-value">{flowSummaryStats.unclassified}</strong></div>
              </div>
            </div>

            {flowLoading ? <p className="text-sm text-muted">테마 요약을 조회 중입니다.</p> : null}
            {!flowLoading && flowSummaries.length === 0 ? <p className="text-sm text-muted">이 날짜에 저장된 수급 이벤트 후보가 없습니다.</p> : null}

            {flowSummaries.length > 0 ? (
              <div className={`daily-theme-rank-grid ${rankEditMode ? "is-editing" : ""}`}>
                {visibleFlowSummaries.map((item, index) => {
                  const selected = selectedFlowTheme?.id === item.market_theme_id;
                  const displayRank = rankEditMode ? index + 1 : item.final_rank ?? index + 1;
                  const strengthScore = item.theme_strength_score ?? item.rank_score;
                  return (
                    <button
                      key={item.market_theme_id}
                      type="button"
                      className={`daily-theme-rank-card ${selected ? "selected" : ""} ${rankEditMode ? "rank-editing" : ""} ${draggingThemeId === item.market_theme_id ? "dragging" : ""}`}
                      draggable={rankEditMode}
                      onDragStart={(e) => handleRankDragStart(e, item.market_theme_id)}
                      onDragOver={(e) => handleRankDragOver(e, item.market_theme_id)}
                      onDrop={(e) => handleRankDrop(e, item.market_theme_id)}
                      onDragEnd={() => setDraggingThemeId(null)}
                      onClick={() => {
                        if (!rankEditMode) void loadFlowStocks(item);
                      }}
                      title={rankEditMode ? "드래그해서 순서를 바꿀 수 있습니다." : `상승 ${fmtScore(item.return_score)} · 거래대금 ${fmtScore(item.trading_value_score)} · 확산 ${fmtScore(item.breadth_score)}`}
                    >
                      <div className="daily-theme-rank-title">
                        {rankEditMode ? <span className="daily-theme-drag-handle" aria-hidden="true">↕</span> : null}
                        <span>{displayRank}위 {item.theme_name}</span>
                        {item.rank_basis === "manual" ? <span className="daily-theme-rank-badge">수동순위</span> : null}
                      </div>
                      <div className="daily-theme-rank-meta">강도점수 {fmtScore(strengthScore)} · {item.stock_count}종목 · 이벤트 {item.event_count}</div>
                      <div className="daily-theme-rank-meta">평균 {fmtSignedPct(item.avg_change_rate)} · 최고 {fmtSignedPct(item.max_change_rate)}</div>
                      <div className="daily-theme-rank-meta truncate">대표 {item.representative_stocks.length > 0 ? item.representative_stocks[0] : "-"} · 거래대금 {fmtEokShort(item.estimated_trading_value_sum)}</div>
                      <div className="daily-theme-rank-breakdown">상승 {fmtScore(item.return_score)} · 거래대금 {fmtScore(item.trading_value_score)} · 확산 {fmtScore(item.breadth_score)}</div>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="">
            <div className="theme-detail-header">
              <div className="theme-detail-title-block">
                <div className="watchlist-card-title-wrap">
                  <h3 className="section-title m-0">선택 테마 상세 종목{selectedFlowTheme ? ` - ${selectedFlowTheme.name}` : ""}</h3>
                </div>
                {selectedFlowTheme && selectedThemeMeta ? <p className="text-sm text-muted mb-2">{selectedThemeMeta.stockCount}종목 · 대표 {selectedThemeMeta.representative}</p> : null}
              </div>
              <div className="market-mini-charts">
                <div className="market-mini-chart-card">
                  <p className="market-mini-chart-label">KOSPI 3개월</p>
                  {brokenCharts["market-kospi-month3"] ? (
                    <div className="market-mini-chart-fallback">차트 이미지 없음</div>
                  ) : (
                    <button
                      type="button"
                      className="market-mini-chart-button"
                      onClick={() => setZoomedChart({ url: getNaverMarketChartImageUrl("KOSPI", chartSidcode), alt: "KOSPI 3개월 차트" })}
                    >
                      <img
                        src={getNaverMarketChartImageUrl("KOSPI", chartSidcode)}
                        alt="KOSPI 3개월 차트"
                        loading="lazy"
                        className="market-mini-chart-image"
                        onError={() => onChartError("market-kospi-month3")}
                      />
                    </button>
                  )}
                </div>
                <div className="market-mini-chart-card">
                  <p className="market-mini-chart-label">KOSDAQ 3개월</p>
                  {brokenCharts["market-kosdaq-month3"] ? (
                    <div className="market-mini-chart-fallback">차트 이미지 없음</div>
                  ) : (
                    <button
                      type="button"
                      className="market-mini-chart-button"
                      onClick={() => setZoomedChart({ url: getNaverMarketChartImageUrl("KOSDAQ", chartSidcode), alt: "KOSDAQ 3개월 차트" })}
                    >
                      <img
                        src={getNaverMarketChartImageUrl("KOSDAQ", chartSidcode)}
                        alt="KOSDAQ 3개월 차트"
                        loading="lazy"
                        className="market-mini-chart-image"
                        onError={() => onChartError("market-kosdaq-month3")}
                      />
                    </button>
                  )}
                </div>
              </div>
            </div>
            {flowStocksLoading ? <p className="text-sm text-muted">상세 종목을 조회 중입니다.</p> : null}
            {!flowStocksLoading && selectedFlowTheme && flowStocks.length === 0 ? <p className="text-sm text-muted">선택한 테마에 연결된 종목이 없습니다.</p> : null}

            {flowStocks.length > 0 ? (
              <div className="table-shell overflow-auto">
                <table className="data-table compact-table min-w-[1320px]">
                  <thead>
                    <tr><th>테마명</th><th>종목명</th><th>일봉</th><th>주봉</th><th>월봉</th></tr>
                  </thead>
                  <tbody>
                    {flowStocks.map((row) => {
                      const dayUrl = getNaverChartImageUrl(row.stock_code, "day", chartSidcode);
                      const weekUrl = getNaverChartImageUrl(row.stock_code, "week", chartSidcode);
                      const monthUrl = getNaverChartImageUrl(row.stock_code, "month", chartSidcode);

                      const chartCell = (url: string, key: string) => (
                        <div className="w-[280px]">
                          {brokenCharts[key] ? (
                            <div className="h-[120px] w-[280px] border rounded flex items-center justify-center text-xs text-muted">차트 이미지 없음</div>
                          ) : (
                            <button type="button" className="block" onClick={() => setZoomedChart({ url, alt: `차트-${row.stock_code}` })}>
                              <img
                                src={url}
                                alt={`차트-${row.stock_code}`}
                                loading="lazy"
                                className="h-auto w-[280px] border rounded"
                                onError={() => onChartError(key)}
                              />
                            </button>
                          )}
                        </div>
                      );

                      return (
                        <tr key={`${row.market_theme_id}-${row.stock_code}`}>
                          <td>{row.theme_name}</td>
                          <td>
                            <div>{row.stock_name}</div>
                            <div className="text-xs text-muted">{row.stock_code}</div>
                            {row.user_memo ? (
                              <div className="theme-flow-memo-text text-[11px] text-slate-500 max-w-[260px]" title={row.user_memo}>
                                메모: {row.user_memo}
                              </div>
                            ) : null}
                          </td>
                          <td>{chartCell(dayUrl, `${row.stock_code}-day`)}</td>
                          <td>{chartCell(weekUrl, `${row.stock_code}-week`)}</td>
                          <td>{chartCell(monthUrl, `${row.stock_code}-month`)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "monthly" ? (
        <div className="space-y-4">
          <SectionCard title="">
            <div className="monthly-flow-heading-row">
              <div className="watchlist-card-title-wrap">
                <h3 className="section-title m-0">월별 수급 테마(종목)</h3>
                <span className="hint-icon" title="저장된 수급 이벤트 후보를 월 단위로 집계하여 날짜별·테마별 수급 흐름을 보여줍니다.">i</span>
              </div>
              {monthlySummary30d ? (
                <span className="monthly-supply-period-badge">최근 30일 · 기간 {monthlySummary30d.period_start_date} ~ {monthlySummary30d.period_end_date}</span>
              ) : null}
            </div>
            <div className="monthly-flow-toolbar">
              <div className="monthly-flow-controls calendar-period-nav">
                <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => void applyMonthlyFlowMonth(shiftMonthInput(monthlyBaseMonth, -1))} aria-label="이전 월">◀</button>
                <input className="input-control calendar-period-input" type="month" value={monthlyBaseMonth} onChange={(e) => void applyMonthlyFlowMonth(e.target.value)} />
                <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => void applyMonthlyFlowMonth(shiftMonthInput(monthlyBaseMonth, 1))} aria-label="다음 월">▶</button>
                <button type="button" className="btn btn-secondary calendar-today-button" onClick={() => void applyMonthlyFlowMonth(getMonthInput())}>이번달</button>
              </div>

              <div className="monthly-flow-compact-stats">
                <div className="monthly-flow-stat-mini">
                  <p className="monthly-flow-stat-label">등장 테마 수</p>
                  <strong className="monthly-flow-stat-value">{monthlySummary30d?.appeared_theme_count ?? 0}개</strong>
                </div>
                <div className="monthly-flow-stat-mini">
                  <p className="monthly-flow-stat-label">TOP 테마</p>
                  <strong
                    className="monthly-flow-stat-value"
                    title={monthlySummary30d?.top_theme ? `${monthlySummary30d.top_theme.theme_name} · ${monthlySummary30d.top_theme.appearance_count}회` : "-"}
                  >
                    {monthlySummary30d?.top_theme ? `${monthlySummary30d.top_theme.theme_name} · ${monthlySummary30d.top_theme.appearance_count}회` : "-"}
                  </strong>
                </div>
                {[0, 1, 2].map((index) => {
                  const stock = monthlySummary30d?.top_stocks[index];
                  const value = stock ? `(${stock.appearance_count}회)${stock.stock_name}` : "-";
                  return (
                    <div key={`monthly-top-stock-${index + 1}`} className="monthly-flow-stat-mini">
                      <p className="monthly-flow-stat-label">TOP{index + 1} 종목</p>
                      <strong className="monthly-flow-stat-value" title={value}>{value}</strong>
                    </div>
                  );
                })}
              </div>
            </div>
            {monthlyLoading ? <p className="text-sm text-muted">월별 테마 수급 흐름을 조회 중입니다.</p> : null}
            {!monthlyLoading && monthlyCalendarDays.length === 0 ? <p className="text-sm text-muted">저장된 수급 이벤트 후보가 없습니다.</p> : null}

            {monthlyCalendarDays.length > 0 ? (
              <div className="market-trend-monthly-grid">
                <div className="border rounded-lg p-3">
                  <div className="watchlist-card-title-wrap">
                    <h4 className="section-title m-0">월간 수급 달력</h4>
                    <span className="hint-icon" title="날짜별로 저장된 수급 이벤트 후보의 테마 점수를 표시합니다. 강한 수급일은 더 강조되어 표시됩니다.">i</span>
                  </div>
                  <div className="grid grid-cols-7 gap-2 mb-2 text-xs font-medium text-slate-600">
                    {["일", "월", "화", "수", "목", "금", "토"].map((w) => <div key={w}>{w}</div>)}
                  </div>
                  <div className="grid grid-cols-7 gap-2">
                    {monthlyCells.map((cell, idx) => {
                      const isToday = cell.date === todayDate;
                      const isSelected = cell.date && selectedMonthlyDate === cell.date;
                      const score = cell.day?.themes?.reduce((sum, t) => sum + (t.rank_score ?? 0), 0) ?? 0;
                      const intensity = score / monthlyMaxDayScore;
                      const heatClass = intensity >= 0.75 ? "heat-strong" : intensity >= 0.4 ? "heat-mid" : intensity > 0 ? "heat-light" : "";
                      return (
                        <button
                          key={`${cell.date ?? "blank"}-${idx}`}
                          type="button"
                          disabled={!cell.date}
                          onClick={() => cell.date && setSelectedMonthlyDate(cell.date)}
                          className={`market-trend-calendar-cell ${!cell.date ? "blank" : ""} ${isSelected ? "selected" : ""} ${isToday ? "today" : ""} ${heatClass}`}
                        >
                          <div className="text-xs font-semibold mb-1">{cell.date ? Number(cell.date.slice(8, 10)) : ""}</div>
                          {cell.day?.themes?.slice(0, 3).map((theme) => (
                            <div key={`${cell.date}-${theme.market_theme_id}`} className="text-[11px] text-slate-700 truncate">
                              {theme.theme_name} +{theme.rank_score}
                            </div>
                          ))}
                          {cell.day && cell.day.themes.length > 3 ? <div className="text-[11px] text-slate-500">+{cell.day.themes.length - 3}개</div> : null}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="monthly-flow-selected-detail">
                  {selectedMonthlyDay ? (
                    <div>
                      <div className="monthly-flow-selected-head">
                        <div className="monthly-flow-selected-title">
                          <h4 className="section-title m-0">선택일 상세</h4>
                          <span className="selected-date-inline">{selectedMonthlyDay.trade_date}</span>
                        </div>
                        <div className="theme-flow-detail-tabs" role="tablist" aria-label="선택일 상세 구분">
                          <button
                            type="button"
                            className={`theme-flow-detail-tab ${selectedDayDetailTab === "themes" ? "is-active" : ""}`}
                            onClick={() => setSelectedDayDetailTab("themes")}
                            role="tab"
                            aria-selected={selectedDayDetailTab === "themes"}
                          >
                            테마별 종목
                          </button>
                          <button
                            type="button"
                            className={`theme-flow-detail-tab ${selectedDayDetailTab === "memos" ? "is-active" : ""}`}
                            onClick={() => setSelectedDayDetailTab("memos")}
                            role="tab"
                            aria-selected={selectedDayDetailTab === "memos"}
                          >
                            종목 메모
                          </button>
                        </div>
                      </div>

                      {selectedDayDetailTab === "themes" ? (
                        <div className="theme-flow-theme-cards">
                          {selectedMonthlyThemes.length === 0 ? <p className="selected-empty-message">선택한 날짜에 수급 테마가 없습니다.</p> : null}
                          {selectedMonthlyThemes.map((theme) => (
                            <div key={`selected-${theme.market_theme_id}`} className="selected-theme-item">
                              <div className="selected-theme-row">
                                <span className="selected-theme-name" title={theme.theme_name}>{theme.theme_name}</span>
                                <span className="selected-theme-score">+{theme.rank_score}</span>
                              </div>
                              <div className="selected-stock-list">
                                {(theme.stocks ?? []).length > 0 ? (
                                  theme.stocks.map((stock) => {
                                    const stockLabel = stock.stock_name || stock.stock_code || "-";
                                    const isWideChip = stockLabel.length >= 10;
                                    return (
                                      <span key={`${theme.market_theme_id}-${stock.stock_code ?? stock.stock_id ?? stock.stock_name}`} className={`selected-stock-chip ${isWideChip ? "selected-stock-chip--wide" : ""}`}>
                                        <span className="selected-stock-name">{stockLabel}</span>
                                        {stock.change_rate != null ? <strong className={`monthly-supply-change-rate ${changeRateClass(stock.change_rate)}`}>{fmtSignedPct(stock.change_rate)}</strong> : null}
                                      </span>
                                    );
                                  })
                                ) : (
                                  <span className="selected-empty-message">
                                    {theme.stock_count > 0 ? `${theme.stock_count}종목` : "연결 종목 정보 없음"}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      {selectedDayDetailTab === "memos" ? (
                        <div className="theme-flow-memo-panel">
                          <div className="theme-flow-memo-panel-header">
                            <h5>메모 목록</h5>
                          </div>
                          {(selectedMonthlyDay.memo_items ?? []).length > 0 ? (
                            <div className="table-shell overflow-auto">
                              <table className="data-table compact-table theme-flow-memo-table">
                                <colgroup>
                                  <col style={{ width: "20%" }} />
                                  <col style={{ width: "30%" }} />
                                  <col style={{ width: "50%" }} />
                                </colgroup>
                                <thead>
                                  <tr>
                                    <th>테마명</th>
                                    <th>종목명</th>
                                    <th>메모</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(selectedMonthlyDay.memo_items ?? []).map((item, index) => (
                                    <tr key={`${selectedMonthlyDay.trade_date}-${item.theme_id ?? "none"}-${item.stock_code ?? item.stock_name}-${index}`}>
                                      <td>{item.theme_name || "-"}</td>
                                      <td>
                                        <div className="stock-cell">
                                          <strong>{item.stock_name || item.stock_code || "-"}</strong>
                                          {item.stock_code ? <span>{item.stock_code}</span> : null}
                                        </div>
                                      </td>
                                      <td className="theme-flow-memo-cell">{item.memo || "-"}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="selected-empty-message">선택한 날짜에 등록된 수급 메모가 없습니다.</p>
                          )}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="monthly-flow-selected-fallback">
                      <p className="text-sm text-muted">월간 TOP 테마</p>
                      {monthlyTopThemes.slice(0, 3).map((theme) => (
                        <div key={`month-top-${theme.marketThemeId}`} className="flex items-center justify-between text-sm gap-2">
                          <span className="font-semibold text-slate-800">{theme.themeName}</span>
                          <span className="text-slate-600">+{theme.score}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="">
            <div className="theme-flow-graph-header monthly-theme-treemap-header">
              <div className="watchlist-card-title-wrap monthly-theme-treemap-title-wrap">
                <div>
                  <div className="monthly-theme-treemap-title-row">
                    <h3 className="section-title m-0">최근 1개월 수급 테마(종목) 흐름</h3>
                    <span className="hint-icon" title="월간 테마 누적 흐름의 daily_score를 최근 1개월 기준으로 합산합니다. 타일 면적은 종목수가 아니라 점수 합산값 기준입니다.">i</span>
                  </div>
                  <p className="monthly-theme-treemap-description">
                    <span>저장된 수급 이벤트 후보 종목의 등락률을 기준으로 월간 테마 흐름을 표시합니다.</span>
                    <span>히트맵은 날짜별 테마 출현 및 평균등락률, 트리맵은 누적 수급 점수 기준입니다.</span>
                    <span>테마명·테마그룹·종목 연결은 조회 시점의 현재 활성 분류를 적용하며, 저장된 과거 수급 이벤트는 변경하지 않습니다.</span>
                  </p>
                </div>
              </div>
              <div className="monthly-theme-treemap-controls">
                <div className="market-trend-flow-view-toggle" aria-label="최근 1개월 수급 테마 보기">
                  <button
                    type="button"
                    className={monthlyThemeFlowView === "heatmap" ? "active" : ""}
                    onClick={() => setMonthlyThemeFlowView("heatmap")}
                  >
                    히트맵
                  </button>
                  <button
                    type="button"
                    className={monthlyThemeFlowView === "treemap" ? "active" : ""}
                    onClick={() => setMonthlyThemeFlowView("treemap")}
                  >
                    트리맵
                  </button>
                </div>
                <span className="monthly-theme-treemap-period">기간 {monthlyTreemapPeriodStart} ~ {todayDate}</span>
              </div>
            </div>
            {monthlyThemeFlowView === "treemap" ? (
              <div className="monthly-theme-treemap-subcontrols">
                <div className="theme-flow-view-toggle" aria-label="최근 1개월 트리맵 표시 기준">
                  <button
                    type="button"
                    className={`theme-flow-toggle-button ${monthlyTrendViewMode === "THEME" ? "active" : ""}`}
                    onClick={() => setMonthlyTrendViewMode("THEME")}
                  >
                    테마 기준
                  </button>
                  <button
                    type="button"
                    className={`theme-flow-toggle-button ${monthlyTrendViewMode === "THEME_GROUP" ? "active" : ""}`}
                    onClick={() => setMonthlyTrendViewMode("THEME_GROUP")}
                  >
                    테마그룹 기준
                  </button>
                </div>
              </div>
            ) : null}
            {monthlyThemeFlowView === "heatmap" ? (
              monthlySupplyHeatmapRows.length === 0 ? (
                <div className="monthly-theme-treemap-empty">
                  최근 1개월 기준으로 표시할 수급 테마(종목) 히트맵 데이터가 없습니다.
                </div>
              ) : (
                <MonthlySupplyHeatmap
                  rows={monthlySupplyHeatmapRows}
                  dates={monthlyHeatmapDates}
                  onSelectDate={selectMonthlyHeatmapDate}
                />
              )
            ) : monthlyTreemapItems.length === 0 ? (
              <div className="monthly-theme-treemap-empty">
                최근 1개월 기준으로 집계된 테마 수급 데이터가 없습니다.
              </div>
            ) : (
              <div className="monthly-theme-treemap-section">
                <div className="theme-treemap monthly-theme-treemap-card" onMouseLeave={() => setMonthlyTreemapTooltip(null)}>
                  {monthlyTreemapItems.map((item) => {
                    const rect = monthlyTreemapRectMap.get(`${item.viewMode}-${item.marketThemeId}`);
                    const sizeClass = getThemeTreemapSizeClass(item, monthlyTreemapMaxScore);
                    const textMetrics = getTreemapTextMetrics(rect, item.themeName, { variant: "marketTrend" });
                    const labelClass = getTreemapLabelClass(rect, item.themeName, { variant: "marketTrend" });
                    const intensity = Math.max(0.22, Math.min(1, item.scoreSum / monthlyTreemapMaxScore));
                    const share = monthlyTreemapTotalScore > 0 ? Math.round((item.scoreSum / monthlyTreemapTotalScore) * 1000) / 10 : 0;
                    const style = {
                      "--theme-intensity": intensity,
                      "--tile-title-size": `${textMetrics.titleFontSize}px`,
                      "--tile-title-lines": textMetrics.titleLineClamp,
                      left: `calc(${rect?.x ?? 0}% + 2px)`,
                      top: `calc(${rect?.y ?? 0}% + 2px)`,
                      width: `calc(${rect?.width ?? 0}% - 4px)`,
                      height: `calc(${rect?.height ?? 0}% - 4px)`,
                    } as CSSProperties;
                    return (
                      <button
                        key={`${item.viewMode}-${item.marketThemeId}`}
                        type="button"
                        title={`${item.themeName} · 최근 1개월 누적 ${item.scoreSum}점 · ${item.stockCount}종목 · 비중 ${share}% · 기간 ${monthlyTreemapPeriodStart} ~ ${todayDate}`}
                        className={`theme-treemap-tile monthly-theme-treemap-tile ${sizeClass} ${labelClass} ${selectedMonthlyTreemapItem?.marketThemeId === item.marketThemeId ? "selected" : ""}`}
                        style={style}
                        onClick={() => setSelectedMonthlyTreemapId(item.marketThemeId)}
                        onMouseMove={(event) => setMonthlyTreemapTooltip({ x: event.clientX, y: event.clientY, item, share })}
                        onFocus={(event) => {
                          const box = event.currentTarget.getBoundingClientRect();
                          setMonthlyTreemapTooltip({ x: box.left + box.width / 2, y: box.top + 12, item, share });
                        }}
                        onBlur={() => setMonthlyTreemapTooltip(null)}
                      >
                        <span className="theme-treemap-title">{item.themeName}</span>
                        {item.viewMode === "THEME_GROUP" && item.topChildThemes.length ? (
                          <span className="theme-treemap-subthemes">{item.topChildThemes.join(" · ")}</span>
                        ) : item.viewMode === "THEME" && item.themeGroupName ? (
                          <span className="theme-treemap-subthemes">{item.themeGroupName}</span>
                        ) : null}
                        <span className="theme-treemap-stock-count">{item.scoreSum}점 · {item.stockCount}종목</span>
                      </button>
                    );
                  })}
                  {monthlyTreemapTooltip ? (
                    <div
                      className="theme-treemap-tooltip"
                      style={{
                        left: Math.max(8, Math.min(monthlyTreemapTooltip.x + 14, (typeof window === "undefined" ? 1440 : window.innerWidth) - 340)),
                        top: Math.max(8, Math.min(monthlyTreemapTooltip.y + 14, (typeof window === "undefined" ? 900 : window.innerHeight) - 230)),
                      }}
                    >
                      <strong>{monthlyTreemapTooltip.item.themeName}</strong>
                      <dl>
                        <div><dt>기간</dt><dd>{monthlyTreemapPeriodStart} ~ {todayDate}</dd></div>
                        <div><dt>누적 점수</dt><dd>{monthlyTreemapTooltip.item.scoreSum}점</dd></div>
                        <div><dt>비중</dt><dd>{monthlyTreemapTooltip.share}%</dd></div>
                        <div><dt>관련 종목</dt><dd>{monthlyTreemapTooltip.item.stockCount}종목 · 이벤트 {monthlyTreemapTooltip.item.eventCount}건</dd></div>
                        <div><dt>최근 등장</dt><dd>{monthlyTreemapTooltip.item.latestDate ?? "-"}</dd></div>
                        <div><dt>대표 종목</dt><dd>{monthlyTreemapTooltip.item.relatedStocks.length ? monthlyTreemapTooltip.item.relatedStocks.slice(0, 5).join(", ") : "-"}</dd></div>
                      </dl>
                    </div>
                  ) : null}
                </div>

                {selectedMonthlyTreemapItem ? (
                  <div className="monthly-theme-treemap-detail">
                    <div>
                      <h4>{selectedMonthlyTreemapItem.themeName}</h4>
                      <p>기간 {monthlyTreemapPeriodStart} ~ {todayDate}</p>
                    </div>
                    <div className="monthly-theme-treemap-detail-grid">
                      <div><span>누적 점수</span><strong>{selectedMonthlyTreemapItem.scoreSum}점</strong></div>
                      <div><span>관련 종목</span><strong>{selectedMonthlyTreemapItem.stockCount}종목</strong></div>
                      <div><span>이벤트</span><strong>{selectedMonthlyTreemapItem.eventCount}건</strong></div>
                      <div><span>마지막 순위</span><strong>{selectedMonthlyTreemapItem.latestFinalRank ? `${selectedMonthlyTreemapItem.latestFinalRank}위` : "-"}</strong></div>
                    </div>
                    <p className="monthly-theme-treemap-detail-meta">
                      등장일: {selectedMonthlyTreemapItem.sourceDates.length ? selectedMonthlyTreemapItem.sourceDates.join(", ") : "-"}
                    </p>
                    <p className="monthly-theme-treemap-detail-meta">
                      관련 종목: {selectedMonthlyTreemapItem.relatedStocks.length ? selectedMonthlyTreemapItem.relatedStocks.join(", ") : "월간 테마 누적 흐름 데이터에 포함되지 않음"}
                    </p>
                  </div>
                ) : null}

                <div className="monthly-theme-treemap-summary">
                  <h4>최근 1개월 상위 테마 요약</h4>
                  <div className="table-shell overflow-auto">
                    <table className="data-table compact-table">
                      <thead>
                        <tr><th>순위</th><th>{monthlyTrendEntityLabel}</th><th>누적 점수</th><th>관련 종목</th><th>비중</th></tr>
                      </thead>
                      <tbody>
                        {monthlyTreemapSummaryRows.map((item) => (
                          <tr key={`summary-${item.marketThemeId}`}>
                            <td>{item.rank}</td>
                            <td>{item.themeName}</td>
                            <td>{item.scoreSum}점</td>
                            <td>{item.stockCount}종목</td>
                            <td>{item.share}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
            <SupplyTopStockReturnChart
              data={topStockReturnTrend}
              loading={topStockReturnLoading}
              error={topStockReturnError}
              collecting={topStockPriceCollecting}
              collectionMessage={topStockPriceCollectionMessage}
              onRefreshPrices={() => void refreshTopStockPrices()}
              onRetry={() => {
                if (!monthlySummary30d) return;
                void loadTopStockReturnTrend(monthlySummary30d.period_start_date, monthlySummary30d.period_end_date, true);
              }}
            />
          </SectionCard>
        </div>
      ) : null}

      {zoomedChart ? (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setZoomedChart(null)}>
          <img
            src={zoomedChart.url}
            alt={zoomedChart.alt}
            className="h-auto w-[700px] max-w-[95vw] rounded border border-white/30"
            onClick={(e) => {
              e.stopPropagation();
              setZoomedChart(null);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export default MarketTrendsPage;
