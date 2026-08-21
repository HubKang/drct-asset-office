import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { CSSProperties } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Info, Pencil, RefreshCw } from "lucide-react";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import MarketThemePriceFlowPanel from "@/components/marketThemes/MarketThemePriceFlowPanel";
import MarketThemeFlowTrendPanel, { invalidateMarketThemeFlowTrendFrontendCache } from "@/components/marketThemes/MarketThemeFlowTrendPanel";
import MarketThemeReturnPredictionPanel from "@/components/marketThemes/MarketThemeReturnPredictionPanel";
import MarketThemeDetailDrawer, { ThemeLinkedStockChart, type MarketThemeDetailFlowContext } from "@/components/marketThemes/MarketThemeDetailDrawer";
import UsMarketThemesPanel from "@/components/marketThemes/UsMarketThemesPanel";
import { repositories } from "@/services";
import { ApiError } from "@/services/api/apiClient";
import {
  buildNaverTraderChartUrl,
  normalizeNaverStockCode,
  type NaverTraderChartType,
} from "@/utils/naverChart";
import { compareThemeStocksBySupplyCount, type SupplyCountSort } from "@/utils/marketThemeStockSort";
import { getThemeReturnHeatmapColor, THEME_RETURN_HEATMAP_COLORS } from "@/utils/marketThemeReturnColor";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeFlowTrendActor,
  MarketThemeFlowTrendAttribution,
  MarketThemeFlowTrendMetric,
  MarketThemeFlowTrendTheme,
  MarketThemeMonthlyReturnResponse,
  MarketThemeMonthlyReturnThemeItem,
  MarketThemeReturnRecalculationPreview,
  MarketThemeReturnRecalculationResponse,
  MarketThemeReturnRefreshResponse,
  MarketThemeCandidateStatus,
  MarketThemeLevel,
  MarketThemeStock,
  MarketThemeStockSupplyMemo,
  MarketThemeStockSupplySummary,
  MarketThemeType,
} from "@/types/marketTheme";
import type { Stock } from "@/types/stock";
import type { UsThemeSummary } from "@/types/usMarketTheme";

type ActiveTab = "themes" | "mapping" | "candidates" | "usTrend";
type ThemeViewMode = "group" | "theme" | "trend" | "flowTrend" | "prediction";
type PredictionSort = "default" | "desc" | "asc";
type ThemeReturnSort = "default" | "desc" | "asc";
type ThemeStockSort = "default" | "name" | "memo";
type MemoSaveStatus = "idle" | "saving" | "saved" | "error";
type ThemeReturnTrendViewMode = "heatmap" | "line";
type TrendSortMode = "CURRENT_STRENGTH" | "ROLLING_30D_RETURN";
const THEME_PAGE_SIZE = 50;
const THEME_RETURN_LINE_COLORS = [
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#9333ea",
  "#ea580c",
  "#0891b2",
  "#4f46e5",
  "#be123c",
  "#65a30d",
  "#7c3aed",
  "#0f766e",
  "#c2410c",
  "#0369a1",
  "#a21caf",
  "#15803d",
  "#b91c1c",
];

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function toPriceFlowErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "가격·수급 갱신 API 또는 작업 상태를 찾을 수 없습니다. 백엔드 서버를 재시작해 주세요.";
    if (error.status === 409) return "이미 가격·수급 갱신 작업이 실행 중입니다.";
    if (error.status === 500) return "가격·수급 갱신 작업을 시작하지 못했습니다.";
    if (error.status === 0 || error.status === 408) return "서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인해 주세요.";
  }
  return toErrorMessage(error, "테마 등락률&수급 갱신에 실패했습니다. Kiwoom REST 연결 상태를 확인해 주세요.");
}

function parseKeywordsInput(value: string): string[] {
  return value
    .split(/\r?\n|,/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

function sourceLabel(source: string): string {
  if (source === "news") return "\uB274\uC2A4";
  if (source === "disclosure") return "\uACF5\uC2DC";
  if (source === "supply_event" || source === "kiwoom_supply_event") return "\uC218\uAE09\uC774\uBCA4\uD2B8";
  if (source === "manual") return "manual";
  return source;
}

function ThemeLinkedStockTraderChart({
  stockCode,
  stockName,
  type,
  title,
  onOpen,
}: {
  stockCode: string;
  stockName: string;
  type: NaverTraderChartType;
  title: string;
  onOpen: (chart: { url: string; alt: string; title?: string }) => void;
}) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setHasError(false);
  }, [stockCode, type]);

  if (!stockCode) {
    return <p className="selected-empty-message">종목코드가 없어 매매동향 이미지를 표시할 수 없습니다.</p>;
  }

  const url = buildNaverTraderChartUrl(type, stockCode);
  const alt = `${stockName || stockCode} ${title}`;

  return (
    <button
      type="button"
      className={`theme-stock-trader-chart-card ${hasError ? "is-error" : ""}`}
      onClick={() => {
        if (!hasError) onOpen({ url, alt, title });
      }}
      disabled={hasError}
    >
      <div className="theme-stock-trader-chart-title">{title}</div>
      {hasError ? (
        <div className="theme-stock-trader-chart-fallback">이미지를 불러오지 못했습니다.</div>
      ) : (
        <img src={url} alt={alt} loading="lazy" onError={() => setHasError(true)} />
      )}
    </button>
  );
}

function statusLabel(status: MarketThemeCandidateStatus): string {
  if (status === "pending") return "승인 대기";
  if (status === "approved") return "승인 완료";
  if (status === "rejected") return "거절";
  return "보류";
}

function themeTypeLabel(type: MarketThemeType): string {
  if (type === "theme") return "테마";
  if (type === "industry") return "산업";
  if (type === "custom") return "커스텀";
  return "텔레그램";
}

function themeLevelLabel(level?: MarketThemeLevel): string {
  return level === "THEME_GROUP" ? "테마그룹" : "테마";
}

function themeGroupSortName(theme: MarketTheme): string {
  if (theme.theme_level === "THEME_GROUP") return theme.theme_name || "";
  return theme.parent_theme_name || "미지정";
}

const fmtPct = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};

const fmtEok = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
};


const formatDateInputValue = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseDateInputValue = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
};

const getDateInputValue = () => formatDateInputValue(new Date());

const formatThemeReturnDateLabel = (value?: string | null) => {
  if (!value) return "-";
  const datePart = value.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return datePart.replace(/-/g, ".");
  return value;
};

const getDateRange = (startDate: string, endDate: string) => {
  const dates: string[] = [];
  const start = parseDateInputValue(startDate);
  const end = parseDateInputValue(endDate);
  for (const day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
    dates.push(formatDateInputValue(day));
  }
  return dates;
};


const formatHeatmapDayLabel = (date: string): string => date.slice(8, 10);

const fmtHeatmapCellPct = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}`;
};
const heatmapTextClass = (rate: number | null | undefined) => {
  if (rate == null || Number.isNaN(Number(rate))) return "theme-return-heatmap__value-text--empty";
  if (Number(rate) <= -20) return "theme-return-heatmap__value-text--negative-strong";
  if (Number(rate) < 0) return "theme-return-heatmap__value-text--negative";
  if (Number(rate) >= 20) return "theme-return-heatmap__value-text--positive-strong";
  if (Number(rate) > 0) return "theme-return-heatmap__value-text--positive";
  return "theme-return-heatmap__value-text--empty";
};
const getRelativeStrengthColor = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(Number(value))) return "#F8FAFC";
  if (value < 20) return "#DBEAFE";
  if (value < 40) return "#EFF6FF";
  if (value < 60) return "#F1F5F9";
  if (value < 80) return "#FEE2E2";
  return "#F87171";
};
const relativeStrengthTextClass = (value: number | null | undefined) => value == null ? "theme-return-heatmap__value-text--empty" : Number(value) >= 80 ? "theme-return-heatmap__value-text--positive-strong" : Number(value) >= 60 ? "theme-return-heatmap__value-text--positive" : Number(value) < 40 ? "theme-return-heatmap__value-text--negative" : "theme-return-heatmap__value-text--empty";
const returnToneClass = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "theme-return-empty";
  if (Number(value) > 0) return "theme-return-positive";
  if (Number(value) < 0) return "theme-return-negative";
  return "theme-return-neutral";
};

function buildLinePath(points: Array<{ x: number; y: number }>): string {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
}

function splitLineSegments(points: Array<{ x: number; y: number } | null>): Array<Array<{ x: number; y: number }>> {
  const segments: Array<Array<{ x: number; y: number }>> = [];
  let current: Array<{ x: number; y: number }> = [];
  points.forEach((point) => {
    if (!point) {
      if (current.length > 0) segments.push(current);
      current = [];
      return;
    }
    current.push(point);
  });
  if (current.length > 0) segments.push(current);
  return segments;
}

function ThemeReturnLineChart({
  themes,
  dates,
  hoveredThemeId,
  onHoverTheme,
}: {
  themes: MarketThemeMonthlyReturnThemeItem[];
  dates: string[];
  hoveredThemeId: number | null;
  onHoverTheme: (themeId: number | null) => void;
}) {
  const chartWidth = 840;
  const chartHeight = 500;
  const margin = { top: 24, right: 18, bottom: 34, left: 44 };
  const innerWidth = chartWidth - margin.left - margin.right;
  const innerHeight = chartHeight - margin.top - margin.bottom;
  const validDateSet = new Set<string>();
  themes.forEach((theme) => {
    theme.daily_returns.forEach((day) => {
      const value = Number(day.rolling_30d_change_rate);
      if (day.rolling_30d_change_rate != null && Number.isFinite(value)) {
        validDateSet.add(day.return_date);
      }
    });
  });
  const lineDates = dates.filter((date) => validDateSet.has(date));

  const series = themes.map((theme, index) => {
    const dailyMap = new Map(theme.daily_returns.map((item) => [item.return_date, item]));
    const values = lineDates.map((date) => {
      const dailyReturn = dailyMap.get(date);
      const raw = dailyReturn?.rolling_30d_change_rate;
      const numberValue = Number(raw);
      const value = raw == null || !Number.isFinite(numberValue) ? null : numberValue;
      return { date, returnRate: value };
    });
    const lastValue = [...values].reverse().find((item) => item.returnRate != null)?.returnRate ?? null;
    const lastDailyValue = [...lineDates]
      .reverse()
      .map((date) => dailyMap.get(date)?.avg_change_rate)
      .find((value) => value != null && Number.isFinite(Number(value))) ?? null;
    return {
      themeId: theme.theme_id,
      themeName: theme.theme_name,
      color: THEME_RETURN_LINE_COLORS[index % THEME_RETURN_LINE_COLORS.length],
      lastValue,
      lastDailyValue,
      values,
    };
  });
  const allValues = series.flatMap((item) => item.values.map((value) => value.returnRate).filter((value): value is number => value != null));
  const hasData = lineDates.length > 0 && allValues.length > 0;
  if (!hasData) {
    return <div className="theme-return-line-empty">선그래프로 표시할 거래일 데이터가 없습니다.</div>;
  }

  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  const yMin = rawMin < -30 ? Math.floor(rawMin / 10) * 10 : -30;
  const yMax = rawMax > 30 ? Math.ceil(rawMax / 10) * 10 : 30;
  const yTicks = Array.from({ length: Math.floor((yMax - yMin) / 10) + 1 }, (_, index) => yMin + index * 10);
  const targetXTickCount = Math.min(7, Math.max(2, lineDates.length));
  const xTicks = lineDates.filter((_, index) => {
    if (index === 0 || index === lineDates.length - 1) return true;
    if (targetXTickCount <= 2) return false;
    const tickIndex = Math.round(((targetXTickCount - 1) * index) / (lineDates.length - 1));
    const tickDateIndex = Math.round((tickIndex * (lineDates.length - 1)) / (targetXTickCount - 1));
    return tickDateIndex === index;
  });
  const xScale = (index: number) => margin.left + (lineDates.length <= 1 ? innerWidth / 2 : (innerWidth * index) / (lineDates.length - 1));
  const yScale = (value: number) => margin.top + innerHeight - ((value - yMin) / (yMax - yMin)) * innerHeight;
  const zeroY = yScale(0);
  const linePanelStyle = {
    "--theme-return-line-chart-height": `${chartHeight}px`,
    "--theme-return-line-plot-top": `${margin.top}px`,
    "--theme-return-line-plot-bottom": `${margin.bottom}px`,
  } as CSSProperties;

  return (
    <div className="theme-return-line-panel" style={linePanelStyle}>
      <div className="theme-return-line-header">
        <div>
          <strong>테마별 30일 누적 등락률 선그래프</strong>
          <span>각 날짜 기준 최근 30일 일별 테마 등락률을 단순 합산해 비교합니다. 히트맵은 기존처럼 일별 등락률을 표시합니다.</span>
        </div>
      </div>
      <div className="theme-return-line-body">
        <div className="theme-return-line-chart">
          <svg className="theme-return-line-svg" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" role="img" aria-label="테마별 30일 누적 등락률 선그래프">
            {yTicks.map((tick) => {
              const y = yScale(tick);
              return (
                <g key={`y-${tick.toFixed(2)}`}>
                  <line className="theme-return-line-grid" x1={margin.left} x2={chartWidth - margin.right} y1={y} y2={y} />
                  <text className="theme-return-line-axis-label theme-return-line-y-label" x={margin.left - 10} y={y + 3} textAnchor="end">{fmtHeatmapCellPct(tick)}%</text>
                </g>
              );
            })}
            {zeroY >= margin.top && zeroY <= margin.top + innerHeight ? <line className="theme-return-line-zero" x1={margin.left} x2={chartWidth - margin.right} y1={zeroY} y2={zeroY} /> : null}
            {xTicks.map((date) => {
              const index = lineDates.indexOf(date);
              const x = xScale(index);
              return (
                <g key={`x-${date}`}>
                  <line className="theme-return-line-grid theme-return-line-grid--vertical" x1={x} x2={x} y1={margin.top} y2={margin.top + innerHeight} />
                  <text className="theme-return-line-axis-label theme-return-line-x-label" x={x} y={chartHeight - 12} textAnchor="middle">{date.slice(5).replace("-", ".")}</text>
                </g>
              );
            })}
            <line className="theme-return-line-axis-line" x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + innerHeight} />
            <line className="theme-return-line-axis-line" x1={margin.left} x2={chartWidth - margin.right} y1={margin.top + innerHeight} y2={margin.top + innerHeight} />
            {series.map((item) => {
              const pointList = item.values.map((value, index) => {
                if (value.returnRate == null) return null;
                return { x: xScale(index), y: yScale(value.returnRate) };
              });
              const segments = splitLineSegments(pointList).filter((segment) => segment.length > 1);
              const active = hoveredThemeId === item.themeId;
              const muted = hoveredThemeId != null && !active;
              return segments.map((segment, segmentIndex) => (
                <path
                  key={`${item.themeId}-${segmentIndex}`}
                  className={`theme-return-line-path ${active ? "theme-return-line-path-active" : ""} ${muted ? "theme-return-line-path-muted" : ""}`}
                  d={buildLinePath(segment)}
                  fill="none"
                  stroke={item.color}
                  onMouseEnter={() => onHoverTheme(item.themeId)}
                  onMouseLeave={() => onHoverTheme(null)}
                >
                  <title>{`${item.themeName} / 30일 누적 ${fmtPct(item.lastValue)} / 최근 일별 ${fmtPct(item.lastDailyValue)}`}</title>
                </path>
              ));
            })}
          </svg>
        </div>
        <div className="theme-return-line-legend-shell" onMouseLeave={() => onHoverTheme(null)}>
          <div className="theme-return-line-legend">
            {series.map((item) => {
              const active = hoveredThemeId === item.themeId;
              const muted = hoveredThemeId != null && !active;
              return (
                <button
                  key={item.themeId}
                  type="button"
                  className={`theme-return-line-legend-item ${active ? "theme-return-line-legend-item-active" : ""} ${muted ? "theme-return-line-legend-item-muted" : ""}`}
                  onMouseEnter={() => onHoverTheme(item.themeId)}
                  onFocus={() => onHoverTheme(item.themeId)}
                  onBlur={() => onHoverTheme(null)}
                >
                  <span className="theme-return-line-legend-color" style={{ background: item.color }} />
                  <span className="theme-return-line-legend-text">
                    <strong>{item.themeName}</strong>
                    <em>30일 누적 {fmtPct(item.lastValue)} · 최근 일별 {fmtPct(item.lastDailyValue)}</em>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function MarketThemesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const marketScope = searchParams.get("market")?.toLowerCase() === "us" ? "US" : "KR";
  const refreshPollingTokenRef = useRef(0);
  const observationDeepLinkOpenedRef = useRef(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("themes");
  const [usSummary, setUsSummary] = useState<UsThemeSummary>({ theme_groups: 0, themes: 0, active_themes: 0, linked_stocks: 0 });

  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [themeStocks, setThemeStocks] = useState<MarketThemeStock[]>([]);
  const themeStocksCacheRef = useRef(new Map<number, MarketThemeStock[]>());
  const themeStocksInFlightRef = useRef(new Map<number, Promise<MarketThemeStock[]>>());
  const themeStocksRequestRef = useRef(0);
  const [themeStockSort, setThemeStockSort] = useState<ThemeStockSort>("default");
  const [memoDrafts, setMemoDrafts] = useState<Record<number, string>>({});
  const [memoSaveStatuses, setMemoSaveStatuses] = useState<Record<number, MemoSaveStatus>>({});
  const [editingMemoMappingId, setEditingMemoMappingId] = useState<number | null>(null);
  const memoSavedRef = useRef<Record<number, string>>({});
  const memoPendingRef = useRef<Record<number, string | undefined>>({});
  const memoSaveSequenceRef = useRef<Record<number, number>>({});
  const memoSaveChainsRef = useRef<Record<number, Promise<void>>>({});
  const memoSavedTimersRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const [candidates, setCandidates] = useState<MarketThemeCandidate[]>([]);

  const [themeFilterType, setThemeFilterType] = useState<"all" | MarketThemeType>("all");
  const [themeFilterActive, setThemeFilterActive] = useState<"all" | "1" | "0">("all");
  const [themeFilterSupply, setThemeFilterSupply] = useState<"all" | "1" | "0">("all");
  const [themeFilterKeyword, setThemeFilterKeyword] = useState("");
  const [themeViewMode, setThemeViewMode] = useState<ThemeViewMode>(() => searchParams.get("view") === "prediction" ? "prediction" : "theme");
  const [themeFilterGroupId, setThemeFilterGroupId] = useState<"all" | string>("all");
  const [expandedThemeGroupIds, setExpandedThemeGroupIds] = useState<Set<number>>(() => new Set());
  const [mappingThemeGroupId, setMappingThemeGroupId] = useState<"all" | string>("all");
  const [mappingThemeSearchText, setMappingThemeSearchText] = useState("");
  const [mappingAllThemesSelected, setMappingAllThemesSelected] = useState(false);
  const [mappingThemeDropdownOpen, setMappingThemeDropdownOpen] = useState(false);
  const [themePage, setThemePage] = useState(1);

  const [candidateStatusFilter, setCandidateStatusFilter] = useState<"all" | MarketThemeCandidateStatus>("pending");
  const [candidateSourceFilter, setCandidateSourceFilter] = useState<"all" | "news" | "disclosure">("all");
  const [lookbackDays, setLookbackDays] = useState(7);

  const [stockSearchKeyword, setStockSearchKeyword] = useState("");
  const [stockSearchResults, setStockSearchResults] = useState<Stock[]>([]);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [generatingCandidates, setGeneratingCandidates] = useState(false);
  const [refreshingReturns, setRefreshingReturns] = useState(false);
  const [refreshFailures, setRefreshFailures] = useState<NonNullable<MarketThemeReturnRefreshResponse["failure_items"]>>([]);
  const [themeReturnSort, setThemeReturnSort] = useState<ThemeReturnSort>("default");
  const [trendEndDate, setTrendEndDate] = useState(getDateInputValue());
  const [trendThemeGroupId, setTrendThemeGroupId] = useState<"all" | string>("all");
  const [trendKeyword, setTrendKeyword] = useState("");
  const [trendLimit, setTrendLimit] = useState<"all" | string>("all");
  const [trendViewMode, setTrendViewMode] = useState<ThemeReturnTrendViewMode>("heatmap");
  const [trendSortMode, setTrendSortMode] = useState<TrendSortMode>("CURRENT_STRENGTH");
  const [trendStrengthInfoOpen, setTrendStrengthInfoOpen] = useState(false);
  const [hoveredTrendThemeId, setHoveredTrendThemeId] = useState<number | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendData, setTrendData] = useState<MarketThemeMonthlyReturnResponse | null>(null);
  const [predictionSort, setPredictionSort] = useState<PredictionSort>("default");
  const [returnRecalculationTheme, setReturnRecalculationTheme] = useState<{ themeId: number; themeName: string } | null>(null);
  const [returnRecalculationPreview, setReturnRecalculationPreview] = useState<MarketThemeReturnRecalculationPreview | null>(null);
  const [returnRecalculationResult, setReturnRecalculationResult] = useState<MarketThemeReturnRecalculationResponse | null>(null);
  const [returnRecalculationLoading, setReturnRecalculationLoading] = useState(false);
  const [returnRecalculationRunning, setReturnRecalculationRunning] = useState(false);
  const [returnRecalculationError, setReturnRecalculationError] = useState("");
  const [themeDetailRequest, setThemeDetailRequest] = useState<{ themeId: number; dataDate: string | null; flowContext: MarketThemeDetailFlowContext } | null>(null);
  const [stockDrawerOpen, setStockDrawerOpen] = useState(false);
  const [selectedLinkedStock, setSelectedLinkedStock] = useState<MarketThemeStock | null>(null);
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string; title?: string } | null>(null);
  const [stockMemos, setStockMemos] = useState<MarketThemeStockSupplyMemo[]>([]);
  const [stockMemoLoading, setStockMemoLoading] = useState(false);
  const [stockMemoError, setStockMemoError] = useState("");
  const [stockSupplySummary, setStockSupplySummary] = useState<MarketThemeStockSupplySummary | null>(null);
  const [stockSupplyLoading, setStockSupplyLoading] = useState(false);
  const [stockSupplyError, setStockSupplyError] = useState("");

  useEffect(() => () => {
    refreshPollingTokenRef.current += 1;
    Object.values(memoSavedTimersRef.current).forEach(clearTimeout);
  }, []);

  useEffect(() => {
    setMemoDrafts((previous) => {
      const next = { ...previous };
      themeStocks.forEach((row) => {
        if (next[row.mapping_id] === undefined) next[row.mapping_id] = row.stock_memo ?? "";
        if (memoPendingRef.current[row.mapping_id] === undefined) {
          memoSavedRef.current[row.mapping_id] = row.stock_memo ?? "";
        }
      });
      return next;
    });
  }, [themeStocks]);
  const [showAllSupplyDates, setShowAllSupplyDates] = useState(false);
  const [supplyCountSort, setSupplyCountSort] = useState<SupplyCountSort>("default");
  const [supplyCountInfoOpen, setSupplyCountInfoOpen] = useState(false);
  const [updatingPrimaryMappingId, setUpdatingPrimaryMappingId] = useState<number | null>(null);
  const mappingThemePickerRef = useRef<HTMLDivElement | null>(null);
  const supplyCountInfoRef = useRef<HTMLDivElement | null>(null);
  const trendStrengthInfoRef = useRef<HTMLDivElement | null>(null);

  const [themeModalOpen, setThemeModalOpen] = useState(false);
  const [deleteThemeTarget, setDeleteThemeTarget] = useState<MarketTheme | null>(null);
  const [deletingTheme, setDeletingTheme] = useState(false);
  const [deleteThemeError, setDeleteThemeError] = useState("");
  const [formThemeId, setFormThemeId] = useState<number | null>(null);
  const [themeLevel, setThemeLevel] = useState<MarketThemeLevel>("THEME");
  const [parentThemeId, setParentThemeId] = useState<string>("");
  const [themeName, setThemeName] = useState("");
  const [themeType, setThemeType] = useState<MarketThemeType>("theme");
  const [description, setDescription] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [sortOrder, setSortOrder] = useState(100);
  const [isSupplyTheme, setIsSupplyTheme] = useState(0);
  const [isActive, setIsActive] = useState(1);

  const sortedThemes = useMemo(
    () => {
      const groupById = new Map(
        themes
          .filter((theme) => theme.theme_level === "THEME_GROUP")
          .map((theme) => [theme.id, theme] as const),
      );
      const groupSortOrder = (theme: MarketTheme) => {
        if (theme.theme_level === "THEME_GROUP") return theme.sort_order;
        return theme.parent_theme_id == null
          ? Number.MAX_SAFE_INTEGER
          : groupById.get(theme.parent_theme_id)?.sort_order ?? Number.MAX_SAFE_INTEGER;
      };
      return [...themes].sort((a, b) => {
        const groupOrderCompare = groupSortOrder(a) - groupSortOrder(b);
        if (groupOrderCompare !== 0) return groupOrderCompare;
        const groupNameCompare = themeGroupSortName(a).localeCompare(themeGroupSortName(b), "ko-KR");
        if (groupNameCompare !== 0) return groupNameCompare;
        if (a.theme_level !== b.theme_level) return a.theme_level === "THEME_GROUP" ? -1 : 1;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        const nameCompare = a.theme_name.localeCompare(b.theme_name, "ko-KR");
        return nameCompare !== 0 ? nameCompare : a.id - b.id;
      });
    },
    [themes],
  );
  const themeGroups = useMemo(
    () => sortedThemes.filter((row) => row.theme_level === "THEME_GROUP"),
    [sortedThemes],
  );

  const manageableThemes = useMemo(
    () => sortedThemes.filter((row) => row.theme_level !== "THEME_GROUP"),
    [sortedThemes],
  );

  const filteredThemes = useMemo(() => {
    const keyword = themeFilterKeyword.trim().toLowerCase();
    const rows = sortedThemes.filter((row) => {
      if (themeViewMode === "group" && row.theme_level !== "THEME_GROUP") return false;
      if (themeViewMode === "theme" && row.theme_level === "THEME_GROUP") return false;
      if (themeViewMode === "theme" && themeFilterGroupId !== "all" && String(row.parent_theme_id ?? "") !== themeFilterGroupId) return false;
      if (themeFilterType !== "all" && row.theme_type !== themeFilterType) return false;
      if (themeFilterActive !== "all" && String(row.is_active) !== themeFilterActive) return false;
      if (themeFilterSupply !== "all" && String(row.is_supply_theme) !== themeFilterSupply) return false;
      if (!keyword) return true;
      return row.theme_name.toLowerCase().includes(keyword) || row.keywords.join(" ").toLowerCase().includes(keyword);
    });
    const activeFirstRows = [...rows].sort((a, b) => b.is_active - a.is_active);
    if (themeViewMode !== "theme" || themeReturnSort === "default") return activeFirstRows;
    return activeFirstRows.sort((a, b) => {
      const av = a.latest_return?.avg_change_rate;
      const bv = b.latest_return?.avg_change_rate;
      const aMissing = av == null;
      const bMissing = bv == null;
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      return themeReturnSort === "desc" ? bv - av : av - bv;
    });
  }, [sortedThemes, themeFilterActive, themeFilterGroupId, themeFilterKeyword, themeFilterSupply, themeFilterType, themeReturnSort, themeViewMode]);

  const themeTotalPages = Math.max(1, Math.ceil(filteredThemes.length / THEME_PAGE_SIZE));
  const safeThemePage = Math.min(themePage, themeTotalPages);
  const themePageStart = filteredThemes.length === 0 ? 0 : (safeThemePage - 1) * THEME_PAGE_SIZE + 1;
  const themePageEnd = Math.min(filteredThemes.length, safeThemePage * THEME_PAGE_SIZE);
  const pagedThemes = filteredThemes.slice((safeThemePage - 1) * THEME_PAGE_SIZE, safeThemePage * THEME_PAGE_SIZE);


  const trendDates = useMemo(
    () => (trendData ? getDateRange(trendData.display_start_date, trendData.display_end_date).slice(-29) : []),
    [trendData],
  );
  const trendThemes = useMemo(() => {
    const rows = trendData?.themes ?? [];
    if (predictionSort === "default") return rows;
    const values = trendData?.prediction?.values ?? {};
    return [...rows].sort((a, b) => {
      const av = values[a.theme_id];
      const bv = values[b.theme_id];
      if (av == null) return bv == null ? 0 : 1;
      if (bv == null) return -1;
      return predictionSort === "desc" ? bv - av : av - bv;
    });
  }, [predictionSort, trendData]);
  const trendSummaryCards = useMemo(() => {
    const summary = trendData?.summary;
    return [
      { label: "현재 강도 1위", item: summary?.current_strength_top, value: summary?.current_strength_top?.theme_strength_score, format: "score" },
      { label: "30일 누적 1위", item: summary?.rolling_30d_top ?? summary?.top_rising_theme, value: summary?.rolling_30d_top?.rolling_30d_change_rate ?? summary?.top_rising_theme?.period_compound_return, format: "percent" },
      { label: "거래대금 1위", item: summary?.trading_value_top ?? summary?.top_trading_value_theme, value: summary?.trading_value_top?.total_trading_value_100m ?? summary?.top_trading_value_theme?.total_trading_value_100m, format: "trading" },
      { label: "상승 지속 1위", item: summary?.persistence_top, value: summary?.persistence_top?.persistence_10d, format: "persistence" },
    ];
  }, [trendData]);  const selectedTheme = useMemo(() => sortedThemes.find((x) => x.id === selectedThemeId) ?? null, [sortedThemes, selectedThemeId]);
  const mappingSelectableThemes = useMemo(
    () =>
      manageableThemes.filter((row) => {
        if (row.is_active !== 1) return false;
        if (mappingThemeGroupId !== "all" && String(row.parent_theme_id ?? "") !== mappingThemeGroupId) return false;
        return true;
      }),
    [manageableThemes, mappingThemeGroupId],
  );
  const mappingThemePickerOptions = useMemo(() => {
    const keyword = mappingThemeSearchText.trim().toLowerCase();
    const rows = [...mappingSelectableThemes].sort((a, b) => {
      const aRate = a.latest_return?.avg_change_rate ?? Number.NEGATIVE_INFINITY;
      const bRate = b.latest_return?.avg_change_rate ?? Number.NEGATIVE_INFINITY;
      if (aRate !== bRate) return bRate - aRate;
      return a.theme_name.localeCompare(b.theme_name, "ko-KR");
    });
    const filtered = keyword
      ? rows.filter((row) => row.theme_name.toLowerCase().includes(keyword) || (row.parent_theme_name || "").toLowerCase().includes(keyword) || row.keywords.join(" ").toLowerCase().includes(keyword))
      : rows;
    return filtered.slice(0, 10);
  }, [mappingSelectableThemes, mappingThemeSearchText]);
  const mappingThemeInputValue = mappingAllThemesSelected && mappingThemeGroupId === "all" ? "테마 전체" : mappingThemeSearchText || selectedTheme?.theme_name || "";
  const showMappingThemeAllOption = mappingThemeGroupId === "all";

  const selectedThemeGroup = useMemo(
    () => themeGroups.find((row) => String(row.id) === mappingThemeGroupId) ?? null,
    [mappingThemeGroupId, themeGroups],
  );
  const activeThemeStocks = useMemo(() => themeStocks.filter((x) => x.is_active === 1), [themeStocks]);
  const displayedThemeStocks = useMemo(() => {
    if (themeStockSort === "name") {
      return [...activeThemeStocks].sort((a, b) => a.stock_name.localeCompare(b.stock_name, "ko-KR") || a.stock_id - b.stock_id);
    }
    if (themeStockSort === "memo") {
      return [...activeThemeStocks].sort((a, b) => {
        const aMemo = (a.stock_memo ?? "").trim();
        const bMemo = (b.stock_memo ?? "").trim();
        if (!aMemo && bMemo) return 1;
        if (aMemo && !bMemo) return -1;
        return aMemo.localeCompare(bMemo, "ko-KR") || a.stock_name.localeCompare(b.stock_name, "ko-KR") || a.stock_id - b.stock_id;
      });
    }
    if (supplyCountSort === "default") return activeThemeStocks;
    return [...activeThemeStocks].sort((a, b) => compareThemeStocksBySupplyCount(a, b, supplyCountSort));
  }, [activeThemeStocks, supplyCountSort, themeStockSort]);
  const isMappingAllThemesSelected = mappingAllThemesSelected && !selectedThemeId && mappingThemeGroupId === "all";
  const chartSidcode = useMemo(() => {
    const freshnessKey = selectedTheme?.latest_return?.last_refreshed_at
      ?? selectedTheme?.latest_return?.return_date
      ?? getDateInputValue();
    return String(freshnessKey).replace(/\D/g, "") || getDateInputValue().replace(/\D/g, "");
  }, [selectedTheme?.latest_return?.last_refreshed_at, selectedTheme?.latest_return?.return_date]);
  const selectedLinkedStockCode = useMemo(() => normalizeNaverStockCode(selectedLinkedStock?.stock_code), [selectedLinkedStock?.stock_code]);
  const connectedStockIdSet = useMemo(() => new Set(activeThemeStocks.map((x) => x.stock_id)), [activeThemeStocks]);
  const primaryCount = useMemo(() => activeThemeStocks.filter((x) => x.is_primary === 1).length, [activeThemeStocks]);

  const pendingCandidatesCount = useMemo(() => candidates.filter((x) => x.status === "pending").length, [candidates]);
  const activeThemesCount = useMemo(() => manageableThemes.filter((x) => x.is_active === 1).length, [manageableThemes]);
  const supplyThemesCount = useMemo(() => manageableThemes.filter((x) => x.is_supply_theme === 1).length, [manageableThemes]);
  const linkedStockCount = useMemo(
    () => manageableThemes.filter((x) => x.is_active === 1).reduce((sum, theme) => sum + (theme.stock_count ?? 0), 0),
    [manageableThemes],
  );
  const latestThemeReturnRefresh = useMemo<{ returnDate: string; refreshedAt: string | null } | null>(() => {
    return manageableThemes.reduce<{ returnDate: string; refreshedAt: string | null } | null>((latest, theme) => {
      const returnDate = theme.latest_return?.return_date;
      if (!returnDate) return latest;
      const refreshedAt = theme.latest_return?.last_refreshed_at ?? null;
      if (!latest || returnDate > latest.returnDate || (returnDate === latest.returnDate && (refreshedAt ?? "") > (latest.refreshedAt ?? ""))) {
        return { returnDate, refreshedAt };
      }
      return latest;
    }, null);
  }, [manageableThemes]);
  const themeGroupCount = useMemo(() => themes.filter((x) => x.theme_level === "THEME_GROUP").length, [themes]);
  const themeManagementTitle = themeViewMode === "group" ? "테마그룹 관리" : themeViewMode === "trend" ? "테마등락추이" : themeViewMode === "flowTrend" ? "테마수급추이" : themeViewMode === "prediction" ? "테마관찰우선순위" : "테마별 관리";

  const resetForm = () => {
    setFormThemeId(null);
    setThemeLevel("THEME");
    setParentThemeId("");
    setThemeName("");
    setThemeType("theme");
    setDescription("");
    setKeywordsText("");
    setSortOrder(100);
    setIsSupplyTheme(0);
    setIsActive(1);
  };

  const loadThemes = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await repositories.marketThemes.list({ limit: 500 });
      setThemes(rows);
      setSelectedThemeId((prev) => {
        if (prev && rows.some((row) => row.id === prev && row.theme_level !== "THEME_GROUP")) return prev;
        return rows.find((row) => row.theme_level !== "THEME_GROUP")?.id ?? null;
      });
    } catch (e) {
      setError(toErrorMessage(e, "테마 목록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const fetchThemeStocks = async (themeId: number, force = false): Promise<MarketThemeStock[]> => {
    const cached = themeStocksCacheRef.current.get(themeId);
    if (!force && cached) return cached;
    const inFlight = themeStocksInFlightRef.current.get(themeId);
    if (!force && inFlight) return inFlight;

    const request = repositories.marketThemes.listThemeStocks(themeId);
    themeStocksInFlightRef.current.set(themeId, request);
    try {
      const rows = await request;
      if (themeStocksInFlightRef.current.get(themeId) === request) {
        themeStocksCacheRef.current.set(themeId, rows);
      }
      return rows;
    } finally {
      if (themeStocksInFlightRef.current.get(themeId) === request) {
        themeStocksInFlightRef.current.delete(themeId);
      }
    }
  };

  const loadThemeStocks = async (themeId: number | null, force = false) => {
    const requestId = ++themeStocksRequestRef.current;
    try {
      if (themeId) {
        const rows = await fetchThemeStocks(themeId, force);
        if (requestId === themeStocksRequestRef.current) setThemeStocks(rows);
        return;
      }
      if (!isMappingAllThemesSelected) {
        setThemeStocks([]);
        return;
      }
      const targetThemes = mappingSelectableThemes.filter((row) => row.theme_level !== "THEME_GROUP" && row.is_active === 1);
      if (targetThemes.length === 0) {
        setThemeStocks([]);
        return;
      }
      const results = await Promise.all(targetThemes.map((theme) => fetchThemeStocks(theme.id)));
      const uniqueByStock = new Map<number, MarketThemeStock>();
      results.flat().forEach((row) => {
        if (row.is_active !== 1) return;
        const current = uniqueByStock.get(row.stock_id);
        if (!current || (row.is_primary === 1 && current.is_primary !== 1)) {
          uniqueByStock.set(row.stock_id, row);
        }
      });
      const rows = Array.from(uniqueByStock.values()).sort((a, b) => a.stock_name.localeCompare(b.stock_name, "ko-KR"));
      if (requestId === themeStocksRequestRef.current) setThemeStocks(rows);
    } catch (e) {
      if (requestId !== themeStocksRequestRef.current) return;
      setError(toErrorMessage(e, "테마 연결 종목을 불러오지 못했습니다."));
      setThemeStocks([]);
    }
  };
  const onRefreshThemeReturns = async () => {
    if (refreshingReturns) {
      return;
    }
    setRefreshingReturns(true);
    setError("");
    setRefreshFailures([]);
    setMessage("가격·수급 갱신 작업을 요청하고 있습니다.");
    const pollingToken = ++refreshPollingTokenRef.current;
    try {
      const startedJob = await repositories.marketThemes.startPriceFlowRefresh({ scope: "all_active" });
      if (!startedJob.job_id) {
        throw new Error("가격·수급 갱신 작업 번호를 받지 못했습니다.");
      }
      if (pollingToken !== refreshPollingTokenRef.current) return;
      setMessage("활성 테마 연결 종목 준비 → 가격·기술지표 → 투자자·프로그램 수급 → 테마등락률 집계 중...");
      let job = await repositories.marketThemes.getPriceFlowRefreshJob(startedJob.job_id);
      while (job.status === "PENDING" || job.status === "RUNNING") {
        if (pollingToken !== refreshPollingTokenRef.current) return;
        const stageLabels: Record<string, string> = {
          PENDING: "작업 준비",
          TARGETS: "대상 종목 확정",
          PRICE: "가격 수집",
          TECHNICAL: "기술지표 계산",
          FLOW: "투자자·프로그램 수급 수집",
          THEME_RETURN: "테마등락률 집계",
        };
        const progress = job.total_count > 0 ? ` ${job.completed_count}/${job.total_count}` : "";
        setMessage(`${stageLabels[job.stage] ?? job.stage}${progress} · ${job.message ?? "진행 중..."}`);
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        if (pollingToken !== refreshPollingTokenRef.current) return;
        job = await repositories.marketThemes.getPriceFlowRefreshJob(startedJob.job_id);
      }
      if (job.status === "FAILED" || !job.result) {
        throw new Error(job.message || "테마 등락률&수급 갱신 작업이 실패했습니다.");
      }
      const res = job.result;
      setRefreshFailures(res.failure_items ?? []);
      invalidateMarketThemeFlowTrendFrontendCache();
      await Promise.all([loadThemes(), loadThemeReturnTrend()]);
      const totalSeconds = typeof res.total_ms === "number" ? (res.total_ms / 1000).toFixed(1) : null;
      const uniqueCount = res.unique_stock_count ?? res.stock_count;
      const statusLabel = res.job_status === "PARTIAL" ? "부분 완료" : "완료";
      const fallbackMessage = [
        `테마 등락률&수급 갱신 ${statusLabel}`,
        `연결 ${res.theme_stock_link_count ?? res.stock_count}건 · 고유 ${uniqueCount}개`,
        `가격 ${res.price_success_count ?? "-"}/${uniqueCount}`,
        `기술지표 ${res.technical_success_count ?? "-"}/${uniqueCount}`,
        `투자자 수급 ${res.investor_success_count ?? "-"}/${uniqueCount}`,
        `프로그램 수급 ${res.program_success_count ?? "-"}/${uniqueCount}`,
        `테마등락률 ${res.theme_count}개`,
        `기준일 ${res.return_date}`,
        totalSeconds ? `${totalSeconds}초` : "",
      ].filter(Boolean).join(" · ");
      setMessage(res.message || fallbackMessage);
      console.info("[theme-return-refresh]", {
        themes: res.theme_count,
        links: res.theme_stock_link_count,
        uniqueStocks: res.unique_stock_count,
        priceApiCalls: res.price_api_call_count,
        restPostCalls: res.rest_post_calls,
        authTokenIssueCount: res.auth_token_issue_count,
        ka10001Calls: res.ka10001_calls,
        ka10015Calls: res.ka10015_calls,
        stockRows: res.stock_count,
        inserted: res.inserted_count,
        updated: res.updated_count,
        priceFetchMs: res.price_fetch_ms,
        calcMs: res.calc_ms,
        dbUpsertMs: res.db_upsert_ms,
        totalMs: res.total_ms,
      });
    } catch (e) {
      console.error("[theme-price-flow-refresh]", e);
      if (pollingToken === refreshPollingTokenRef.current) setError(toPriceFlowErrorMessage(e));
    } finally {
      if (pollingToken === refreshPollingTokenRef.current) setRefreshingReturns(false);
    }
  };


  const loadThemeReturnTrend = async () => {
    setTrendLoading(true);
    setError("");
    try {
      const rows = await repositories.marketThemes.listRangeReturns({
        end_date: trendEndDate,
        days: 30,
        active_only: true,
        theme_group_id: trendThemeGroupId === "all" ? undefined : Number(trendThemeGroupId),
        keyword: trendKeyword.trim() || undefined,
        limit: trendLimit === "all" ? undefined : Number(trendLimit),
        sort_by: trendSortMode,
      });
      setTrendData(rows);
    } catch (e) {
      setError(toErrorMessage(e, "테마등락추이 데이터를 불러오지 못했습니다."));
      setTrendData(null);
    } finally {
      setTrendLoading(false);
    }
  };
  const openReturnRecalculation = async (theme: MarketThemeMonthlyReturnThemeItem) => {
    setReturnRecalculationTheme({ themeId: theme.theme_id, themeName: theme.theme_name });
    setReturnRecalculationPreview(null);
    setReturnRecalculationResult(null);
    setReturnRecalculationError("");
    setReturnRecalculationLoading(true);
    try {
      const preview = await repositories.marketThemes.getReturnRecalculationPreview(theme.theme_id);
      setReturnRecalculationPreview(preview);
    } catch (e) {
      setReturnRecalculationError(toErrorMessage(e, "테마등락률 재계산 정보를 불러오지 못했습니다."));
    } finally {
      setReturnRecalculationLoading(false);
    }
  };
  const closeReturnRecalculation = () => {
    if (returnRecalculationRunning) return;
    setReturnRecalculationTheme(null);
    setReturnRecalculationPreview(null);
    setReturnRecalculationResult(null);
    setReturnRecalculationError("");
  };
  const runReturnRecalculation = async () => {
    if (!returnRecalculationTheme || returnRecalculationRunning) return;
    setReturnRecalculationRunning(true);
    setReturnRecalculationError("");
    try {
      const result = await repositories.marketThemes.recalculateReturns(returnRecalculationTheme.themeId);
      setReturnRecalculationResult(result);
      setReturnRecalculationPreview(result);
      setMessage(
        `${result.theme_name} 테마등락률 재계산 완료 · ${result.period_from ?? "-"} ~ ${result.period_to ?? "-"} · 갱신 ${result.updated_count}건 · 신규 ${result.inserted_count}건`,
      );
      await loadThemeReturnTrend();
    } catch (e) {
      setReturnRecalculationError(toErrorMessage(e, "테마등락률 재계산에 실패했습니다."));
    } finally {
      setReturnRecalculationRunning(false);
    }
  };
  const openThemeReturnDetail = (
    theme: MarketTheme | MarketThemeMonthlyReturnThemeItem | MarketThemeFlowTrendTheme,
    returnDate?: string,
    flowContext: { actor: MarketThemeFlowTrendActor; metric: MarketThemeFlowTrendMetric; attribution: MarketThemeFlowTrendAttribution } | null = null,
  ) => {
    const themeId = "id" in theme ? theme.id : theme.theme_id;
    setSelectedThemeId(themeId);
    setThemeDetailRequest({
      themeId,
      dataDate: returnDate ?? null,
      flowContext: flowContext ? { actor: flowContext.actor } : null,
    });
  };

  const closeReturnDrawer = () => {
    setThemeDetailRequest(null);
  };

  const closeStockDrawer = () => {
    setStockDrawerOpen(false);
    setSelectedLinkedStock(null);
    setStockMemos([]);
    setStockMemoLoading(false);
    setStockMemoError("");
    setStockSupplySummary(null);
    setStockSupplyLoading(false);
    setStockSupplyError("");
  };

  const loadStockSupplySummary = async (row: MarketThemeStock) => {
    setStockSupplyLoading(true);
    setStockSupplyError("");
    setStockSupplySummary(null);
    setStockMemoLoading(true);
    setStockMemoError("");
    setStockMemos([]);
    try {
      const summary = await repositories.marketThemes.getThemeStockSupplySummary(row.theme_id, row.stock_id);
      setStockSupplySummary(summary);
      setStockMemos(summary.stock_memos ?? []);
    } catch (e) {
      const message = toErrorMessage(e, "수급 이력을 불러오지 못했습니다.");
      setStockSupplyError(message);
      setStockMemoError(message);
    } finally {
      setStockSupplyLoading(false);
      setStockMemoLoading(false);
    }
  };

  const openLinkedStockDrawer = (row: MarketThemeStock) => {
    setSelectedLinkedStock(row);
    setStockDrawerOpen(true);
    setShowAllSupplyDates(false);
    void loadStockSupplySummary(row);
  };
  const toggleThemeReturnSort = () => {
    setThemeReturnSort((prev) => (prev === "default" ? "desc" : prev === "desc" ? "asc" : "default"));
  };

  const toggleSupplyCountSort = () => {
    setThemeStockSort("default");
    setSupplyCountSort((prev) => (prev === "default" ? "desc" : prev === "desc" ? "asc" : "default"));
  };

  const beginThemeStockMemoEdit = (row: MarketThemeStock) => {
    const mappingId = row.mapping_id;
    const saved = memoSavedRef.current[mappingId] ?? row.stock_memo ?? "";
    setMemoDrafts((previous) => ({ ...previous, [mappingId]: previous[mappingId] ?? saved }));
    setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "idle" }));
    setEditingMemoMappingId(mappingId);
  };

  const saveThemeStockMemo = (row: MarketThemeStock) => {
    const mappingId = row.mapping_id;
    const normalized = (memoDrafts[mappingId] ?? row.stock_memo ?? "").trim();
    const saved = (memoSavedRef.current[mappingId] ?? row.stock_memo ?? "").trim();
    if (normalized === saved) {
      setMemoDrafts((previous) => ({ ...previous, [mappingId]: saved }));
      setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "idle" }));
      setEditingMemoMappingId((current) => current === mappingId ? null : current);
      return;
    }
    if (memoPendingRef.current[mappingId] === normalized) return;

    const sequence = (memoSaveSequenceRef.current[mappingId] ?? 0) + 1;
    memoSaveSequenceRef.current[mappingId] = sequence;
    memoPendingRef.current[mappingId] = normalized;
    setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "saving" }));
    clearTimeout(memoSavedTimersRef.current[mappingId]);

    const previousSave = memoSaveChainsRef.current[mappingId] ?? Promise.resolve();
    const nextSave = previousSave.catch(() => undefined).then(async () => {
      try {
        const updated = await repositories.marketThemes.updateThemeStockMemo(
          row.theme_id,
          row.stock_id,
          { stock_memo: normalized || null },
        );
        memoSavedRef.current[mappingId] = updated.stock_memo ?? "";
        setThemeStocks((previous) => {
          const next = previous.map((item) => item.mapping_id === mappingId ? updated : item);
          themeStocksCacheRef.current.set(row.theme_id, next);
          return next;
        });
        if (memoSaveSequenceRef.current[mappingId] === sequence) {
          setMemoDrafts((previous) => {
            const currentDraft = previous[mappingId] ?? "";
            return currentDraft.trim() === normalized
              ? { ...previous, [mappingId]: updated.stock_memo ?? "" }
              : previous;
          });
          setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "saved" }));
          setEditingMemoMappingId((current) => current === mappingId ? null : current);
          memoSavedTimersRef.current[mappingId] = setTimeout(() => {
            setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "idle" }));
          }, 1200);
        }
      } catch {
        if (memoSaveSequenceRef.current[mappingId] === sequence) {
          setMemoSaveStatuses((previous) => ({ ...previous, [mappingId]: "error" }));
        }
      } finally {
        if (memoPendingRef.current[mappingId] === normalized) delete memoPendingRef.current[mappingId];
      }
    });
    memoSaveChainsRef.current[mappingId] = nextSave;
  };

  const cancelThemeStockMemo = (row: MarketThemeStock) => {
    const saved = memoSavedRef.current[row.mapping_id] ?? row.stock_memo ?? "";
    setMemoDrafts((previous) => ({ ...previous, [row.mapping_id]: saved }));
    setMemoSaveStatuses((previous) => ({ ...previous, [row.mapping_id]: "idle" }));
    setEditingMemoMappingId((current) => current === row.mapping_id ? null : current);
  };
  const loadCandidates = async () => {
    try {
      const rows = await repositories.marketThemes.listCandidates({
        status: candidateStatusFilter === "all" ? undefined : candidateStatusFilter,
        candidate_source: candidateSourceFilter === "all" ? undefined : candidateSourceFilter,
        limit: 200,
      });
      setCandidates(rows);
    } catch (e) {
      setError(toErrorMessage(e, "추천 후보 목록을 불러오지 못했습니다."));
    }
  };

  useEffect(() => {
    if (marketScope === "KR") void Promise.all([loadThemes(), loadCandidates()]);
  }, [marketScope]);

  useEffect(() => {
    if (observationDeepLinkOpenedRef.current || themeViewMode !== "prediction") return;
    const themeId = Number(searchParams.get("theme_id"));
    if (!themeId) return;
    const theme = manageableThemes.find((row) => row.id === themeId);
    if (!theme) return;
    observationDeepLinkOpenedRef.current = true;
    void openThemeReturnDetail(theme);
  }, [manageableThemes, searchParams, themeViewMode]);

  useEffect(() => {
    if (marketScope === "KR") void loadThemeStocks(selectedThemeId);
  }, [selectedThemeId, mappingThemeGroupId, mappingSelectableThemes, mappingAllThemesSelected, marketScope]);

  useEffect(() => {
    if (!stockDrawerOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (zoomedChart) return;
      if (event.key === "Escape") closeStockDrawer();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [stockDrawerOpen, zoomedChart]);

  useEffect(() => {
    if (!supplyCountInfoOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!supplyCountInfoRef.current?.contains(event.target as Node)) setSupplyCountInfoOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSupplyCountInfoOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [supplyCountInfoOpen]);

  useEffect(() => {
    if (!trendStrengthInfoOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!trendStrengthInfoRef.current?.contains(event.target as Node)) setTrendStrengthInfoOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setTrendStrengthInfoOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [trendStrengthInfoOpen]);

  useEffect(() => {
    setSupplyCountSort("default");
    setSupplyCountInfoOpen(false);
  }, [selectedThemeId, mappingAllThemesSelected]);

  useEffect(() => {
    if (!zoomedChart) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setZoomedChart(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [zoomedChart]);

  useEffect(() => {
    if (!selectedLinkedStock) return;
    const stillActive = activeThemeStocks.some((row) => row.mapping_id === selectedLinkedStock.mapping_id);
    if (!stillActive) closeStockDrawer();
  }, [activeThemeStocks, selectedLinkedStock]);

  useEffect(() => {
    setThemePage(1);
  }, [themeFilterActive, themeFilterGroupId, themeFilterKeyword, themeFilterSupply, themeFilterType, themeViewMode]);


  useEffect(() => {
    if (marketScope === "KR" && activeTab === "themes" && themeViewMode === "trend") {
      void loadThemeReturnTrend();
    }
  }, [activeTab, themeViewMode, trendEndDate, trendThemeGroupId, trendLimit, trendSortMode, marketScope]);
  useEffect(() => {
    if (themePage > themeTotalPages) {
      setThemePage(themeTotalPages);
    }
  }, [themePage, themeTotalPages]);
  useEffect(() => {
    if (mappingSelectableThemes.length === 0) {
      setSelectedThemeId(null);
      return;
    }
    if (selectedThemeId && !mappingSelectableThemes.some((row) => row.id === selectedThemeId)) {
      setSelectedThemeId(null);
      setMappingThemeSearchText("");
    }
  }, [mappingSelectableThemes, selectedThemeId]);

  useEffect(() => {
    if (!mappingThemeDropdownOpen) return undefined;
    const onPointerDown = (event: MouseEvent) => {
      if (!mappingThemePickerRef.current?.contains(event.target as Node)) {
        setMappingThemeDropdownOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMappingThemeDropdownOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [mappingThemeDropdownOpen]);

  useEffect(() => {
    if (marketScope === "KR") void loadCandidates();
  }, [candidateSourceFilter, candidateStatusFilter, marketScope]);

  const openCreateThemeModal = () => {
    resetForm();
    setThemeModalOpen(true);
  };

  const openCreateThemeInGroupModal = (themeGroupId: number) => {
    resetForm();
    setThemeLevel("THEME");
    setParentThemeId(String(themeGroupId));
    setThemeModalOpen(true);
  };

  const openEditThemeModal = (theme: MarketTheme) => {
    setFormThemeId(theme.id);
    setThemeLevel(theme.theme_level ?? "THEME");
    setParentThemeId(theme.parent_theme_id ? String(theme.parent_theme_id) : "");
    setThemeName(theme.theme_name);
    setThemeType(theme.theme_type);
    setDescription(theme.description ?? "");
    setKeywordsText(theme.keywords.join("\n"));
    setSortOrder(theme.sort_order);
    setIsSupplyTheme(theme.is_supply_theme ?? 0);
    setIsActive(theme.is_active);
    setThemeModalOpen(true);
  };

  const onSubmitTheme = async () => {
    setMessage("");
    setError("");
    if (!themeName.trim()) {
      setError("테마명은 필수입니다.");
      return;
    }
    const keywords = parseKeywordsInput(keywordsText);
    const nextThemeLevel = themeLevel;
    const nextParentThemeId = nextThemeLevel === "THEME" && parentThemeId ? Number(parentThemeId) : null;
    const nextIsSupplyTheme = nextThemeLevel === "THEME" ? isSupplyTheme : 0;
    try {
      if (formThemeId) {
        await repositories.marketThemes.update(formThemeId, {
          theme_name: themeName.trim(),
          theme_type: themeType,
          theme_level: nextThemeLevel,
          description: description.trim() || null,
          keywords,
          parent_theme_id: nextParentThemeId,
          sort_order: sortOrder,
          is_supply_theme: nextIsSupplyTheme,
          is_active: isActive,
        });
        invalidateMarketThemeFlowTrendFrontendCache();
      } else {
        await repositories.marketThemes.create({
          theme_name: themeName.trim(),
          theme_type: themeType,
          theme_level: nextThemeLevel,
          description: description.trim() || null,
          keywords,
          parent_theme_id: nextParentThemeId,
          sort_order: sortOrder,
          is_supply_theme: nextIsSupplyTheme,
          is_active: isActive,
        });
        invalidateMarketThemeFlowTrendFrontendCache();
      }
      await loadThemes();
      setThemeModalOpen(false);
      resetForm();
      setMessage("테마가 저장되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 저장 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateTheme = async (themeId: number) => {
    const ok = window.confirm("선택한 테마를 비활성화하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.deactivate(themeId);
      invalidateMarketThemeFlowTrendFrontendCache();
      await loadThemes();
      setMessage("테마가 비활성화되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 비활성화 중 오류가 발생했습니다."));
    }
  };

  const onActivateTheme = async (theme: MarketTheme) => {
    const ok = window.confirm("선택한 테마를 다시 활성화하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.update(theme.id, {
        theme_name: theme.theme_name,
        theme_type: theme.theme_type,
        theme_level: theme.theme_level,
        description: theme.description,
        keywords: theme.keywords,
        parent_theme_id: theme.parent_theme_id,
        is_supply_theme: theme.is_supply_theme,
        sort_order: theme.sort_order,
        is_active: 1,
      });
      invalidateMarketThemeFlowTrendFrontendCache();
      await loadThemes();
      setMessage("테마가 활성화되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 활성화 중 오류가 발생했습니다."));
    }
  };

  const onDeleteTheme = async () => {
    if (!deleteThemeTarget || deletingTheme) return;
    setDeletingTheme(true);
    setDeleteThemeError("");
    setMessage("");
    setError("");
    try {
      const result = await repositories.marketThemes.delete(deleteThemeTarget.id);
      invalidateMarketThemeFlowTrendFrontendCache();
      const deletedIds = new Set([
        deleteThemeTarget.id,
        ...themes.filter((theme) => theme.parent_theme_id === deleteThemeTarget.id).map((theme) => theme.id),
      ]);
      deletedIds.forEach((themeId) => {
        themeStocksCacheRef.current.delete(themeId);
        themeStocksInFlightRef.current.delete(themeId);
      });
      if (selectedThemeId != null && deletedIds.has(selectedThemeId)) {
        setSelectedThemeId(null);
        setThemeStocks([]);
      }
      setExpandedThemeGroupIds((previous) => {
        const next = new Set(previous);
        next.delete(deleteThemeTarget.id);
        return next;
      });
      setDeleteThemeTarget(null);
      await loadThemes();
      setMessage(
        result.deleted_theme_count > 1
          ? `테마그룹과 하위 테마 ${result.deleted_theme_count - 1}개가 완전히 삭제되었습니다.`
          : `테마 '${result.deleted_theme_name}'이(가) 완전히 삭제되었습니다.`,
      );
    } catch (e) {
      const nextError = toErrorMessage(e, "테마 삭제 중 오류가 발생했습니다.");
      setDeleteThemeError(nextError);
      setError(nextError);
    } finally {
      setDeletingTheme(false);
    }
  };

  const openDeleteThemeModal = (theme: MarketTheme) => {
    setDeleteThemeError("");
    setDeleteThemeTarget(theme);
  };

  const toggleThemeGroupExpanded = (themeGroupId: number) => {
    setExpandedThemeGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(themeGroupId)) next.delete(themeGroupId);
      else next.add(themeGroupId);
      return next;
    });
  };

  const openThemeStockMappings = (theme: MarketTheme) => {
    setMappingAllThemesSelected(false);
    if (theme.theme_level === "THEME_GROUP") {
      const firstChildTheme = sortedThemes.find((row) => row.parent_theme_id === theme.id && row.theme_level !== "THEME_GROUP" && row.is_active === 1);
      setMappingThemeGroupId(String(theme.id));
      if (firstChildTheme) {
        setMappingThemeSearchText(firstChildTheme.theme_name);
        setSelectedThemeId(firstChildTheme.id);
      }
    } else {
      setMappingThemeGroupId(theme.parent_theme_id ? String(theme.parent_theme_id) : "all");
      setMappingThemeSearchText(theme.theme_name);
      setSelectedThemeId(theme.id);
    }
    setStockSearchResults([]);
    setActiveTab("mapping");
  };

  const selectMappingTheme = (theme: MarketTheme) => {
    setMappingAllThemesSelected(false);
    setSelectedThemeId(theme.id);
    setMappingThemeSearchText(theme.theme_name);
    setMappingThemeDropdownOpen(false);
  };

  const selectMappingAllThemes = () => {
    setMappingAllThemesSelected(true);
    setSelectedThemeId(null);
    setMappingThemeSearchText("");
    setStockSearchResults([]);
    setMappingThemeDropdownOpen(false);
  };

  const clearMappingThemeInput = () => {
    setMappingAllThemesSelected(false);
    setSelectedThemeId(null);
    setMappingThemeSearchText("");
    setStockSearchResults([]);
    setThemeStocks([]);
    setMappingThemeDropdownOpen(true);
  };
  const applyMappingThemeSearchValue = (value: string) => {
    const matchedTheme = mappingSelectableThemes.find((row) => row.theme_name === value)
      ?? mappingSelectableThemes.find((row) => row.theme_name.toLowerCase() === value.trim().toLowerCase());
    setMappingAllThemesSelected(false);
    setMappingThemeSearchText(value);
    setSelectedThemeId(matchedTheme ? matchedTheme.id : null);
    setMappingThemeDropdownOpen(true);
  };

  const onSearchStocks = async () => {
    if (!selectedThemeId) {
      setError("종목을 연결할 테마를 선택해 주세요.");
      return;
    }
    if (selectedTheme?.theme_level === "THEME_GROUP") {
      setError("종목 연결은 테마를 선택해 주세요.");
      return;
    }
    setSearching(true);
    setError("");
    try {
      const rows = await repositories.stocks.list({ keyword: stockSearchKeyword.trim(), is_active: 1, limit: 30 });
      setStockSearchResults(rows);
    } catch (e) {
      setError(toErrorMessage(e, "종목 검색 중 오류가 발생했습니다."));
    } finally {
      setSearching(false);
    }
  };

  const onAddThemeStock = async (stockId: number) => {
    if (!selectedThemeId) return;
    if (selectedTheme?.theme_level === "THEME_GROUP") {
      setError("종목은 테마에만 연결할 수 있습니다.");
      return;
    }
    try {
      await repositories.marketThemes.createThemeStock(selectedThemeId, { stock_id: stockId, is_primary: false });
      invalidateMarketThemeFlowTrendFrontendCache();
      await Promise.all([loadThemeStocks(selectedThemeId, true), loadThemes()]);
      setMessage("테마에 종목이 연결되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "종목 연결 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateMapping = async (mappingId: number) => {
    if (!selectedThemeId) return;
    const ok = window.confirm("선택한 종목을 테마에서 연결 해제하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.deactivateThemeStock(mappingId);
      invalidateMarketThemeFlowTrendFrontendCache();
      if (selectedLinkedStock?.mapping_id === mappingId) closeStockDrawer();
      await Promise.all([loadThemeStocks(selectedThemeId, true), loadThemes()]);
      setMessage("테마 연결이 해제되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "연결 해제 중 오류가 발생했습니다."));
    }
  };

  const onTogglePrimary = async (mappingId: number, checked: boolean) => {
    setUpdatingPrimaryMappingId(mappingId);
    try {
      await repositories.marketThemes.updateThemeStock(mappingId, { is_primary: checked });
      invalidateMarketThemeFlowTrendFrontendCache();
      await loadThemeStocks(selectedThemeId, true);
      setMessage("대표 여부가 변경되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "대표 변경 중 오류가 발생했습니다."));
    } finally {
      setUpdatingPrimaryMappingId(null);
    }
  };

  const onGenerateCandidates = async () => {
    setGeneratingCandidates(true);
    try {
      const result = await repositories.marketThemes.generateCandidates({
        lookback_days: lookbackDays,
        source: candidateSourceFilter,
        limit: 500,
        force: false,
      });
      await loadCandidates();
      setMessage(`추천 후보 생성 완료: ${result.generated_count}건`);
    } catch (e) {
      setError(toErrorMessage(e, "추천 후보 생성 중 오류가 발생했습니다."));
    } finally {
      setGeneratingCandidates(false);
    }
  };

  const onApproveCandidate = async (candidateId: number) => {
    await repositories.marketThemes.approveCandidate(candidateId);
    await Promise.all([loadCandidates(), loadThemes(), loadThemeStocks(selectedThemeId, true)]);
  };

  const onRejectCandidate = async (candidateId: number) => {
    await repositories.marketThemes.rejectCandidate(candidateId, { review_memo: "관련성 낮음" });
    await loadCandidates();
  };

  const onIgnoreCandidate = async (candidateId: number) => {
    await repositories.marketThemes.ignoreCandidate(candidateId, { review_memo: "추가 확인" });
    await loadCandidates();
  };

  const changeMarketScope = (scope: "KR" | "US") => {
    const next = new URLSearchParams(searchParams);
    next.set("market", scope.toLowerCase());
    if (scope === "US") {
      next.delete("view");
      next.delete("theme_id");
      if (activeTab === "candidates") setActiveTab("themes");
      if (!(["group", "theme"] as ThemeViewMode[]).includes(themeViewMode)) setThemeViewMode("theme");
    } else if (activeTab === "usTrend") {
      setActiveTab("themes");
    }
    setSearchParams(next, { replace: true });
  };

  const marketScopeControl = <div className="stock-market-scope market-theme-scope-control" role="group" aria-label="시장 범위">
    <button type="button" className={marketScope === "KR" ? "active" : ""} aria-pressed={marketScope === "KR"} onClick={() => changeMarketScope("KR")}>국내 KRX</button>
    <button type="button" className={marketScope === "US" ? "active" : ""} aria-pressed={marketScope === "US"} onClick={() => changeMarketScope("US")}>미국 US</button>
  </div>;

  if (marketScope === "US") {
    return <div className="space-y-4">
      <div className="journal-hero-row market-theme-hero-row">
        <section className="journal-hero-panel"><h1>시장 테마 관리</h1><p>미국 테마와 연결 종목을 관리합니다.</p></section>
        <section className="journal-summary-compact market-theme-hero-summary us-market-theme-summary" aria-label="미국 시장 테마 요약">
          {[
            ["테마그룹", usSummary.theme_groups], ["전체 테마", usSummary.themes], ["활성 테마", usSummary.active_themes], ["연결 종목", usSummary.linked_stocks],
          ].map(([label, value]) => <div className="journal-summary-mini-card" key={String(label)}><span className="journal-summary-label">{label}</span><strong className="journal-summary-value">{value}</strong></div>)}
        </section>
      </div>
      <div className="market-theme-command-grid">
        <SectionCard title="" className="market-theme-tabs-card"><div className="gpt-domain-tabs market-theme-primary-tabs">
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "themes" ? "active" : ""}`} onClick={() => setActiveTab("themes")}>테마 관리</button>
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "mapping" ? "active" : ""}`} onClick={() => setActiveTab("mapping")}>종목 연결</button>
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "usTrend" ? "active" : ""}`} onClick={() => setActiveTab("usTrend")}>테마등락추이</button>
        </div></SectionCard>
        <SectionCard title="시장" className="market-theme-scope-panel">{marketScopeControl}</SectionCard>
      </div>
      <UsMarketThemesPanel activeTab={activeTab === "mapping" ? "mapping" : activeTab === "usTrend" ? "trend" : "themes"} onSummaryChange={setUsSummary} />
    </div>;
  }

  return (
    <div className="space-y-4">
      <div className="journal-hero-row market-theme-hero-row">
        <section className="journal-hero-panel">
          <h1>시장 테마 관리</h1>
          <p>테마와 연결 종목을 관리합니다.</p>
        </section>

        <section className="journal-summary-compact market-theme-hero-summary" aria-label="시장 테마 요약">
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">테마그룹</span>
            <strong className="journal-summary-value">{themeGroupCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">전체 테마</span>
            <strong className="journal-summary-value">{manageableThemes.length}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">활성 테마</span>
            <strong className="journal-summary-value">{activeThemesCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">수급 테마</span>
            <strong className="journal-summary-value">{supplyThemesCount}</strong>
          </div>
          <div className="journal-summary-mini-card" title="테마에 연결된 활성 종목 연결 수입니다. 같은 종목이 여러 테마에 연결되어 있으면 각각 계산합니다.">
            <span className="journal-summary-label">연결 종목</span>
            <strong className="journal-summary-value">{linkedStockCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">추천 후보</span>
            <strong className="journal-summary-value">{pendingCandidatesCount}</strong>
          </div>
        </section>
      </div>

      {message ? <div className="inline-result inline-success">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}
      {refreshFailures.length > 0 ? (
        <details className="inline-result inline-error">
          <summary>실패 상세 {refreshFailures.length}건</summary>
          <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
            {Array.from(
              refreshFailures.reduce((groups, item) => {
                const key = item.error_code || `${item.stage}:${item.message}`;
                const current = groups.get(key);
                if (current) current.count += 1;
                else groups.set(key, { item, count: 1 });
                return groups;
              }, new Map<string, { item: (typeof refreshFailures)[number]; count: number }>()).values(),
            ).map(({ item, count }) => (
              <div key={`${item.error_code || item.stage}-${item.stock_id || "common"}`}>
                <strong>{item.error_code || item.stage} · {count}종목</strong>
                <div>{item.user_message || item.message}</div>
                {item.stock_code ? <small>{item.stock_name || item.stock_code} ({item.stock_code}) · 재실행 {item.retryable === false ? "불가" : "가능"}</small> : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <div className="market-theme-command-grid">
        <SectionCard title="" className="market-theme-tabs-card">
          <div className="gpt-domain-tabs market-theme-primary-tabs">
            <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "themes" ? "active" : ""}`} onClick={() => { setActiveTab("themes"); setThemeViewMode("theme"); }}>테마 관리</button>
            <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "mapping" ? "active" : ""}`} onClick={() => setActiveTab("mapping")}>종목 연결</button>
            <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "candidates" ? "active" : ""}`} onClick={() => setActiveTab("candidates")}>추천 후보</button>
          </div>
        </SectionCard>
        <SectionCard title="시장" className="market-theme-scope-panel">{marketScopeControl}</SectionCard>
      </div>

      {activeTab === "themes" ? (
        <SectionCard title="" className="market-theme-management-card">
          <div className="theme-view-mode-tabs market-theme-view-toggle">
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "group" ? "active" : ""}`} onClick={() => setThemeViewMode("group")}>
              테마그룹별
            </button>
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "theme" ? "active" : ""}`} onClick={() => setThemeViewMode("theme")}>
              테마별
            </button>
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "trend" ? "active" : ""}`} onClick={() => setThemeViewMode("trend")}>
              테마등락추이
            </button>
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "flowTrend" ? "active" : ""}`} onClick={() => setThemeViewMode("flowTrend")}>
              테마수급추이
            </button>
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "prediction" ? "active" : ""}`} onClick={() => setThemeViewMode("prediction")}>
              테마관찰우선순위
            </button>
          </div>
          {themeViewMode === "trend" ? (
            <div className="theme-return-trend-panel">
              <div className="theme-return-trend-toolbar">
                <input className="input-control" type="date" value={trendEndDate} onChange={(e) => setTrendEndDate(e.target.value)} />
                <select className="select-control" value={trendThemeGroupId} onChange={(e) => setTrendThemeGroupId(e.target.value)}>
                  <option value="all">테마그룹 전체</option>
                  {themeGroups.map((row) => (
                    <option key={row.id} value={row.id}>{row.theme_name}</option>
                  ))}
                </select>
                <input className="input-control" placeholder="테마명 검색" value={trendKeyword} onChange={(e) => setTrendKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void loadThemeReturnTrend(); }} />
                <select className="select-control" value={trendLimit} onChange={(e) => setTrendLimit(e.target.value as "all" | string)}>
                  <option value="10">상위 10개</option>
                  <option value="20">상위 20개</option>
                  <option value="30">상위 30개</option>
                  <option value="all">전체</option>
                </select>
                <button type="button" className="btn btn-secondary market-theme-refresh-button" onClick={() => void loadThemeReturnTrend()} disabled={trendLoading}>{trendLoading ? "조회 중..." : "새로고침"}</button>
                <div className="theme-return-view-toggle" aria-label="테마등락추이 보기 선택">
                  <button type="button" className={trendViewMode === "heatmap" ? "active" : ""} onClick={() => setTrendViewMode("heatmap")}>히트맵</button>
                  <button type="button" className={trendViewMode === "line" ? "active" : ""} onClick={() => setTrendViewMode("line")}>선그래프</button>
                </div>
              </div>
              <div className="theme-return-summary-row">
              <div className="theme-return-summary-grid">
                {trendSummaryCards.map((card) => (
                  <div key={card.label} className="theme-return-summary-card">
                    <span>{card.label}</span>
                    <strong>{card.item?.theme_name ?? "-"}</strong>
                    <em>{card.value == null ? "-" : card.format === "score" ? `${Math.round(card.value)}점` : card.format === "trading" ? `${fmtEok(card.value)}억` : card.format === "persistence" ? `${Math.round(card.value)}%` : fmtPct(card.value)}</em>
                  </div>
                ))}
              </div>
              <div className="theme-strength-sort-row" aria-label="테마등락추이 정렬 기준">
                <div className="theme-strength-sort-control" ref={trendStrengthInfoRef}>
                  <button
                    type="button"
                    className={`theme-strength-sort-button ${trendSortMode === "CURRENT_STRENGTH" ? "active" : ""}`}
                    aria-pressed={trendSortMode === "CURRENT_STRENGTH"}
                    onClick={() => setTrendSortMode("CURRENT_STRENGTH")}
                  >
                    현재강도
                  </button>
                  <button
                    type="button"
                    className="theme-strength-info-button"
                    aria-label="현재 강도 산정 기준"
                    aria-expanded={trendStrengthInfoOpen}
                    onClick={(event) => {
                      event.stopPropagation();
                      setTrendStrengthInfoOpen((prev) => !prev);
                    }}
                  >
                    <Info size={13} />
                  </button>
                  {trendStrengthInfoOpen ? (
                    <div className="theme-strength-popover" role="dialog" aria-label="현재 강도 산정 기준 설명">
                      <strong>현재 강도 산정 기준</strong>
                      <p className="theme-strength-popover__formula">현재 강도 점수 = 최근 10일 가중 수익 강도 45% + 상승 지속성 25% + 최근 모멘텀 20% + 상승 신선도 10% - 소멸 위험 감점 최대 20점</p>
                      <dl>
                        <dt>최근 10일 가중 수익 강도</dt><dd>최근 날짜일수록 높은 가중치를 적용해 최근 흐름을 더 중요하게 평가합니다.</dd>
                        <dt>상승 지속성</dt><dd>최근 10일 중 테마 평균 등락률이 상승한 날짜 비율입니다.</dd>
                        <dt>최근 모멘텀</dt><dd>최근 5일 누적과 직전 5일 누적 등락률의 차이입니다.</dd>
                        <dt>상승 신선도</dt><dd>최근 +3% 이상 상승이 얼마나 최근에 나타났는지 평가합니다.</dd>
                        <dt>소멸 위험 감점</dt><dd>30일 성과는 높지만 최근 수익률·지속성·모멘텀이 약해진 경우 감점합니다.</dd>
                      </dl>
                      <div className="theme-strength-popover__statuses">
                        <span><b>점화</b> 최근 상승이 새롭게 강화</span><span><b>지속</b> 상승과 지속성이 함께 유지</span><span><b>둔화</b> 30일 성과는 양수지만 최근 힘이 약화</span><span><b>소멸</b> 최근 수익·지속성이 모두 약함</span><span><b>중립</b> 명확한 방향이 없는 상태</span>
                      </div>
                      <small>현재 강도는 투자 추천 점수가 아니라, 연결 종목의 최근 가격 흐름이 얼마나 살아 있는지를 비교하기 위한 상대 점수입니다.</small>
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  className={`theme-strength-sort-button ${trendSortMode === "ROLLING_30D_RETURN" ? "active" : ""}`}
                  aria-pressed={trendSortMode === "ROLLING_30D_RETURN"}
                  onClick={() => setTrendSortMode("ROLLING_30D_RETURN")}
                >
                  30일 누적
                </button>
              </div>
              </div>
              {trendViewMode === "heatmap" ? (
                <div className="theme-return-legend">
                  {[`-20% 이하`, `-15%`, `-10%`, `-5%`, `0%`, `+5%`, `+10%`, `+15%`, `+20% 이상`].map((label, index) => {
                    return <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: THEME_RETURN_HEATMAP_COLORS[index] }} />{label}</span>;
                  })}
                </div>
              ) : null}
              {trendViewMode === "heatmap" ? (
              <div className="theme-return-heatmap-wrap">
                <div className="theme-return-heatmap" style={{ gridTemplateColumns: `minmax(200px, 220px) repeat(${Math.max(trendDates.length + 1, 1)}, minmax(0, 1fr))` }}>
                  <div className="theme-return-heatmap__theme-cell theme-return-heatmap__header-cell">테마</div>
                  {trendDates.map((day) => <div key={day} className="theme-return-heatmap__date-cell" title={day}>{formatHeatmapDayLabel(day)}</div>)}
                  <button
                    type="button"
                    className="theme-return-heatmap__date-cell theme-return-heatmap__prediction-header"
                    title={trendData?.prediction?.run ? `${trendData.prediction.mode === "PROBABILITY" ? "D+1 실제 Top20 상대강도 확률" : "D+1 관찰 상대강도 점수(확률 아님)"}\n${trendData.prediction.run.calculation_mode === "REFRESHED_MARKET_DATA" ? "시장지표 보정관찰" : "기존 시장지표 기준"}\n대상일 ${trendData.prediction.run.target_date}\n테마·종목 기준일 ${trendData.prediction.run.data_cutoff_date}\n시장지표 갱신 ${trendData.prediction.run.market_indicator_refreshed_at ?? "-"}\n방법 ${trendData.prediction.method}\n계산 ${trendData.prediction.calculated_at}` : "저장된 D+1 관찰 우선순위가 없습니다."}
                    onClick={() => setPredictionSort((current) => current === "default" ? "desc" : current === "desc" ? "asc" : "default")}
                  >D+1<small>{trendData?.prediction?.run?.target_date?.slice(5).replace("-", "/") ?? ""}</small></button>
                  {trendLoading ? <div className="theme-return-heatmap__empty-row">테마등락추이를 조회 중입니다.</div> : null}
                  {!trendLoading && (!trendData || trendData.themes.length === 0) ? <div className="theme-return-heatmap__empty-row">조회된 테마등락추이 데이터가 없습니다.</div> : null}
                  {!trendLoading && trendThemes.map((theme) => {
                    const dailyMap = new Map(theme.daily_returns.map((item) => [item.return_date, item]));
                    return (
                      <Fragment key={theme.theme_id}>
                        <div className="theme-return-heatmap__theme-cell" title={`${theme.theme_group_name ?? "미지정"} / ${theme.theme_name} / 거래대금 ${fmtEok(theme.total_trading_value_100m)}억`}>
                          <button
                            type="button"
                            className="theme-return-recalculate-trigger"
                            title={`${theme.theme_name} 현재 연결 종목 기준 과거 등락률 재계산`}
                            onClick={() => void openReturnRecalculation(theme)}
                          >
                            <strong>{theme.theme_name}</strong>
                            <RefreshCw size={12} aria-hidden="true" />
                          </button>
                          <span className="theme-strength-row-meta">
                            <b className="theme-strength-score">강도 {theme.theme_strength_score == null ? "-" : Math.round(theme.theme_strength_score)}점</b>
                            <i>·</i>
                            <b className="theme-rolling-return">30일 {fmtPct(theme.rolling_30d_change_rate)}</b>
                            <i>·</i>
                            <em className={`theme-strength-status status-${String(theme.strength_status_code ?? "INSUFFICIENT").toLowerCase()}`}>{theme.strength_status_name ?? "데이터 부족"}</em>
                          </span>
                        </div>
                        {trendDates.map((day) => {
                          const item = dailyMap.get(day);
                          const rate = item?.avg_change_rate ?? null;
                          return (
                            <button
                              key={`${theme.theme_id}-${day}`}
                              type="button"
                              className={`theme-return-heatmap__value-cell ${item ? "" : "theme-return-heatmap__value-cell--empty"}`}
                              style={{ background: getThemeReturnHeatmapColor(rate) }}
                              title={`${theme.theme_name} / ${day} / 등락률 ${fmtPct(rate)} / 거래대금 ${fmtEok(item?.total_trading_value_100m)}억 / 상승 ${item?.rising_stock_count ?? 0} / 하락 ${item?.falling_stock_count ?? 0} / 보합 ${item?.flat_stock_count ?? 0}`}
                              onClick={() => item ? void openThemeReturnDetail(theme, day) : undefined}
                            >
                              <span className={heatmapTextClass(rate)}>{item ? fmtHeatmapCellPct(rate) : "-"}</span>
                            </button>
                          );
                        })}
                        {(() => {
                          const predicted = trendData?.prediction?.values?.[theme.theme_id] ?? null;
                          return <button
                            key={`${theme.theme_id}-prediction`}
                            type="button"
                            className={`theme-return-heatmap__value-cell theme-return-heatmap__prediction-cell ${predicted == null ? "theme-return-heatmap__value-cell--empty" : ""}`}
                            style={{ background: predicted == null ? undefined : getRelativeStrengthColor(predicted), borderStyle: predicted != null && predicted < 40 ? "dashed" : undefined }}
                            title={`${theme.theme_name} / D+1 ${trendData?.prediction?.run?.target_date ?? "-"} / ${trendData?.prediction?.mode === "PROBABILITY" ? `실제 Top20 상대강도 확률 ${predicted == null ? "-" : `${predicted.toFixed(1)}%`}` : `관찰 상대강도 점수 ${predicted == null ? "-" : predicted.toFixed(1)} (확률 아님)`} / 관찰 순위 ${trendData?.prediction?.ranks?.[theme.theme_id] ?? "-"}\n${trendData?.prediction?.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "시장지표 보정관찰" : "기존 시장지표 기준"} / 테마·종목 기준일 ${trendData?.prediction?.run?.data_cutoff_date ?? "-"} / 시장지표 ${trendData?.prediction?.run?.market_indicator_refreshed_at ?? "-"} / 방법 ${trendData?.prediction?.method ?? "-"} / 계산 ${trendData?.prediction?.calculated_at ?? "-"}`}
                            onClick={() => predicted != null ? void openThemeReturnDetail(theme, trendData?.prediction?.run?.data_cutoff_date) : undefined}
                          ><span className={relativeStrengthTextClass(predicted)}>{predicted == null ? "-" : trendData?.prediction?.mode === "PROBABILITY" ? `${Math.round(predicted)}%` : Math.round(predicted)}</span></button>;
                        })()}
                      </Fragment>
                    );
                  })}
                </div>
              </div>
              ) : (
                <ThemeReturnLineChart themes={trendData?.themes ?? []} dates={trendDates} hoveredThemeId={hoveredTrendThemeId} onHoverTheme={setHoveredTrendThemeId} />
              )}
            </div>
          ) : themeViewMode === "flowTrend" ? (
            <MarketThemeFlowTrendPanel
              endDate={trendEndDate}
              onEndDateChange={setTrendEndDate}
              themeGroupId={trendThemeGroupId}
              onThemeGroupChange={setTrendThemeGroupId}
              keyword={trendKeyword}
              onKeywordChange={setTrendKeyword}
              limit={trendLimit}
              onLimitChange={setTrendLimit}
              themeGroups={themeGroups}
              onCellClick={(theme, date, actor, metric, attribution) => void openThemeReturnDetail(theme, date, { actor, metric, attribution })}
            />
          ) : themeViewMode === "prediction" ? (
            <MarketThemeReturnPredictionPanel
              themeGroups={themeGroups}
              initialTargetDate={searchParams.get("target_date")}
              onThemeClick={(themeId) => {
                const theme = manageableThemes.find((row) => row.id === themeId);
                if (theme) void openThemeReturnDetail(theme);
              }}
            />
          ) : (
            <>
          <div className="market-theme-filter-toolbar">
            {themeViewMode === "theme" ? (
              <select className="select-control" value={themeFilterGroupId} onChange={(e) => setThemeFilterGroupId(e.target.value)}>
                <option value="all">테마그룹 전체</option>
                {themeGroups.map((row) => (
                  <option key={row.id} value={row.id}>{row.theme_name}</option>
                ))}
              </select>
            ) : null}
            <select className="select-control" value={themeFilterType} onChange={(e) => setThemeFilterType(e.target.value as "all" | MarketThemeType)}>
              <option value="all">유형 전체</option><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option>
            </select>
            <select className="select-control" value={themeFilterActive} onChange={(e) => setThemeFilterActive(e.target.value as "all" | "1" | "0")}>
              <option value="all">활성 전체</option><option value="1">활성</option><option value="0">비활성</option>
            </select>
            <select className="select-control" value={themeFilterSupply} onChange={(e) => setThemeFilterSupply(e.target.value as "all" | "1" | "0")}>
              <option value="all">수급 전체</option><option value="1">수급 테마</option><option value="0">일반 테마</option>
            </select>
            <input className="input-control market-theme-search-input" placeholder="테마그룹명, 테마명 또는 키워드 검색" value={themeFilterKeyword} onChange={(e) => setThemeFilterKeyword(e.target.value)} />
            <button type="button" className="btn btn-secondary market-theme-action-button" onClick={openCreateThemeModal}>+ 테마 등록</button>
            {themeViewMode === "theme" ? (
              <div className="market-theme-refresh-action-group">
                <span className="market-theme-latest-return-date" title={latestThemeReturnRefresh?.refreshedAt ? `최종 처리: ${latestThemeReturnRefresh.refreshedAt}` : undefined}>
                  최신갱신일 {formatThemeReturnDateLabel(latestThemeReturnRefresh?.returnDate)}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary market-theme-action-button market-theme-refresh-button"
                  onClick={() => void onRefreshThemeReturns()}
                  disabled={refreshingReturns}
                  title="현재 활성 테마에 연결된 고유 종목의 가격과 개인·외국인·기관·프로그램 수급을 갱신하고 테마등락률을 재계산합니다. 같은 날짜의 기존 데이터는 최신 값으로 갱신됩니다."
                >
                  {refreshingReturns ? "가격·수급 갱신 중..." : "테마 등락률&수급 갱신"}
                </button>
              </div>
            ) : null}
          </div>
          <div className="table-shell">
            <table className="data-table compact-table">
              {themeViewMode === "group" ? (
                <thead><tr><th>상태</th><th>테마그룹명</th><th>하위 테마</th><th>수급 테마</th><th>키워드</th><th>연결 종목</th><th>정렬</th><th>작업</th></tr></thead>
              ) : (
                <thead><tr><th>상태</th><th>테마그룹</th><th>테마명</th><th>유형</th><th>수급</th><th>키워드</th><th>연결 종목</th><th><button type="button" className="theme-return-sort-button" onClick={toggleThemeReturnSort}>테마등락률{themeReturnSort === "desc" ? " ↓" : themeReturnSort === "asc" ? " ↑" : ""}</button></th><th>정렬</th><th>작업</th></tr></thead>
              )}
              <tbody>
                {filteredThemes.length === 0 ? (
                  <tr><td colSpan={themeViewMode === "group" ? 8 : 10} className="text-center text-muted">조회 결과가 없습니다.</td></tr>
                ) : null}
                {themeViewMode === "group" ? pagedThemes.map((row) => {
                  const isExpanded = expandedThemeGroupIds.has(row.id);
                  const childThemes = sortedThemes
                    .filter((theme) => theme.parent_theme_id === row.id && theme.theme_level !== "THEME_GROUP")
                    .sort((a, b) => b.is_active - a.is_active);
                  return (
                    <Fragment key={row.id}>
                      <tr className="theme-group-row" onClick={() => toggleThemeGroupExpanded(row.id)}>
                        <td>{row.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                        <td><button type="button" className="theme-expand-button" onClick={(e) => { e.stopPropagation(); toggleThemeGroupExpanded(row.id); }}>{isExpanded ? "접기" : "펼치기"}</button> {row.theme_name}</td>
                        <td><span className="badge badge-slate">{row.child_theme_count ?? childThemes.length}개</span></td>
                        <td><span className="badge badge-blue">{row.supply_child_theme_count ?? childThemes.filter((x) => x.is_supply_theme === 1).length}개</span></td>
                        <td><span className="badge badge-slate">{row.keyword_count ?? row.keywords.length}개</span></td>
                        <td>
                          <button
                            type="button"
                            className="theme-stock-count-link"
                            onClick={(e) => { e.stopPropagation(); openThemeStockMappings(row); }}
                          >
                            {row.linked_stock_count ?? row.stock_count}개
                          </button>
                        </td>
                        <td>{row.sort_order}</td>
                        <td>
                          <div className="theme-group-actions">
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(row); }}>수정</button>
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openCreateThemeInGroupModal(row.id); }}>테마 추가</button>
                            {row.is_active === 1 ? (
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(row.id); }}>비활성화</button>
                            ) : (
                              <>
                                <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
                                <button type="button" className="btn btn-danger btn-table-sm" onClick={(e) => { e.stopPropagation(); openDeleteThemeModal(row); }}>삭제</button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded ? childThemes.map((child) => (
                        <tr key={`${row.id}-${child.id}`} className="theme-child-row" onClick={() => setSelectedThemeId(child.id)}>
                          <td>{child.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                          <td colSpan={2}>{child.theme_name}</td>
                          <td>{child.is_supply_theme === 1 ? <span className="badge badge-blue">수급</span> : "-"}</td>
                          <td><span className="badge badge-slate">{child.keywords.length}개</span></td>
                          <td>
                            <button
                              type="button"
                              className="theme-stock-count-link"
                              onClick={(e) => { e.stopPropagation(); openThemeStockMappings(child); }}
                            >
                              {child.stock_count}개
                            </button>
                          </td>
                          <td>{child.sort_order}</td>
                          <td>
                            <div className="theme-group-actions">
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(child); }}>수정</button>
                              {child.is_active === 1 ? (
                                <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(child.id); }}>비활성화</button>
                              ) : (
                                <>
                                  <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(child); }}>활성화</button>
                                  <button type="button" className="btn btn-danger btn-table-sm" onClick={(e) => { e.stopPropagation(); openDeleteThemeModal(child); }}>삭제</button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )) : null}
                    </Fragment>
                  );
                }) : pagedThemes.map((row) => (
                  <tr key={row.id} className="theme-return-clickable-row" onClick={() => void openThemeReturnDetail(row)}>
                    <td>{row.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                    <td>{row.parent_theme_name ?? <span className="text-muted">미지정</span>}</td>
                    <td>{row.theme_name}</td><td>{themeTypeLabel(row.theme_type)}</td><td>{row.is_supply_theme === 1 ? <span className="badge badge-blue">수급</span> : "-"}</td>
                    <td><span className="badge badge-slate">{row.keywords.length}개</span></td>
                    <td>
                      <button
                        type="button"
                        className="theme-stock-count-link"
                        onClick={(e) => { e.stopPropagation(); openThemeStockMappings(row); }}
                      >
                        {row.stock_count}개
                      </button>
                    </td>
                    <td><span className={`theme-return-badge ${returnToneClass(row.latest_return?.avg_change_rate)}`}>{fmtPct(row.latest_return?.avg_change_rate)}</span></td>
                    <td>{row.sort_order}</td>
                    <td>
                      <div className="theme-group-actions">
                        <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(row); }}>수정</button>
                        {row.is_active === 1 ? (
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(row.id); }}>비활성화</button>
                        ) : (
                          <>
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
                            <button type="button" className="btn btn-danger btn-table-sm" onClick={(e) => { e.stopPropagation(); openDeleteThemeModal(row); }}>삭제</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination-bar">
            <span className="pagination-info">
              {`이번 페이지 ${themePageStart}-${themePageEnd} / 전체 ${filteredThemes.length}건 - 50개씩 표시`}
            </span>
            <div className="pagination-actions">
              <button
                type="button"
                className="btn btn-secondary btn-table-sm"
                disabled={safeThemePage <= 1}
                onClick={() => setThemePage((prev) => Math.max(1, prev - 1))}
              >
                이전
              </button>
              <span className="pagination-info">{`${safeThemePage} / ${themeTotalPages}`}</span>
              <button
                type="button"
                className="btn btn-secondary btn-table-sm"
                disabled={safeThemePage >= themeTotalPages}
                onClick={() => setThemePage((prev) => Math.min(themeTotalPages, prev + 1))}
              >
                다음
              </button>
            </div>
          </div>
            </>
          )}
        </SectionCard>
      ) : null}

      {activeTab === "mapping" ? (
        <div className="space-y-4">
          <SectionCard title="종목 연결">
            <div className="market-theme-mapping-toolbar">
              <select
                className="select-control"
                value={mappingThemeGroupId}
                onChange={(e) => {
                  setMappingThemeGroupId(e.target.value);
                  setMappingAllThemesSelected(false);
                  setMappingThemeSearchText("");
                  setSelectedThemeId(null);
                }}
              >
                <option value="all">테마그룹 전체</option>
                {themeGroups.filter((x) => x.is_active === 1).map((row) => <option key={row.id} value={row.id}>{row.theme_name}</option>)}
              </select>
              <div className="market-theme-mapping-theme-picker" ref={mappingThemePickerRef}>
                <div className="theme-search-combobox">
                  <input
                    className="input-control theme-search-combobox__input"
                    value={mappingThemeInputValue}
                    placeholder="테마명 검색"
                    autoComplete="off"
                    onFocus={() => setMappingThemeDropdownOpen(true)}
                    onChange={(e) => applyMappingThemeSearchValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const firstTheme = mappingThemePickerOptions[0];
                        if (firstTheme) {
                          e.preventDefault();
                          selectMappingTheme(firstTheme);
                        }
                      }
                    }}
                  />
                  {mappingThemeInputValue ? (
                    <button
                      type="button"
                      className="theme-search-combobox__clear"
                      aria-label="테마 입력값 초기화"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={clearMappingThemeInput}
                    >
                      x
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="theme-search-combobox__toggle"
                    aria-label="테마 선택 목록 열기"
                    onClick={() => setMappingThemeDropdownOpen((prev) => !prev)}
                  >
                    ▾
                  </button>
                </div>
                {mappingThemeDropdownOpen ? (
                  <div className="theme-search-combobox__menu" role="listbox">
                    {showMappingThemeAllOption ? (
                      <button
                        type="button"
                        className={`theme-search-combobox__item ${isMappingAllThemesSelected ? "theme-search-combobox__item--active" : ""}`}
                        onClick={selectMappingAllThemes}
                        role="option"
                        aria-selected={isMappingAllThemesSelected}
                      >
                        <span className="theme-search-combobox__item-title">전체</span>
                        <span className="theme-search-combobox__item-meta">테마그룹 전체</span>
                      </button>
                    ) : null}
                    {mappingThemePickerOptions.length === 0 && !showMappingThemeAllOption ? (
                      <div className="theme-search-combobox__empty">검색된 테마가 없습니다.</div>
                    ) : (
                      mappingThemePickerOptions.map((row) => (
                        <button
                          key={row.id}
                          type="button"
                          className={`theme-search-combobox__item ${row.id === selectedThemeId ? "theme-search-combobox__item--active" : ""}`}
                          onClick={() => selectMappingTheme(row)}
                          role="option"
                          aria-selected={row.id === selectedThemeId}
                        >
                          <span className="theme-search-combobox__item-title">{row.theme_name}</span>
                          <span className="theme-search-combobox__item-meta">
                            {row.parent_theme_name || "미지정"} · 연결 {row.linked_stock_count ?? row.stock_count}종목
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                ) : null}
              </div>
              <input className="input-control" placeholder="종목명 또는 종목코드 검색" value={stockSearchKeyword} onChange={(e) => setStockSearchKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void onSearchStocks(); } }} />
              <button type="button" className="btn btn-secondary" onClick={() => void onSearchStocks()} disabled={searching || !selectedThemeId}>{searching ? "검색 중..." : "검색"}</button>
            </div>

            <div className="table-shell max-h-[300px] overflow-auto mt-3">
              <table className="data-table compact-table">
                <thead><tr><th>종목</th><th>시장</th><th>추가</th></tr></thead>
                <tbody>
                  {!selectedThemeId ? <tr><td colSpan={3} className="text-center text-muted">{isMappingAllThemesSelected ? "테마 전체 선택 상태입니다. 아래 연결 종목 목록에서 전체 종목을 확인하세요." : "테마명을 입력하거나 드롭다운에서 테마를 선택해 주세요."}</td></tr> : null}
                  {selectedThemeId && stockSearchResults.length === 0 ? <tr><td colSpan={3} className="text-center text-muted">종목을 검색해 주세요.</td></tr> : null}
                  {stockSearchResults.map((row) => {
                    const alreadyLinked = connectedStockIdSet.has(row.id);
                    return (
                      <tr key={row.id}>
                        <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                        <td>{row.market ?? "-"}</td>
                        <td>{alreadyLinked ? <button type="button" className="btn btn-secondary btn-table-sm" disabled>연결됨</button> : <button type="button" className="btn btn-primary btn-table-sm" onClick={() => void onAddThemeStock(row.id)}>추가</button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard title={`연결 종목 목록${selectedTheme ? ` : ${selectedThemeGroup ? `${selectedThemeGroup.theme_name} ▶ ` : ""}${selectedTheme.theme_name}` : isMappingAllThemesSelected ? " : 테마 전체" : ""} (${activeThemeStocks.length}종목 · 대표 ${primaryCount})`}>
            <div className="theme-linked-stock-sortbar">
              <label><span>정렬</span><select className="select-control" value={themeStockSort} onChange={(event) => { setThemeStockSort(event.target.value as ThemeStockSort); setSupplyCountSort("default"); }}>
                <option value="default">기본순</option><option value="name">종목명</option><option value="memo">종목메모</option>
              </select></label>
            </div>
            <div className="table-shell theme-linked-stock-table-shell">
              <table className="data-table compact-table theme-linked-stock-table">
                <colgroup>
                  <col className="theme-linked-stock-col-stock" />
                  <col className="theme-linked-stock-col-market" />
                  <col className="theme-linked-stock-col-primary" />
                  <col className="theme-linked-stock-col-status" />
                  <col className="theme-linked-stock-col-supply" />
                  <col className="theme-linked-stock-col-chart" />
                  <col className="theme-linked-stock-col-chart" />
                  <col className="theme-linked-stock-col-chart" />
                  <col className="theme-linked-stock-col-action" />
                </colgroup>
                <thead><tr><th>종목</th><th>시장</th><th>대표</th><th>상태</th><th>
                  <div className="theme-supply-count-heading" ref={supplyCountInfoRef}>
                    <button
                      type="button"
                      className="theme-supply-count-sort"
                      onClick={toggleSupplyCountSort}
                      aria-label={`최근 30일 수급횟수 ${supplyCountSort === "desc" ? "내림차순" : supplyCountSort === "asc" ? "오름차순" : "기본순"}`}
                      title="최근 30일 수급횟수 정렬"
                    >
                      <span>수급횟수</span>
                      {supplyCountSort === "desc" ? <ArrowDown size={13} /> : supplyCountSort === "asc" ? <ArrowUp size={13} /> : <ArrowUpDown size={13} />}
                    </button>
                    <button
                      type="button"
                      className="theme-supply-count-info-button"
                      onClick={() => setSupplyCountInfoOpen((prev) => !prev)}
                      aria-label="수급횟수 집계 기준"
                      aria-expanded={supplyCountInfoOpen}
                    >
                      <Info size={13} />
                    </button>
                    {supplyCountInfoOpen ? (
                      <div className="theme-supply-count-popover" role="dialog" aria-label="수급횟수 집계 기준 설명">
                        <strong>수급횟수</strong>
                        <p>최근 30일 수급일수 / 전체 수급일수 순으로 표시합니다.</p>
                        <p>최근 30일 수급일수는 오늘을 포함한 최근 30개 달력일 동안 현재 테마의 일별 수급 종목으로 등록된 고유 일수입니다.</p>
                        <p>전체 수급일수는 전체 기간 동안 현재 테마의 일별 수급 종목으로 등록된 고유 일수입니다.</p>
                        <p>같은 날짜의 중복 등록은 1회로 계산하며, 종목 연결을 해제하더라도 과거 수급 이력은 유지됩니다.</p>
                      </div>
                    ) : null}
                  </div>
                </th><th>일봉</th><th>주봉</th><th>월봉</th><th>작업</th></tr></thead>
                <tbody>
                  {displayedThemeStocks.length === 0 ? (
                    <tr><td colSpan={9} className="text-center text-muted">연결된 종목이 없습니다.</td></tr>
                  ) : null}
                  {displayedThemeStocks.map((row) => {
                    const stockCode = normalizeNaverStockCode(row.stock_code);
                    return (
                      <tr
                        key={row.mapping_id}
                        className={`market-theme-stock-row ${selectedLinkedStock?.mapping_id === row.mapping_id ? "selected" : ""}`}
                        onClick={(e) => {
                          if ((e.target as HTMLElement).closest("button,input,textarea,label")) return;
                          void openLinkedStockDrawer(row);
                        }}
                      >
                        <td><div className="stock-cell theme-linked-stock-name">
                          <strong>{row.stock_name}</strong>
                          <span className="theme-linked-stock-code">{stockCode || row.stock_code}</span>
                          <div className="theme-stock-memo-line">
                            {editingMemoMappingId === row.mapping_id ? <div className="theme-stock-memo-editor">
                              <input autoFocus type="text" maxLength={100} value={memoDrafts[row.mapping_id] ?? row.stock_memo ?? ""} placeholder="세부분야 메모" aria-label={`${row.stock_name} 세부분야 메모 수정`} title={memoDrafts[row.mapping_id] ?? row.stock_memo ?? ""} onFocus={(event) => { const length = event.currentTarget.value.length; event.currentTarget.setSelectionRange(length, length); }} onChange={(event) => setMemoDrafts((previous) => ({ ...previous, [row.mapping_id]: event.target.value }))} onBlur={() => saveThemeStockMemo(row)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); saveThemeStockMemo(row); } else if (event.key === "Escape") { event.preventDefault(); cancelThemeStockMemo(row); } }} />
                            </div> : <button type="button" className={`theme-stock-memo-view${(memoDrafts[row.mapping_id] ?? row.stock_memo ?? "").trim() ? "" : " is-empty"}`} aria-label={`${row.stock_name} 세부분야 메모 ${(memoDrafts[row.mapping_id] ?? row.stock_memo ?? "").trim() ? "수정" : "추가"}`} title={(memoDrafts[row.mapping_id] ?? row.stock_memo ?? "").trim() || `${row.stock_name} 세부분야 메모 추가`} onClick={() => beginThemeStockMemoEdit(row)}>
                              <span>{(memoDrafts[row.mapping_id] ?? row.stock_memo ?? "").trim() || "+ 세부분야 메모"}</span><Pencil className="theme-stock-memo-edit-icon" aria-hidden="true" size={11} />
                            </button>}
                            <small className={`theme-stock-memo-status is-${memoSaveStatuses[row.mapping_id] ?? "idle"}`} aria-live="polite">{memoSaveStatuses[row.mapping_id] === "saving" ? "저장 중" : memoSaveStatuses[row.mapping_id] === "saved" ? "저장됨 ✓" : memoSaveStatuses[row.mapping_id] === "error" ? "저장 실패" : ""}</small>
                          </div>
                        </div></td>
                        <td>{row.market ?? "-"}</td>
                        <td><label className="theme-linked-stock-primary"><input type="checkbox" checked={row.is_primary === 1} disabled={updatingPrimaryMappingId === row.mapping_id} onChange={(e) => void onTogglePrimary(row.mapping_id, e.target.checked)} /><span>{row.is_primary === 1 ? "대표" : "일반"}</span></label></td>
                        <td><span className={`badge ${row.is_active === 1 ? "badge-emerald" : "badge-slate"}`}>{row.is_active === 1 ? "활성" : "비활성"}</span></td>
                        <td>
                          <span className="theme-supply-count-value" title={`최근 30일 ${row.recent_30d_supply_day_count}일 · 전체 ${row.supply_day_count}일 · 최초 ${row.first_supply_date ?? "-"} · 최근 ${row.last_supply_date ?? "-"}`}>
                            <strong>{row.recent_30d_supply_day_count}</strong>
                            <span aria-hidden="true"> / </span>
                            <span>{row.supply_day_count}</span>
                          </span>
                        </td>
                        <td><ThemeLinkedStockChart stockCode={stockCode} stockName={row.stock_name} period="day" label="일봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td><ThemeLinkedStockChart stockCode={stockCode} stockName={row.stock_name} period="week" label="주봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td><ThemeLinkedStockChart stockCode={stockCode} stockName={row.stock_name} period="month" label="월봉" sidcode={chartSidcode} onOpen={setZoomedChart} /></td>
                        <td><button type="button" className="btn btn-secondary btn-table-sm theme-linked-stock-action" onClick={() => void onDeactivateMapping(row.mapping_id)} disabled={!selectedThemeId}>해제</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "candidates" ? (
        <SectionCard title="추천 후보">
          <div className="theme-candidate-toolbar">
            <div className="theme-candidate-lookback-group">
              <span className="theme-candidate-lookback-label">최근 기간(일)</span>
              <input className="input-control theme-candidate-lookback-input" type="number" min={1} max={30} value={lookbackDays} onChange={(e) => setLookbackDays(Number(e.target.value) || 7)} />
            </div>
            <select className="select-control theme-candidate-select" value={candidateSourceFilter} onChange={(e) => setCandidateSourceFilter(e.target.value as "all" | "news" | "disclosure")}>
              <option value="all">출처 전체</option>
              <option value="news">뉴스</option>
              <option value="disclosure">공시</option>
            </select>
            <select className="select-control theme-candidate-select" value={candidateStatusFilter} onChange={(e) => setCandidateStatusFilter(e.target.value as "all" | MarketThemeCandidateStatus)}>
              <option value="all">상태 전체</option>
              <option value="pending">승인 대기</option>
              <option value="approved">승인 완료</option>
              <option value="rejected">거절</option>
              <option value="ignored">보류</option>
            </select>
            <button type="button" className="btn btn-primary" onClick={() => void onGenerateCandidates()} disabled={generatingCandidates}>{generatingCandidates ? "생성 중..." : "뉴스·공시 후보 생성"}</button>
            <button type="button" className="btn btn-secondary" onClick={() => void loadCandidates()}>새로고침</button>
          </div>

          <div className="table-shell max-h-[420px] overflow-auto mt-3">
            <table className="data-table compact-table">
              <thead><tr><th>추천 테마</th><th>추천 종목</th><th>출처</th><th>신뢰도</th><th>매칭 키워드</th><th>근거</th><th>상태</th><th>작업</th></tr></thead>
              <tbody>
                {candidates.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center text-muted">추천 후보가 없습니다.</td>
                  </tr>
                ) : null}
                {candidates.map((row) => (
                  <tr key={row.id}>
                    <td><span className="badge badge-slate">{row.theme_name}</span></td>
                    <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                    <td><span className={`badge ${row.candidate_source === "news" ? "badge-blue" : "badge-slate"}`}>{sourceLabel(row.candidate_source)}</span></td>
                    <td>{row.confidence_score == null ? "-" : <span className="badge badge-neutral">{row.confidence_score}</span>}</td>
                    <td>
                      <div className="candidate-keyword-chips">
                        {row.matched_keywords.length > 0 ? row.matched_keywords.map((keyword) => (
                          <span key={`${row.id}-${keyword}`} className="badge badge-slate">{keyword}</span>
                        )) : <span>-</span>}
                      </div>
                    </td>
                    <td><span className="badge badge-slate">{row.evidence_count}건</span></td>
                    <td>
                      <span className={`badge ${row.status === "approved" ? "badge-emerald" : row.status === "rejected" ? "badge-rose" : row.status === "ignored" ? "badge-neutral" : "badge-amber"}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td><div className="theme-group-actions"><button type="button" className="btn btn-primary btn-table-sm" onClick={() => void onApproveCandidate(row.id)}>승인</button><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void onRejectCandidate(row.id)}>거절</button><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void onIgnoreCandidate(row.id)}>보류</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}
      {zoomedChart ? (
        <div className="theme-linked-stock-chart-modal" onClick={() => setZoomedChart(null)}>
          <div className="theme-linked-stock-chart-modal-panel" onClick={(event) => event.stopPropagation()}>
            <div className="theme-linked-stock-chart-modal-header">
              <h3>{zoomedChart.title || zoomedChart.alt}</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setZoomedChart(null)}>닫기</button>
            </div>
            <img
              src={zoomedChart.url}
              alt={zoomedChart.alt}
              className="theme-linked-stock-chart-modal-image theme-linked-stock-chart-modal-image-clickable"
              onClick={() => setZoomedChart(null)}
            />
          </div>
        </div>
      ) : null}
      {stockDrawerOpen && selectedLinkedStock ? (
        <div className="market-theme-stock-drawer-backdrop" onClick={closeStockDrawer}>
          <aside className="market-theme-stock-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="market-theme-stock-drawer-header">
              <div>
                <h3 className="market-theme-stock-drawer-title">{selectedLinkedStock.stock_name}</h3>
                <p className="market-theme-stock-drawer-subtitle">
                  {selectedLinkedStock.stock_code} · {selectedLinkedStock.market ?? "-"}
                </p>
              </div>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeStockDrawer}>닫기</button>
            </div>

            <div className="market-theme-stock-drawer-body">
              <section className="market-theme-stock-trader-section">
                <h4 className="market-theme-stock-section-title">매매동향</h4>
                {selectedLinkedStockCode ? (
                  <div className="theme-stock-trader-chart-grid">
                    <ThemeLinkedStockTraderChart stockCode={selectedLinkedStockCode} stockName={selectedLinkedStock.stock_name} type="foreign" title="외국인매매동향 3개월" onOpen={setZoomedChart} />
                    <ThemeLinkedStockTraderChart stockCode={selectedLinkedStockCode} stockName={selectedLinkedStock.stock_name} type="institution" title="기관매매동향 3개월" onOpen={setZoomedChart} />
                  </div>
                ) : (
                  <p className="selected-empty-message">종목코드가 없어 매매동향 이미지를 표시할 수 없습니다.</p>
                )}
              </section>

              <MarketThemePriceFlowPanel stockId={selectedLinkedStock.stock_id} themeId={selectedLinkedStock.theme_id} />

              <section
                className="market-theme-stock-supply-section"
                style={{ "--theme-context-color": stockSupplySummary?.current_theme.color ?? "#dc2626" } as CSSProperties}
              >
                <div className="market-theme-stock-section-heading">
                  <div>
                    <h4 className="market-theme-stock-section-title">수급 이력</h4>
                    <p>{stockSupplySummary ? `${stockSupplySummary.current_theme.theme_name} · ${stockSupplySummary.stock_name}` : "테마별 수급 기록"}</p>
                  </div>
                  {stockSupplyError ? (
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void loadStockSupplySummary(selectedLinkedStock)}>
                      <RefreshCw size={13} /> 재시도
                    </button>
                  ) : null}
                </div>
                {stockSupplyLoading ? (
                  <div className="market-theme-stock-supply-skeleton" aria-label="수급 이력 불러오는 중">
                    {Array.from({ length: 5 }, (_, index) => <span key={index} />)}
                  </div>
                ) : null}
                {stockSupplyError ? <p className="market-theme-stock-section-error">{stockSupplyError}</p> : null}
                {!stockSupplyLoading && !stockSupplyError && stockSupplySummary ? (
                  <>
                    <div className="theme-context-supply-head">
                      <div>
                        <strong>{stockSupplySummary.stock_name}에 속한 테마</strong>
                        <span>테마별 고유 수급일 수</span>
                      </div>
                      <span
                        className="theme-context-supply-info"
                        title="현재 테마 수급횟수는 현재 조회 중인 테마로 등록된 고유 수급일 수입니다. 전체테마 수급횟수는 테마 중복을 제거한 종목 전체 고유 수급일 수입니다. 종목 메모는 모두 표시하며 현재 테마 수급일만 강조합니다."
                      >
                        <Info size={13} /> 집계 기준
                      </span>
                    </div>
                    <div className="theme-context-chip-list">
                      {stockSupplySummary.linked_theme_supply_summaries.map((theme) => (
                        <span
                          key={theme.theme_id}
                          className={`theme-context-chip${theme.is_current_theme ? " is-current" : ""}`}
                          title={theme.supply_dates.length > 0 ? theme.supply_dates.join(", ") : "수급 이력 없음"}
                        >
                          {theme.theme_name} <strong>{theme.supply_count}회</strong>
                          {theme.is_current_theme ? <small>현재 테마</small> : null}
                        </span>
                      ))}
                    </div>
                    <div className="market-theme-stock-supply-grid">
                      <div className="stock-supply-summary-card is-theme-context">
                        <span>최근30일 수급횟수</span>
                        <strong>{stockSupplySummary.recent_30d_theme_supply_count}회</strong>
                      </div>
                      <div className="stock-supply-summary-card is-theme-context">
                        <span>해당테마 수급횟수</span>
                        <strong>{stockSupplySummary.current_theme_supply_count}회</strong>
                      </div>
                      <div className="stock-supply-summary-card is-overall">
                        <span>전체테마 수급횟수</span>
                        <strong>{stockSupplySummary.overall_stock_supply_count}회</strong>
                      </div>
                      <div className="stock-supply-summary-card is-theme-context">
                        <span>최근수급일</span>
                        <strong>{stockSupplySummary.latest_current_theme_supply_date ?? "-"}</strong>
                      </div>
                      <div className="stock-supply-summary-card is-theme-context">
                        <span>최초수급일</span>
                        <strong>{stockSupplySummary.first_current_theme_supply_date ?? "-"}</strong>
                      </div>
                    </div>
                    <p className="theme-context-period">최근 30일 기준 {stockSupplySummary.period_start_date} ~ {stockSupplySummary.period_end_date} · 날짜는 현재 테마 기준</p>
                    {stockSupplySummary.current_theme_supply_dates.length > 0 ? (
                      <div className="market-theme-stock-recent-supply">
                        <span>최근 수급일 {stockSupplySummary.current_theme_supply_dates.length}건</span>
                        <div>
                          {(showAllSupplyDates ? stockSupplySummary.current_theme_supply_dates : stockSupplySummary.current_theme_supply_dates.slice(0, 10)).map((date) => (
                            <em key={date} className="current-theme-supply-date-chip">{date}</em>
                          ))}
                          {stockSupplySummary.current_theme_supply_dates.length > 10 ? (
                            <button type="button" className="theme-context-date-toggle" onClick={() => setShowAllSupplyDates((value) => !value)}>
                              {showAllSupplyDates ? "접기" : `전체 보기 (${stockSupplySummary.current_theme_supply_dates.length})`}
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <p className="selected-empty-message">현재 테마로 등록된 수급 이력이 없습니다.</p>
                    )}
                  </>
                ) : null}
              </section>

              <section
                className="market-theme-stock-memo-section"
                style={{ "--theme-context-color": stockSupplySummary?.current_theme.color ?? "#dc2626" } as CSSProperties}
              >
                <div className="market-theme-stock-memo-heading">
                  <h4 className="market-theme-stock-section-title">종목 메모</h4>
                  <span>전체 테마 메모 · 현재 테마 수급일 강조</span>
                </div>
                {stockMemoLoading ? <p className="selected-empty-message">메모를 불러오는 중입니다.</p> : null}
                {stockMemoError && !stockSupplyError ? <p className="text-sm text-red-600">{stockMemoError}</p> : null}
                {!stockMemoLoading && !stockMemoError && stockMemos.length === 0 ? (
                  <p className="selected-empty-message">등록된 종목 메모가 없습니다.</p>
                ) : null}
                {!stockMemoLoading && !stockMemoError && stockMemos.length > 0 ? (
                  <div className="market-theme-stock-memo-list">
                    {stockMemos.map((memo, index) => (
                      <div
                        key={`${memo.detected_date}-${memo.memo}-${index}`}
                        className={`market-theme-stock-memo-row${memo.is_current_theme_supply_date ? " is-current-theme-date" : ""}`}
                      >
                        <div className="market-theme-stock-memo-meta">
                          <span className="market-theme-stock-memo-date">{memo.detected_date}</span>
                          {memo.is_current_theme_supply_date ? <small>현재 테마 수급일</small> : null}
                        </div>
                        <span className="market-theme-stock-memo-text">{memo.memo}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            </div>
          </aside>
        </div>
      ) : null}
      <MarketThemeDetailDrawer
        open={Boolean(themeDetailRequest)}
        themeId={themeDetailRequest?.themeId ?? null}
        dataDate={themeDetailRequest?.dataDate}
        flowContext={themeDetailRequest?.flowContext}
        onClose={closeReturnDrawer}
      />

      {returnRecalculationTheme ? (
        <div className="modal-backdrop" onClick={closeReturnRecalculation}>
          <section
            className="modal-card theme-return-recalculation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="theme-return-recalculation-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="trade-journal-detail-header">
              <div>
                <h3 id="theme-return-recalculation-title">테마등락률 재계산</h3>
                <p>{returnRecalculationTheme.themeName}</p>
              </div>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeReturnRecalculation} disabled={returnRecalculationRunning}>닫기</button>
            </div>

            {returnRecalculationLoading ? <p className="theme-return-recalculation-loading">재계산 범위를 확인하는 중입니다.</p> : null}
            {!returnRecalculationLoading && returnRecalculationPreview ? (
              <>
                <p className="theme-return-recalculation-description">
                  현재 연결된 종목 구성을 기준으로 과거 테마등락률을 다시 계산합니다.
                  <strong> 과거 당시의 종목 구성은 복원하지 않습니다.</strong>
                </p>
                <p className="theme-return-recalculation-source">
                  외부 API를 호출하지 않고 DrCT DB에 기존 수집된 종목별 일간 가격·등락률 데이터만 사용합니다.
                </p>
                <dl className="theme-return-recalculation-summary">
                  <div><dt>현재 연결 종목</dt><dd>{returnRecalculationPreview.connected_stock_count}종목</dd></div>
                  <div><dt>재계산 범위</dt><dd>{returnRecalculationPreview.period_from ?? "-"} ~ {returnRecalculationPreview.period_to ?? "-"}</dd></div>
                </dl>
                {!returnRecalculationResult ? (
                  <div className="theme-return-recalculation-warning">
                    <p>기존에 저장된 테마등락률은 현재 종목 구성 기준으로 갱신됩니다.</p>
                    <p>종목 가격 데이터가 없는 날짜에는 해당 종목을 평균 계산에서 제외합니다.</p>
                    <strong>계속 진행하시겠습니까?</strong>
                  </div>
                ) : (
                  <div className="theme-return-recalculation-result" role="status">
                    <strong>테마등락률 재계산 완료</strong>
                    <dl>
                      <div><dt>계산 날짜</dt><dd>{returnRecalculationResult.processed_date_count}일</dd></div>
                      <div><dt>갱신</dt><dd>{returnRecalculationResult.updated_count}건</dd></div>
                      <div><dt>신규 생성</dt><dd>{returnRecalculationResult.inserted_count}건</dd></div>
                      <div><dt>결측 날짜</dt><dd>{returnRecalculationResult.skipped_date_count}건</dd></div>
                    </dl>
                  </div>
                )}
              </>
            ) : null}
            {returnRecalculationError ? <p className="form-error">{returnRecalculationError}</p> : null}

            <div className="watchlist-theme-modal-actions">
              <button type="button" className="btn btn-secondary" onClick={closeReturnRecalculation} disabled={returnRecalculationRunning}>
                {returnRecalculationResult ? "닫기" : "취소"}
              </button>
              {!returnRecalculationResult ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void runReturnRecalculation()}
                  disabled={
                    returnRecalculationLoading
                    || returnRecalculationRunning
                    || !returnRecalculationPreview?.connected_stock_count
                    || !returnRecalculationPreview.period_from
                    || !returnRecalculationPreview.period_to
                  }
                >
                  {returnRecalculationRunning ? "테마등락률 재계산 중..." : "재계산 진행"}
                </button>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {deleteThemeTarget ? (() => {
        const childThemes = themes.filter((theme) => theme.parent_theme_id === deleteThemeTarget.id);
        const activeChildThemes = childThemes.filter((theme) => theme.is_active === 1);
        const isGroup = deleteThemeTarget.theme_level === "THEME_GROUP";
        return (
          <div className="modal-backdrop" role="presentation">
            <section
              className="modal-card market-theme-delete-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="market-theme-delete-title"
            >
              <header className="market-theme-delete-modal__header">
                <div>
                  <span>{isGroup ? "테마그룹 영구 삭제" : "테마 영구 삭제"}</span>
                  <h3 id="market-theme-delete-title">{deleteThemeTarget.theme_name}</h3>
                </div>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setDeleteThemeTarget(null)} disabled={deletingTheme}>닫기</button>
              </header>
              <div className="market-theme-delete-modal__warning">
                <strong>삭제한 데이터는 복구할 수 없습니다.</strong>
                <p>
                  {isGroup
                    ? `이 그룹과 하위 테마 ${childThemes.length}개를 함께 물리 삭제합니다.`
                    : "이 테마를 물리 삭제합니다."}
                </p>
              </div>
              <ul className="market-theme-delete-modal__scope">
                <li>종목 연결과 후보 데이터</li>
                <li>일별 등락률·실시간 Snapshot</li>
                <li>예측·관찰·수급 순위 데이터</li>
                <li>캘린더·브리핑·시장 이벤트의 테마 연결</li>
              </ul>
              {isGroup && childThemes.length > 0 ? (
                <div className="market-theme-delete-modal__children">
                  <strong>함께 삭제되는 하위 테마</strong>
                  <p>{childThemes.map((theme) => theme.theme_name).join(", ")}</p>
                </div>
              ) : null}
              {activeChildThemes.length > 0 ? (
                <p className="form-error" role="alert">
                  활성 하위 테마가 있습니다. 먼저 {activeChildThemes.map((theme) => theme.theme_name).join(", ")}을(를) 비활성화해 주세요.
                </p>
              ) : null}
              {deleteThemeError ? <p className="form-error" role="alert">{deleteThemeError}</p> : null}
              <footer className="watchlist-theme-modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setDeleteThemeTarget(null)} disabled={deletingTheme}>취소</button>
                <button type="button" className="btn btn-danger" onClick={() => void onDeleteTheme()} disabled={deletingTheme || activeChildThemes.length > 0}>
                  {deletingTheme ? "삭제 중..." : "완전히 삭제"}
                </button>
              </footer>
            </section>
          </div>
        );
      })() : null}

      {themeModalOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card watchlist-theme-modal market-theme-edit-modal">
            <div className="trade-journal-detail-header">
              <h3>{formThemeId ? `${themeLevelLabel(themeLevel)} 수정` : `${themeLevelLabel(themeLevel)} 등록`}</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setThemeModalOpen(false)}>닫기</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="space-y-1">
                <span>구분</span>
                <select className="select-control" value={themeLevel} onChange={(e) => {
                  const nextLevel = e.target.value as MarketThemeLevel;
                  setThemeLevel(nextLevel);
                  if (nextLevel === "THEME_GROUP") setParentThemeId("");
                }}>
                  <option value="THEME_GROUP">테마그룹</option>
                  <option value="THEME">테마</option>
                </select>
              </label>
              {themeLevel === "THEME" ? (
                <label className="space-y-1">
                  <span>상위 테마그룹</span>
                  <select className="select-control" value={parentThemeId} onChange={(e) => setParentThemeId(e.target.value)}>
                    <option value="">미지정</option>
                    {themeGroups.filter((row) => row.id !== formThemeId).map((row) => (
                      <option key={row.id} value={row.id}>{row.theme_name}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="space-y-1"><span>{themeLevel === "THEME_GROUP" ? "테마그룹명" : "테마명"}</span><input className="input-control" value={themeName} onChange={(e) => setThemeName(e.target.value)} /></label>
              <label className="space-y-1"><span>유형</span><select className="select-control" value={themeType} onChange={(e) => setThemeType(e.target.value as MarketThemeType)}><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option></select></label>
              <label className="space-y-1"><span>정렬 순서</span><input className="input-control" type="number" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value) || 0)} /></label>
              <label className="space-y-1"><span>활성 여부</span><select className="select-control" value={isActive} onChange={(e) => setIsActive(Number(e.target.value))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
              <label className="space-y-1 md:col-span-2"><span>설명</span><input className="input-control" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
              {themeLevel === "THEME" ? (
                <label className="space-y-1"><span>수급테마 여부</span><select className="select-control" value={isSupplyTheme} onChange={(e) => setIsSupplyTheme(Number(e.target.value))}><option value={0}>일반 테마</option><option value={1}>수급 테마</option></select></label>
              ) : null}
              <label className="space-y-1 md:col-span-2"><span>키워드(줄바꿈/쉼표 구분)</span><textarea className="input-control min-h-[120px]" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} /></label>
            </div>
            <div className="watchlist-theme-modal-actions">
              <button type="button" className="btn btn-primary" onClick={() => void onSubmitTheme()}>저장</button>
              <button type="button" className="btn btn-secondary" onClick={resetForm}>초기화</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default MarketThemesPage;
