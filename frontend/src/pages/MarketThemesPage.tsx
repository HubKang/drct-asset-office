import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Info, RefreshCw } from "lucide-react";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import {
  buildNaverTraderChartUrl,
  buildNaverStockCandleChartUrl,
  createNaverChartSidcode,
  normalizeNaverStockCode,
  type NaverTraderChartType,
  type NaverStockCandlePeriod,
} from "@/utils/naverChart";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeLatestReturnDetail,
  MarketThemeMonthlyReturnResponse,
  MarketThemeMonthlyReturnThemeItem,
  MarketThemeCandidateStatus,
  MarketThemeLevel,
  MarketThemeStock,
  MarketThemeStockMemo,
  MarketThemeStockSupplySummary,
  MarketThemeType,
} from "@/types/marketTheme";
import type { Stock } from "@/types/stock";

type ActiveTab = "themes" | "mapping" | "candidates";
type ThemeViewMode = "group" | "theme" | "trend";
type ThemeReturnSort = "default" | "desc" | "asc";
type SupplyCountSort = "default" | "desc" | "asc";
type ThemeReturnTrendViewMode = "heatmap" | "line";
const THEME_PAGE_SIZE = 20;
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

function ThemeLinkedStockChart({
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
    return <div className="theme-linked-stock-chart-fallback">차트 없음</div>;
  }

  const url = buildNaverStockCandleChartUrl(stockCode, period, sidcode);
  const alt = `${stockName || stockCode} ${label} 차트`;

  return (
    <button
      type="button"
      className="theme-linked-stock-chart-button"
      onClick={(event) => {
        event.stopPropagation();
        onOpen({ url, alt });
      }}
    >
      <img
        src={url}
        alt={alt}
        className="theme-linked-stock-chart"
        loading="lazy"
        onError={() => setHasError(true)}
      />
    </button>
  );
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
const getThemeReturnHeatmapColor = (rate: number | null | undefined): string => {
  if (rate == null || Number.isNaN(Number(rate))) return "#F8FAFC";
  const value = Number(rate);
  if (value <= -10) return "#93C5FD";
  if (value <= -7) return "#BFDBFE";
  if (value <= -5) return "#DBEAFE";
  if (value <= -3) return "#EFF6FF";
  if (value < 3) return "#F3F4F6";
  if (value < 5) return "#FEF2F2";
  if (value < 7) return "#FEE2E2";
  if (value < 10) return "#FECACA";
  return "#FCA5A5";
};

const heatmapTextClass = (rate: number | null | undefined) => {
  if (rate == null || Number.isNaN(Number(rate))) return "theme-return-heatmap__value-text--empty";
  if (Number(rate) <= -7) return "theme-return-heatmap__value-text--negative-strong";
  if (Number(rate) < 0) return "theme-return-heatmap__value-text--negative";
  if (Number(rate) >= 7) return "theme-return-heatmap__value-text--positive-strong";
  if (Number(rate) > 0) return "theme-return-heatmap__value-text--positive";
  return "theme-return-heatmap__value-text--empty";
};
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
  const [activeTab, setActiveTab] = useState<ActiveTab>("themes");

  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [themeStocks, setThemeStocks] = useState<MarketThemeStock[]>([]);
  const [candidates, setCandidates] = useState<MarketThemeCandidate[]>([]);

  const [themeFilterType, setThemeFilterType] = useState<"all" | MarketThemeType>("all");
  const [themeFilterActive, setThemeFilterActive] = useState<"all" | "1" | "0">("all");
  const [themeFilterSupply, setThemeFilterSupply] = useState<"all" | "1" | "0">("all");
  const [themeFilterKeyword, setThemeFilterKeyword] = useState("");
  const [themeViewMode, setThemeViewMode] = useState<ThemeViewMode>("theme");
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
  const [themeReturnSort, setThemeReturnSort] = useState<ThemeReturnSort>("default");
  const [trendEndDate, setTrendEndDate] = useState(getDateInputValue());
  const [trendThemeGroupId, setTrendThemeGroupId] = useState<"all" | string>("all");
  const [trendKeyword, setTrendKeyword] = useState("");
  const [trendLimit, setTrendLimit] = useState<"all" | string>("20");
  const [trendViewMode, setTrendViewMode] = useState<ThemeReturnTrendViewMode>("heatmap");
  const [hoveredTrendThemeId, setHoveredTrendThemeId] = useState<number | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendData, setTrendData] = useState<MarketThemeMonthlyReturnResponse | null>(null);
  const [returnDrawerOpen, setReturnDrawerOpen] = useState(false);
  const [returnDetailLoading, setReturnDetailLoading] = useState(false);
  const [returnDetailError, setReturnDetailError] = useState("");
  const [selectedReturnDetail, setSelectedReturnDetail] = useState<MarketThemeLatestReturnDetail | null>(null);
  const [stockDrawerOpen, setStockDrawerOpen] = useState(false);
  const [selectedLinkedStock, setSelectedLinkedStock] = useState<MarketThemeStock | null>(null);
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string; title?: string } | null>(null);
  const [stockMemos, setStockMemos] = useState<MarketThemeStockMemo[]>([]);
  const [stockMemoLoading, setStockMemoLoading] = useState(false);
  const [stockMemoError, setStockMemoError] = useState("");
  const [stockSupplySummary, setStockSupplySummary] = useState<MarketThemeStockSupplySummary | null>(null);
  const [stockSupplyLoading, setStockSupplyLoading] = useState(false);
  const [stockSupplyError, setStockSupplyError] = useState("");
  const [supplyCountSort, setSupplyCountSort] = useState<SupplyCountSort>("default");
  const [supplyCountInfoOpen, setSupplyCountInfoOpen] = useState(false);
  const [updatingPrimaryMappingId, setUpdatingPrimaryMappingId] = useState<number | null>(null);
  const mappingThemePickerRef = useRef<HTMLDivElement | null>(null);
  const supplyCountInfoRef = useRef<HTMLDivElement | null>(null);

  const [themeModalOpen, setThemeModalOpen] = useState(false);
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
    () =>
      [...themes].sort((a, b) => {
        if (a.is_active !== b.is_active) return b.is_active - a.is_active;
        const groupCompare = themeGroupSortName(a).localeCompare(themeGroupSortName(b), "ko-KR");
        if (groupCompare !== 0) return groupCompare;
        if (a.is_supply_theme !== b.is_supply_theme) return b.is_supply_theme - a.is_supply_theme;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      }),
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
    if (themeViewMode !== "theme" || themeReturnSort === "default") return rows;
    return [...rows].sort((a, b) => {
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
    () => (trendData ? getDateRange(trendData.display_start_date, trendData.display_end_date) : []),
    [trendData],
  );
  const trendSummaryCards = useMemo(() => {
    const summary = trendData?.summary;
    return [
      { label: "30일 상승 1위", item: summary?.top_rising_theme, value: summary?.top_rising_theme?.period_compound_return ?? summary?.top_rising_theme?.monthly_compound_return },
      { label: "30일 하락 1위", item: summary?.top_falling_theme, value: summary?.top_falling_theme?.period_compound_return ?? summary?.top_falling_theme?.monthly_compound_return },
      { label: "거래대금 1위", item: summary?.top_trading_value_theme, value: summary?.top_trading_value_theme?.total_trading_value_100m, suffix: "억" },
      { label: "상승 지속 1위", item: summary?.top_continuous_rising_theme ?? summary?.rising_day_theme, value: summary?.top_continuous_rising_theme?.continuous_rising_days ?? summary?.rising_day_theme?.continuous_rising_days, suffix: "일" },
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
    if (supplyCountSort === "default") return activeThemeStocks;
    return [...activeThemeStocks].sort((a, b) => {
      const difference = a.supply_day_count - b.supply_day_count;
      if (difference !== 0) return supplyCountSort === "desc" ? -difference : difference;
      return a.stock_name.localeCompare(b.stock_name, "ko-KR");
    });
  }, [activeThemeStocks, supplyCountSort]);
  const isMappingAllThemesSelected = mappingAllThemesSelected && !selectedThemeId && mappingThemeGroupId === "all";
  const chartSidcode = useMemo(() => createNaverChartSidcode(), [selectedThemeId, activeThemeStocks.length]);
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
  const themeManagementTitle = themeViewMode === "group" ? "테마그룹 관리" : themeViewMode === "trend" ? "테마등락추이" : "테마별 관리";

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

  const loadThemeStocks = async (themeId: number | null) => {
    try {
      if (themeId) {
        const rows = await repositories.marketThemes.listThemeStocks(themeId);
        setThemeStocks(rows);
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
      const results = await Promise.all(targetThemes.map((theme) => repositories.marketThemes.listThemeStocks(theme.id)));
      const uniqueByStock = new Map<number, MarketThemeStock>();
      results.flat().forEach((row) => {
        if (row.is_active !== 1) return;
        const current = uniqueByStock.get(row.stock_id);
        if (!current || (row.is_primary === 1 && current.is_primary !== 1)) {
          uniqueByStock.set(row.stock_id, row);
        }
      });
      const rows = Array.from(uniqueByStock.values()).sort((a, b) => a.stock_name.localeCompare(b.stock_name, "ko-KR"));
      setThemeStocks(rows);
    } catch (e) {
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
    setMessage("\ud14c\ub9c8\ub4f1\ub77d\ub960 \uac31\uc2e0 \uc911...");
    try {
      const res = await repositories.marketThemes.refreshReturns({ scope: "all_active" });
      await Promise.all([loadThemes(), loadThemeReturnTrend()]);
      const totalSeconds = typeof res.total_ms === "number" ? (res.total_ms / 1000).toFixed(1) : null;
      const fallbackMessage = `\ud14c\ub9c8\ub4f1\ub77d\ub960 \uac31\uc2e0 \uc644\ub8cc: ${res.theme_count}\uac1c \ud14c\ub9c8, \uace0\uc720 ${res.unique_stock_count ?? res.stock_count}\uac1c \uc885\ubaa9${totalSeconds ? `, ${totalSeconds}\ucd08` : ""}`;
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
      setError(toErrorMessage(e, "\ud14c\ub9c8\ub4f1\ub77d\ub960 \uac31\uc2e0\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4. Kiwoom REST \ud1a0\ud070/\uc5f0\uacb0 \uc0c1\ud0dc\ub97c \ud655\uc778\ud574 \uc8fc\uc138\uc694."));
    } finally {
      setRefreshingReturns(false);
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
      });
      setTrendData(rows);
    } catch (e) {
      setError(toErrorMessage(e, "테마등락추이 데이터를 불러오지 못했습니다."));
      setTrendData(null);
    } finally {
      setTrendLoading(false);
    }
  };
  const openThemeReturnDetail = async (theme: MarketTheme | MarketThemeMonthlyReturnThemeItem, returnDate?: string) => {
    const themeId = "id" in theme ? theme.id : theme.theme_id;
    setSelectedThemeId(themeId);
    setReturnDrawerOpen(true);
    setReturnDetailLoading(true);
    setReturnDetailError("");
    setSelectedReturnDetail(null);
    try {
      const detail = returnDate ? await repositories.marketThemes.getDailyReturn(themeId, returnDate) : await repositories.marketThemes.getLatestReturn(themeId);
      setSelectedReturnDetail(detail);
    } catch (e) {
      setReturnDetailError(toErrorMessage(e, "테마 상세 정보를 불러오지 못했습니다."));
    } finally {
      setReturnDetailLoading(false);
    }
  };

  const closeReturnDrawer = () => {
    setReturnDrawerOpen(false);
    setReturnDetailLoading(false);
    setReturnDetailError("");
    setSelectedReturnDetail(null);
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
    try {
      const summary = await repositories.marketThemes.getThemeStockSupplySummary(row.theme_id, row.stock_id);
      setStockSupplySummary(summary);
    } catch (e) {
      setStockSupplyError(toErrorMessage(e, "수급 이력을 불러오지 못했습니다."));
    } finally {
      setStockSupplyLoading(false);
    }
  };

  const openLinkedStockDrawer = async (row: MarketThemeStock) => {
    setSelectedLinkedStock(row);
    setStockDrawerOpen(true);
    setStockMemoLoading(true);
    setStockMemoError("");
    setStockMemos([]);
    void loadStockSupplySummary(row);
    try {
      const res = await repositories.marketThemes.listStockMemos(row.stock_code);
      setStockMemos(res.items ?? []);
    } catch (e) {
      setStockMemoError(toErrorMessage(e, "종목 메모를 불러오지 못했습니다."));
    } finally {
      setStockMemoLoading(false);
    }
  };

  const toggleThemeReturnSort = () => {
    setThemeReturnSort((prev) => (prev === "default" ? "desc" : prev === "desc" ? "asc" : "default"));
  };

  const toggleSupplyCountSort = () => {
    setSupplyCountSort((prev) => (prev === "default" ? "desc" : prev === "desc" ? "asc" : "default"));
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
    void Promise.all([loadThemes(), loadCandidates()]);
  }, []);

  useEffect(() => {
    void loadThemeStocks(selectedThemeId);
  }, [selectedThemeId, mappingThemeGroupId, mappingSelectableThemes, mappingAllThemesSelected]);

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
    if (activeTab === "themes" && themeViewMode === "trend") {
      void loadThemeReturnTrend();
    }
  }, [activeTab, themeViewMode, trendEndDate, trendThemeGroupId, trendLimit]);
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
    void loadCandidates();
  }, [candidateSourceFilter, candidateStatusFilter]);

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
      await loadThemes();
      setMessage("테마가 활성화되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 활성화 중 오류가 발생했습니다."));
    }
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
      await Promise.all([loadThemeStocks(selectedThemeId), loadThemes()]);
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
      if (selectedLinkedStock?.mapping_id === mappingId) closeStockDrawer();
      await Promise.all([loadThemeStocks(selectedThemeId), loadThemes()]);
      setMessage("테마 연결이 해제되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "연결 해제 중 오류가 발생했습니다."));
    }
  };

  const onTogglePrimary = async (mappingId: number, checked: boolean) => {
    setUpdatingPrimaryMappingId(mappingId);
    try {
      await repositories.marketThemes.updateThemeStock(mappingId, { is_primary: checked });
      await loadThemeStocks(selectedThemeId);
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
    await Promise.all([loadCandidates(), loadThemes(), loadThemeStocks(selectedThemeId)]);
  };

  const onRejectCandidate = async (candidateId: number) => {
    await repositories.marketThemes.rejectCandidate(candidateId, { review_memo: "관련성 낮음" });
    await loadCandidates();
  };

  const onIgnoreCandidate = async (candidateId: number) => {
    await repositories.marketThemes.ignoreCandidate(candidateId, { review_memo: "추가 확인" });
    await loadCandidates();
  };

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

      <SectionCard title="" className="market-theme-tabs-card">
        <div className="gpt-domain-tabs market-theme-primary-tabs">
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "themes" ? "active" : ""}`} onClick={() => { setActiveTab("themes"); setThemeViewMode("theme"); }}>테마 관리</button>
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "mapping" ? "active" : ""}`} onClick={() => setActiveTab("mapping")}>종목 연결</button>
          <button type="button" className={`gpt-domain-tab market-theme-primary-tab ${activeTab === "candidates" ? "active" : ""}`} onClick={() => setActiveTab("candidates")}>추천 후보</button>
        </div>
      </SectionCard>

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
              <div className="theme-return-summary-grid">
                {trendSummaryCards.map((card) => (
                  <div key={card.label} className="theme-return-summary-card">
                    <span>{card.label}</span>
                    <strong>{card.item?.theme_name ?? "-"}</strong>
                    <em>{card.value == null ? "-" : card.suffix === "억" ? `${fmtEok(card.value)}억` : fmtPct(card.value)}</em>
                  </div>
                ))}
              </div>
              {trendViewMode === "heatmap" ? (
                <div className="theme-return-legend">
                  {[`-10% 이하`, `-7%`, `-5%`, `-3%`, `0%`, `+3%`, `+5%`, `+7%`, `+10% 이상`].map((label, index) => {
                    const colors = ["#93C5FD", "#BFDBFE", "#DBEAFE", "#EFF6FF", "#F3F4F6", "#FEF2F2", "#FEE2E2", "#FECACA", "#FCA5A5"];
                    return <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: colors[index] }} />{label}</span>;
                  })}
                </div>
              ) : null}
              {trendViewMode === "heatmap" ? (
              <div className="theme-return-heatmap-wrap">
                <div className="theme-return-heatmap" style={{ gridTemplateColumns: `minmax(130px, 150px) repeat(${Math.max(trendDates.length, 1)}, minmax(0, 1fr))` }}>
                  <div className="theme-return-heatmap__theme-cell theme-return-heatmap__header-cell">테마</div>
                  {trendDates.map((day) => <div key={day} className="theme-return-heatmap__date-cell" title={day}>{formatHeatmapDayLabel(day)}</div>)}
                  {trendLoading ? <div className="theme-return-heatmap__empty-row">테마등락추이를 조회 중입니다.</div> : null}
                  {!trendLoading && (!trendData || trendData.themes.length === 0) ? <div className="theme-return-heatmap__empty-row">조회된 테마등락추이 데이터가 없습니다.</div> : null}
                  {!trendLoading && trendData?.themes.map((theme) => {
                    const dailyMap = new Map(theme.daily_returns.map((item) => [item.return_date, item]));
                    return (
                      <Fragment key={theme.theme_id}>
                        <div className="theme-return-heatmap__theme-cell" title={`${theme.theme_group_name ?? "미지정"} / ${theme.theme_name}`}>
                          <strong>{theme.theme_name}</strong>
                          <span>{fmtPct(theme.period_compound_return ?? theme.monthly_compound_return)} · {fmtEok(theme.total_trading_value_100m)}억</span>
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
                      </Fragment>
                    );
                  })}
                </div>
              </div>
              ) : (
                <ThemeReturnLineChart themes={trendData?.themes ?? []} dates={trendDates} hoveredThemeId={hoveredTrendThemeId} onHoverTheme={setHoveredTrendThemeId} />
              )}
            </div>
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
                <button type="button" className="btn btn-secondary market-theme-action-button market-theme-refresh-button" onClick={() => void onRefreshThemeReturns()} disabled={refreshingReturns}>
                  {refreshingReturns ? "갱신 중..." : "테마등락률 갱신"}
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
                  const childThemes = sortedThemes.filter((theme) => theme.parent_theme_id === row.id && theme.theme_level !== "THEME_GROUP");
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
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
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
                                <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(child); }}>활성화</button>
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
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
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
              {`이번 페이지 ${themePageStart}-${themePageEnd} / 전체 ${filteredThemes.length}건 - 20개씩 표시`}
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

          <SectionCard title={`연결 종목 목록${selectedTheme ? ` - ${selectedThemeGroup ? `${selectedThemeGroup.theme_name} / ` : ""}${selectedTheme.theme_name}` : isMappingAllThemesSelected ? " - 테마 전체" : ""} (${activeThemeStocks.length}종목 · 대표 ${primaryCount})`}>
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
                      aria-label={`수급횟수 정렬${supplyCountSort === "desc" ? ": 내림차순" : supplyCountSort === "asc" ? ": 오름차순" : ": 기본순"}`}
                      title="수급횟수 정렬"
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
                      <div className="theme-supply-count-popover" role="dialog">
                        선택한 테마와 종목에 연결된 수급 기록을 날짜 기준으로 집계합니다. 같은 날 기록이 여러 건이어도 1회로 계산합니다.
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
                          if ((e.target as HTMLElement).closest("button,input,label")) return;
                          void openLinkedStockDrawer(row);
                        }}
                      >
                        <td><div className="stock-cell theme-linked-stock-name"><strong>{row.stock_name}</strong><span>{stockCode || row.stock_code}</span></div></td>
                        <td>{row.market ?? "-"}</td>
                        <td><label className="theme-linked-stock-primary"><input type="checkbox" checked={row.is_primary === 1} disabled={updatingPrimaryMappingId === row.mapping_id} onChange={(e) => void onTogglePrimary(row.mapping_id, e.target.checked)} /><span>{row.is_primary === 1 ? "대표" : "일반"}</span></label></td>
                        <td><span className={`badge ${row.is_active === 1 ? "badge-emerald" : "badge-slate"}`}>{row.is_active === 1 ? "활성" : "비활성"}</span></td>
                        <td><span className="theme-supply-count-value" title={`최초 ${row.first_supply_date ?? "-"} · 최근 ${row.last_supply_date ?? "-"}`}>{row.supply_day_count}회</span></td>
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
              className="theme-linked-stock-chart-modal-image"
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

              <section className="market-theme-stock-supply-section">
                <div className="market-theme-stock-section-heading">
                  <div>
                    <h4 className="market-theme-stock-section-title">수급 이력</h4>
                    <p>{stockSupplySummary ? `${stockSupplySummary.theme_name} · ${stockSupplySummary.stock_name}` : "테마별 수급 기록"}</p>
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
                    <div className="market-theme-stock-supply-grid">
                      <div><span>테마 수급일</span><strong>{stockSupplySummary.supply_day_count}일</strong></div>
                      <div><span>최근 30일</span><strong>{stockSupplySummary.recent_30d_supply_day_count}일</strong></div>
                      <div><span>최근 수급일</span><strong>{stockSupplySummary.last_supply_date ?? "-"}</strong></div>
                      <div><span>최초 수급일</span><strong>{stockSupplySummary.first_supply_date ?? "-"}</strong></div>
                      <div><span>전체 테마 고유일</span><strong>{stockSupplySummary.all_theme_supply_day_count}일</strong></div>
                    </div>
                    {stockSupplySummary.recent_supply_dates.length > 0 ? (
                      <div className="market-theme-stock-recent-supply">
                        <span>최근 수급일 5건</span>
                        <div>{stockSupplySummary.recent_supply_dates.map((date) => <em key={date}>{date}</em>)}</div>
                      </div>
                    ) : (
                      <p className="selected-empty-message">등록된 수급 이력이 없습니다.</p>
                    )}
                  </>
                ) : null}
              </section>

              <section className="market-theme-stock-memo-section">
                <h4 className="market-theme-stock-section-title">종목 메모</h4>
                {stockMemoLoading ? <p className="selected-empty-message">메모를 불러오는 중입니다.</p> : null}
                {stockMemoError ? <p className="text-sm text-red-600">{stockMemoError}</p> : null}
                {!stockMemoLoading && !stockMemoError && stockMemos.length === 0 ? (
                  <p className="selected-empty-message">등록된 종목 메모가 없습니다.</p>
                ) : null}
                {!stockMemoLoading && !stockMemoError && stockMemos.length > 0 ? (
                  <div className="market-theme-stock-memo-list">
                    {stockMemos.map((memo, index) => (
                      <div key={`${memo.memo_date}-${index}`} className="market-theme-stock-memo-row">
                        <span className="market-theme-stock-memo-date">{memo.memo_date}</span>
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
      {returnDrawerOpen ? (
        <div className="theme-return-drawer-backdrop" onClick={closeReturnDrawer}>
          <aside className="theme-return-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="theme-return-drawer-header">
              <div>
                <h3>테마 상세</h3>
                <p>{selectedReturnDetail?.theme_name ?? "테마 정보를 불러오는 중입니다."}</p>
              </div>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeReturnDrawer}>닫기</button>
            </div>
            <div className="theme-return-drawer-body">
              {returnDetailLoading ? <p className="text-sm text-muted">테마 상세를 조회 중입니다.</p> : null}
              {returnDetailError ? <p className="text-sm text-red-600">{returnDetailError}</p> : null}
              {!returnDetailLoading && !returnDetailError && selectedReturnDetail ? (
                <div className="theme-return-detail-stack">
                  <div className="theme-return-detail-title-block">
                    <strong>{selectedReturnDetail.theme_name}</strong>
                    <span>{selectedReturnDetail.theme_group_name || "미지정 테마그룹"}</span>
                  </div>
                  {selectedReturnDetail.return_date ? (
                    <>
                      <div className="theme-return-kpi-grid">
                        <div><span>테마등락률</span><strong className={returnToneClass(selectedReturnDetail.avg_change_rate)}>{fmtPct(selectedReturnDetail.avg_change_rate)}</strong></div>
                        <div><span>연결 종목</span><strong>{selectedReturnDetail.stock_count}개</strong></div>
                        <div><span>거래대금 합계(억)</span><strong>{fmtEok(selectedReturnDetail.total_trading_value_100m)}</strong></div>
                        <div><span>상승</span><strong className="theme-return-positive">{selectedReturnDetail.rising_stock_count}개</strong></div>
                        <div><span>하락</span><strong className="theme-return-negative">{selectedReturnDetail.falling_stock_count}개</strong></div>
                        <div><span>보합</span><strong className="theme-return-neutral">{selectedReturnDetail.flat_stock_count}개</strong></div>
                      </div>
                      <div className="theme-return-meta">
                        <span>기준일: {selectedReturnDetail.return_date}</span>
                        <span>최종 갱신: {selectedReturnDetail.snapshot_at || "-"}</span>
                        {selectedReturnDetail.failed_stock_count > 0 ? <span>조회 실패: {selectedReturnDetail.failed_stock_count}개</span> : null}
                      </div>
                      {selectedReturnDetail.stocks.length > 0 ? (
                        <div className="table-shell overflow-auto">
                          <table className="data-table compact-table theme-return-stock-table">
                            <thead><tr><th>종목명</th><th className="text-right">거래대금(억)</th><th className="text-right">등락률(%)</th></tr></thead>
                            <tbody>
                              {selectedReturnDetail.stocks.map((stock) => (
                                <tr key={`${stock.stock_id}-${stock.stock_code}`}>
                                  <td>
                                    <div className="stock-cell">
                                      <strong>{stock.stock_name || stock.stock_code || "-"}</strong>
                                      {stock.stock_code ? <span>{stock.stock_code}</span> : null}
                                      {stock.data_status !== "success" ? <small className="theme-return-fail-text">조회 실패</small> : null}
                                    </div>
                                  </td>
                                  <td className="text-right">{fmtEok(stock.trading_value_100m)}</td>
                                  <td className={`text-right ${returnToneClass(stock.change_rate)}`}>{fmtPct(stock.change_rate)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="selected-empty-message">이 테마에 연결된 종목이 없습니다.</p>
                      )}
                    </>
                  ) : selectedReturnDetail.stock_count > 0 ? (
                    <p className="selected-empty-message">아직 갱신된 테마등락률 데이터가 없습니다. 상단의 테마등락률 갱신 버튼을 눌러 데이터를 생성하세요.</p>
                  ) : (
                    <p className="selected-empty-message">이 테마에 연결된 종목이 없습니다.</p>
                  )}
                </div>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}

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
