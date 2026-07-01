import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { MarketIndexCompareResponse, MarketIndexDailyPriceItem, MarketIndexItem, MarketIndexProviderCode, MarketIndexProviderMapping } from "@/types/marketIndex";
import type { ExternalProviderStatus, ExternalProviderStatusListResponse, MarketIndicator, MarketIndicatorValue } from "@/types/marketIndicator";

const PERIOD_OPTIONS = [
  { label: "1M", days: 31 },
  { label: "3M", days: 93 },
  { label: "6M", days: 186 },
  { label: "1Y", days: 365 },
  { label: "ALL", days: null },
] as const;

const CATEGORY_OPTIONS = ["전체", "주식시장", "업종", "금현물", "금리/환율", "보류/제외"] as const;

const MARKET_INDEX_CHART_HEIGHT = 520;
const MARKET_INDEX_PRICE_AREA_HEIGHT = 350;
const MARKET_INDEX_VOLUME_AREA_HEIGHT = 90;
const MARKET_INDEX_CHART_TOP_PADDING = 40;
const MARKET_INDEX_PRICE_VOLUME_GAP = 24;
const MARKET_INDEX_CHART_BOTTOM_PADDING = MARKET_INDEX_CHART_HEIGHT - MARKET_INDEX_CHART_TOP_PADDING - MARKET_INDEX_PRICE_AREA_HEIGHT - MARKET_INDEX_PRICE_VOLUME_GAP - MARKET_INDEX_VOLUME_AREA_HEIGHT;
const MARKET_INDEX_DEFAULT_VISIBLE_CANDLES = 80;
const MARKET_INDEX_VISIBLE_CANDLE_COUNT = {
  "1M": 22,
  "3M": 66,
  "6M": 132,
  "1Y": 250,
  ALL: 250,
} as const;

const ADMIN_DRAWER_TABS = [
  { key: "mapping", label: "매핑 상태" },
  { key: "kiwoom", label: "키움 업종코드" },
  { key: "deferred", label: "보류/제외" },
  { key: "provider", label: "대체 provider" },
  { key: "external", label: "\uC678\uBD80 API \uC0C1\uD0DC" },
] as const;

type AdminDrawerTab = (typeof ADMIN_DRAWER_TABS)[number]["key"];

type PeriodLabel = (typeof PERIOD_OPTIONS)[number]["label"];
type CategoryFilter = (typeof CATEGORY_OPTIONS)[number];

type MetricSource = "MARKET_INDEX" | "MARKET_INDICATOR";
type MetricKey = string;

type SelectorMetricItem = {
  key: MetricKey;
  source: MetricSource;
  code: string;
  name: string;
  category: string;
  status: string;
  latestValue?: number | null;
  latestDate?: string | null;
  changeValue?: number | null;
  changePct?: number | null;
  return5?: number | null;
  return20?: number | null;
  unitLabel?: string | null;
};

const TEXT = {
  pageTitle: "시장 지표 관리",
  pageDescription: "코스피, 코스닥, 업종지수, 금 현물 등 주요 시장지표를 수집하고 시장 흐름을 비교합니다.",
  collectSelected: "선택 지표 갱신",
  collectAll: "전체 지표 갱신",
  collectHint: "활성화된 시장지표를 순차 수집합니다. 일부 지표는 provider 지원 여부에 따라 수집대기 또는 오류 상태가 될 수 있습니다.",
  latestClose: "최근 종가",
  latestDate: "최근 거래일",
  tradingValue: "거래대금",
  status: "상태",
  oneDay5: "5일",
  oneDay20: "20일",
  compareTitle: "시장 지표 비교",
  compareDescription: "선택 지표를 첫 거래일 100 기준으로 정규화해 비교합니다.",
  allPeriod: "전체",
  notCollected: "미수집",
  emptyCompare: "비교할 시장 지표 데이터가 없습니다.\n코스피와 코스닥 데이터를 먼저 수집해 주세요.",
  industryGuide: "업종지수는 한국 시장의 공식 업종 흐름을 확인하기 위한 참고 지표입니다. DrCT 테마와 1:1로 일치하지 않을 수 있으므로, 테마 수급과 함께 비교해 해석합니다.",
};

const DEFAULT_INDEX_NAMES: Record<string, string> = {
  KOSPI: "코스피",
  KOSDAQ: "코스닥",
  KOSPI200: "코스피200",
  KOSDAQ150: "코스닥150",
  KOSPI_ELECTRONICS: "코스피 전기전자",
  KOSDAQ_SEMICONDUCTOR: "코스닥 반도체",
  GOLD_KRX: "KRX 금 현물",
  NASDAQ: "나스닥",
  DOW: "다우지수",
  SP500: "S&P500",
  USDKRW: "원/달러",
  GOLD: "금",
  WTI: "WTI",
};

const STATUS_LABELS: Record<string, string> = {
  NOT_COLLECTED: "미수집",
  COLLECTING: "수집중",
  LATEST: "최신",
  PARTIAL: "일부누락",
  ERROR: "오류",
  WAITING: "수집대기",
  SUCCESS: "최신",
  FAILED: "오류",
  READY: "미수집",
  NO_OFFICIAL_INDEX: "공식지수 없음",
  CUSTOM_INDEX_REQUIRED: "자체지수 필요",
  EXCLUDED: "제외",
};

type CompareGroupKey = string;

type CompareGroupConfig = {
  key: CompareGroupKey;
  label: string;
  indexCodes: readonly string[];
  indicatorCodes?: readonly string[];
  prefix?: string;
};

const GENERAL_INDICATOR_CODES = ["USD_KRW", "JPY_KRW", "CNY_KRW", "BASE_RATE", "CALL_RATE", "KTB_3Y", "KTB_10Y"] as const;
const FX_INDICATOR_CODES = ["USD_KRW", "JPY_KRW", "CNY_KRW"] as const;
const RATE_INDICATOR_CODES = ["BASE_RATE", "CALL_RATE", "KTB_3Y", "KTB_10Y"] as const;

const GENERAL_INDICATOR_NAMES: Record<string, string> = {
  USD_KRW: "\uB2EC\uB7EC/\uC6D0 \uD658\uC728",
  JPY_KRW: "\uC5D4/\uC6D0 \uD658\uC728",
  CNY_KRW: "\uC704\uC548/\uC6D0 \uD658\uC728",
  BASE_RATE: "\uAE30\uC900\uAE08\uB9AC",
  CALL_RATE: "\uCF5C\uAE08\uB9AC",
  KTB_3Y: "\uAD6D\uACE0\uCC44 3\uB144",
  KTB_10Y: "\uAD6D\uACE0\uCC44 10\uB144",
};

const makeMetricKey = (source: MetricSource, code: string): MetricKey => source + ":" + code;
const parseMetricKey = (key: MetricKey): { source: MetricSource; code: string } => {
  const [source, ...rest] = key.split(":");
  const code = rest.join(":") || key;
  return source === "MARKET_INDICATOR" ? { source: "MARKET_INDICATOR", code } : { source: "MARKET_INDEX", code };
};

const getIndicatorName = (indicator?: Pick<MarketIndicator, "indicator_code" | "indicator_name"> | null) => {
  const code = (indicator?.indicator_code ?? "").toUpperCase();
  const rawName = (indicator?.indicator_name ?? "").trim();
  if (rawName && !rawName.includes("?")) return rawName;
  return GENERAL_INDICATOR_NAMES[code] ?? code;
};

const COMPARE_GROUPS: CompareGroupConfig[] = [
  {
    key: "DOMESTIC",
    label: "국내 대표/보조",
    indexCodes: ["KOSPI", "KOSDAQ", "KOSPI200", "KOSDAQ150", "KRX100"],
  },
  {
    key: "KOSPI_SECTOR",
    label: "코스피 업종",
    prefix: "KOSPI_",
    indexCodes: [
      "KOSPI_ELECTRONICS",
      "KOSPI_PHARMA",
      "KOSPI_CHEMICAL",
      "KOSPI_MACHINERY",
      "KOSPI_TRANSPORT_EQUIPMENT",
      "KOSPI_STEEL_METAL",
      "KOSPI_FINANCE",
      "KOSPI_CONSTRUCTION",
      "KOSPI_TRANSPORT_WAREHOUSE",
      "KOSPI_SERVICE",
    ],
  },
  {
    key: "KOSDAQ_SECTOR",
    label: "코스닥 업종",
    prefix: "KOSDAQ_",
    indexCodes: [
      "KOSDAQ_IT_SW_SVC",
      "KOSDAQ_PHARMA",
      "KOSDAQ_GENERAL_ELECTRONICS",
      "KOSDAQ_MACHINE_EQUIPMENT",
      "KOSDAQ_CHEMICAL",
      "KOSDAQ_MEDICAL_PRECISION",
    ],
  },
  {
    key: "FX_RATE",
    label: "\uAE08\uB9AC/\uD658\uC728",
    indexCodes: [],
    indicatorCodes: GENERAL_INDICATOR_CODES,
  },
  {
    key: "SAFE_ASSET",
    label: "안전자산/기타",
    indexCodes: ["GOLD_KRX"],
  },
];

const FIRST_SECTOR_CANDIDATES = [
  "KOSPI_ELECTRONICS",
  "KOSPI_PHARMA",
  "KOSPI_CHEMICAL",
  "KOSPI_TRANSPORT_EQUIPMENT",
  "KOSPI_FINANCE",
  "KOSDAQ_SEMICONDUCTOR",
  "KOSDAQ_PHARMA",
  "KOSDAQ_IT_HW",
  "KOSDAQ_IT_SW_SVC",
  "KOSDAQ_GENERAL_ELECTRONICS",
] as const;

const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
};

const getIndexName = (index?: Pick<MarketIndexItem, "index_code" | "index_name"> | null) => {
  const code = (index?.index_code ?? "").toUpperCase();
  const rawName = (index?.index_name ?? "").trim();
  if (rawName && !rawName.includes("?")) return rawName;
  return (DEFAULT_INDEX_NAMES[code] ?? code) || "시장 지표";
};

const getStatusValue = (raw?: string | null, hasPrice = false) => {
  const status = (raw ?? "").toUpperCase();
  if (status === "SUCCESS") return "LATEST";
  if (status === "FAILED") return "ERROR";
  if (status === "NO_OFFICIAL_INDEX" || status === "CUSTOM_INDEX_REQUIRED" || status === "EXCLUDED") return status;
  if (status === "READY" || !status) return hasPrice ? "LATEST" : "NOT_COLLECTED";
  return STATUS_LABELS[status] ? status : hasPrice ? "LATEST" : "NOT_COLLECTED";
};

const getStatusLabel = (raw?: string | null, hasPrice = false) => STATUS_LABELS[getStatusValue(raw, hasPrice)] ?? TEXT.notCollected;
const getStatusClass = (status: string) => status.toLowerCase().replace(/_/g, "-");
const isDeferredStatus = (status: string) => ["NO_OFFICIAL_INDEX", "CUSTOM_INDEX_REQUIRED", "EXCLUDED"].includes(status);

const formatNumber = (value?: number | null, fraction = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: fraction, minimumFractionDigits: fraction }).format(value);
};

const formatPercent = (value?: number | null) => (value === null || value === undefined ? "-" : `${value > 0 ? "+" : ""}${formatNumber(value, 2)}%`);

const formatTradingValue = (value?: number | null) => {
  if (!value) return "-";
  return `${formatNumber(value / 100000000, 1)}억`;
};

function getRange(period: PeriodLabel) {
  const option = PERIOD_OPTIONS.find((item) => item.label === period) ?? PERIOD_OPTIONS[3];
  return {
    startDate: option.days === null ? undefined : daysAgo(option.days),
    endDate: today(),
  };
}

function minMax(values: Array<number | null | undefined>) {
  const nums = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!nums.length) return { min: 0, max: 1 };
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const pad = Math.max((max - min) * 0.08, 1);
  return { min: min - pad, max: max + pad };
}

function CandleChart({ rows, indexName, period, statusValue, errorMessage }: { rows: MarketIndexDailyPriceItem[]; indexName: string; period: PeriodLabel; statusValue?: string; errorMessage?: string | null }) {
  const visibleRows = rows.filter((row) => row.close_price !== null && row.close_price !== undefined && Number.isFinite(row.close_price));
  const chartScrollRef = useRef<HTMLDivElement | null>(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [scrollMetrics, setScrollMetrics] = useState({ scrollLeft: 0, scrollWidth: 0, clientWidth: 0 });
  const priceHeight = MARKET_INDEX_PRICE_AREA_HEIGHT;
  const volumeHeight = MARKET_INDEX_VOLUME_AREA_HEIGHT;
  const height = MARKET_INDEX_CHART_HEIGHT;
  const chartX = 44;
  const chartRight = 28;
  const minChartWidth = 720;
  const measuredWidth = Math.max(viewportWidth, minChartWidth);
  const configuredVisibleCount = MARKET_INDEX_VISIBLE_CANDLE_COUNT[period] ?? Math.max(visibleRows.length, MARKET_INDEX_DEFAULT_VISIBLE_CANDLES);
  const targetVisibleCount = Math.max(1, configuredVisibleCount);
  const candleSlot = (measuredWidth - chartX - chartRight) / targetVisibleCount;
  const width = Math.max(minChartWidth, chartX + chartRight + Math.max(visibleRows.length, targetVisibleCount) * candleSlot);
  const chartWidth = width - chartX - chartRight;
  const gap = visibleRows.length > 1 ? chartWidth / visibleRows.length : chartWidth;
  const candleWidth = Math.max(4, Math.min(14, gap * 0.58));
  const priceRange = minMax(visibleRows.flatMap((row) => [row.open_price, row.high_price, row.low_price, row.close_price, row.ma5, row.ma20, row.ma60, row.ma120]));
  const volumeMax = Math.max(...visibleRows.map((row) => row.volume ?? 0), 1);
  const priceTop = MARKET_INDEX_CHART_TOP_PADDING;
  const priceBottom = priceTop + priceHeight;
  const volumeTop = priceBottom + MARKET_INDEX_PRICE_VOLUME_GAP;
  const volumeBaseline = volumeTop + volumeHeight;
  const y = (value?: number | null) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return priceBottom;
    const domain = priceRange.max - priceRange.min || 1;
    return priceTop + ((priceRange.max - value) / domain) * priceHeight;
  };
  const x = (idx: number) => chartX + idx * gap + gap / 2;
  const linePath = (key: "ma5" | "ma20" | "ma60" | "ma120") => {
    const points = visibleRows
      .map((row, idx) => {
        const value = row[key];
        return value === null || value === undefined ? null : { idx, value };
      })
      .filter((point): point is { idx: number; value: number } => Boolean(point));
    return points.map((point, pathIdx) => `${pathIdx === 0 ? "M" : "L"}${x(point.idx).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  };
  const latestDate = visibleRows[visibleRows.length - 1]?.price_date;
  const updateScrollMetrics = useCallback(() => {
    const scrollElement = chartScrollRef.current;
    if (!scrollElement) return;
    setViewportWidth(scrollElement.clientWidth || 0);
    setScrollMetrics({
      scrollLeft: scrollElement.scrollLeft,
      scrollWidth: scrollElement.scrollWidth,
      clientWidth: scrollElement.clientWidth,
    });
  }, []);
  const maxScrollLeft = Math.max(scrollMetrics.scrollWidth - scrollMetrics.clientWidth, 0);
  const thumbWidthPercent = scrollMetrics.scrollWidth > 0 ? Math.max(7, Math.min(100, (scrollMetrics.clientWidth / scrollMetrics.scrollWidth) * 100)) : 100;
  const thumbLeftPercent = maxScrollLeft > 0 ? (scrollMetrics.scrollLeft / maxScrollLeft) * (100 - thumbWidthPercent) : 0;

  useEffect(() => {
    const scrollElement = chartScrollRef.current;
    if (!scrollElement) return;
    updateScrollMetrics();
    scrollElement.addEventListener("scroll", updateScrollMetrics, { passive: true });
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateScrollMetrics);
      return () => {
        scrollElement.removeEventListener("scroll", updateScrollMetrics);
        window.removeEventListener("resize", updateScrollMetrics);
      };
    }
    const observer = new ResizeObserver(updateScrollMetrics);
    observer.observe(scrollElement);
    return () => {
      scrollElement.removeEventListener("scroll", updateScrollMetrics);
      observer.disconnect();
    };
  }, [updateScrollMetrics]);

  useEffect(() => {
    const scrollElement = chartScrollRef.current;
    if (!scrollElement) return;
    scrollElement.scrollLeft = scrollElement.scrollWidth;
    window.requestAnimationFrame(updateScrollMetrics);
  }, [indexName, latestDate, visibleRows.length, width, updateScrollMetrics]);

  const handleScrollbarPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    const scrollElement = chartScrollRef.current;
    if (!scrollElement) return;
    const trackElement = event.currentTarget;
    const trackRect = trackElement.getBoundingClientRect();
    const maxScroll = Math.max(scrollElement.scrollWidth - scrollElement.clientWidth, 0);
    const thumbWidth = (thumbWidthPercent / 100) * trackRect.width;
    const maxThumbLeft = Math.max(trackRect.width - thumbWidth, 1);
    const moveTo = (clientX: number) => {
      const nextThumbLeft = Math.min(Math.max(clientX - trackRect.left - thumbWidth / 2, 0), maxThumbLeft);
      scrollElement.scrollLeft = maxScroll > 0 ? (nextThumbLeft / maxThumbLeft) * maxScroll : 0;
      updateScrollMetrics();
    };
    moveTo(event.clientX);
    const handlePointerMove = (moveEvent: PointerEvent) => moveTo(moveEvent.clientX);
    const handlePointerUp = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp, { once: true });
  };

  if (!visibleRows.length) {
    const emptyText =
      statusValue === "WAITING"
        ? { title: "이 지표는 아직 provider mapping 검증 또는 활성화가 필요합니다.", body: errorMessage || "키움 provider mapping 확인 후 수집할 수 있습니다." }
        : statusValue === "NO_OFFICIAL_INDEX"
          ? { title: "공식 업종지수에 대응되는 항목이 없습니다.", body: errorMessage || "공식 provider 매핑 없이 보류된 지표입니다." }
          : statusValue === "CUSTOM_INDEX_REQUIRED"
            ? { title: "이 지표는 DrCT 자체 테마지수로 계산이 필요한 항목입니다.", body: errorMessage || "공식 업종지수 수집 대상에서 제외되었습니다." }
            : statusValue === "ERROR"
              ? { title: "최근 수집 중 오류가 발생했습니다.", body: errorMessage || "카드의 오류 메시지를 확인해 주세요." }
              : { title: `수집된 ${indexName} 일봉 데이터가 없습니다.`, body: "상단의 선택 지표 갱신 또는 전체 지표 갱신을 실행해 주세요." };
    return (
      <div className="market-index-chart-viewport">
        <div className="market-index-chart-empty fixed">
          <strong>{emptyText.title}</strong>
          <span>{emptyText.body}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="market-index-chart-viewport">
      <div className="market-index-chart-scroll" ref={chartScrollRef}>
        <svg className="market-index-candle-svg" style={{ width: `${width}px` }} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`${indexName} 일봉 차트`}>
          {[0, 1, 2, 3, 4].map((grid) => {
            const yy = priceTop + (grid * priceHeight) / 4;
            return <line key={grid} x1={chartX} x2={width - chartRight} y1={yy} y2={yy} className="market-index-grid" />;
          })}
          <line x1={chartX} x2={width - chartRight} y1={volumeBaseline} y2={volumeBaseline} className="market-index-volume-baseline" />
          {visibleRows.map((row, idx) => {
            const cx = x(idx);
            const openY = y(row.open_price ?? row.close_price);
            const closeY = y(row.close_price);
            const highY = y(row.high_price ?? row.close_price);
            const lowY = y(row.low_price ?? row.close_price);
            const up = (row.close_price ?? 0) >= (row.open_price ?? row.close_price ?? 0);
            const bodyY = Math.min(openY, closeY);
            const bodyH = Math.max(Math.abs(closeY - openY), 2);
            const volumeH = ((row.volume ?? 0) / volumeMax) * (volumeHeight - 12);
            return (
              <g key={`${row.index_code}-${row.price_date}`}>
                <line x1={cx} x2={cx} y1={highY} y2={lowY} className={up ? "market-index-candle-up" : "market-index-candle-down"} />
                <rect x={cx - candleWidth / 2} y={bodyY} width={candleWidth} height={bodyH} rx="0" className={up ? "market-index-candle-up-fill" : "market-index-candle-down-fill"} />
                <rect x={cx - candleWidth / 2} y={volumeTop + (volumeHeight - volumeH)} width={candleWidth} height={volumeH} rx="0" className={up ? "market-index-volume-up" : "market-index-volume-down"} />
              </g>
            );
          })}
          <path d={linePath("ma5")} className="market-index-ma ma5" />
          <path d={linePath("ma20")} className="market-index-ma ma20" />
          <path d={linePath("ma60")} className="market-index-ma ma60" />
          <path d={linePath("ma120")} className="market-index-ma ma120" />
          <text x={chartX} y={height - Math.max(10, MARKET_INDEX_CHART_BOTTOM_PADDING / 2)} className="market-index-axis-label">{visibleRows[0]?.price_date}</text>
          <text x={width - 24} y={height - Math.max(10, MARKET_INDEX_CHART_BOTTOM_PADDING / 2)} textAnchor="end" className="market-index-axis-label">{visibleRows[visibleRows.length - 1]?.price_date}</text>
        </svg>
      </div>
      <div className="market-index-custom-scrollbar" role="scrollbar" aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={Math.round(maxScrollLeft)} aria-valuenow={Math.round(scrollMetrics.scrollLeft)} onPointerDown={handleScrollbarPointerDown}>
        <span className="market-index-custom-scrollbar-thumb" style={{ width: `${thumbWidthPercent}%`, left: `${thumbLeftPercent}%` }} />
      </div>
    </div>
  );
}

function MarketIndicatorLineChart({ rows, indicatorName, unitLabel }: { rows: MarketIndicatorValue[]; indicatorName: string; unitLabel?: string | null }) {
  const width = 1440;
  const height = 520;
  const chartX = 64;
  const chartRight = 36;
  const chartTop = 36;
  const chartBottom = 48;
  const values = rows.map((row) => row.value ?? row.close_value).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const range = minMax(values);
  const dateValues = rows.map((row) => new Date(row.value_date).getTime()).filter((value) => Number.isFinite(value));
  const minDate = Math.min(...dateValues);
  const maxDate = Math.max(...dateValues);
  const x = (date: string) => {
    const time = new Date(date).getTime();
    const domain = maxDate - minDate || 1;
    return chartX + ((time - minDate) / domain) * (width - chartX - chartRight);
  };
  const y = (value?: number | null) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return height - chartBottom;
    return chartTop + ((range.max - value) / (range.max - range.min || 1)) * (height - chartTop - chartBottom);
  };
  const path = rows
    .map((row) => {
      const value = row.value ?? row.close_value;
      return value === null || value === undefined ? null : x(row.value_date).toFixed(1) + "," + y(value).toFixed(1);
    })
    .filter(Boolean)
    .map((point, idx) => (idx === 0 ? "M" : "L") + point)
    .join(" ");

  if (!rows.length || !values.length) {
    return <div className="market-index-chart-empty fixed"><strong>No data</strong><span>General indicator values are not available.</span></div>;
  }

  return (
    <div className="market-index-chart-viewport">
      <svg className="market-index-compare-svg market-indicator-line-svg" viewBox={"0 0 " + width + " " + height} preserveAspectRatio="none" role="img" aria-label={indicatorName}>
        {[0, 1, 2, 3].map((grid) => {
          const yy = chartTop + (grid * (height - chartTop - chartBottom)) / 3;
          const tickValue = range.max - (grid * (range.max - range.min)) / 3;
          return <g key={grid}><line x1={chartX} x2={width - chartRight} y1={yy} y2={yy} className="market-index-grid" /><text x={chartX - 10} y={yy + 4} textAnchor="end" className="market-index-axis-label">{formatNumber(tickValue, 2)}</text></g>;
        })}
        <path d={path} fill="none" stroke="#2563eb" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
        <text x={chartX} y={height - 14} className="market-index-axis-label">{rows[0]?.value_date}</text>
        <text x={width - chartRight} y={height - 14} textAnchor="end" className="market-index-axis-label">{rows[rows.length - 1]?.value_date}</text>
      </svg>
      <div className="market-index-compare-legend"><span><i style={{ backgroundColor: "#2563eb" }} />{unitLabel || indicatorName}</span></div>
    </div>
  );
}

function CompareChart({ compare }: { compare: MarketIndexCompareResponse | null }) {
  const width = 1440;
  const height = 408;
  const chartX = 58;
  const chartRight = 28;
  const chartTop = 24;
  const chartBottom = 36;
  const series = compare?.series ?? [];
  const values = series.flatMap((item) => item.points.map((point) => point.value));
  const range = minMax(values);
  const dateValues = series
    .flatMap((item) => item.points.map((point) => new Date(point.date).getTime()))
    .filter((value) => Number.isFinite(value));
  const minDate = dateValues.length ? Math.min(...dateValues) : 0;
  const maxDate = dateValues.length ? Math.max(...dateValues) : 1;
  const x = (date: string) => {
    const time = new Date(date).getTime();
    const domain = maxDate - minDate || 1;
    return chartX + ((time - minDate) / domain) * (width - chartX - chartRight);
  };
  const y = (value?: number | null) => (value === null || value === undefined ? height - chartBottom : chartTop + ((range.max - value) / (range.max - range.min || 1)) * (height - chartTop - chartBottom));
  const colors = ["#2563eb", "#ef4444", "#0f9f6e", "#a855f7", "#f59e0b", "#14b8a6"];

  if (!series.some((item) => item.points.length)) {
    return (
      <div className="market-index-chart-empty">
        {TEXT.emptyCompare.split("\n").map((line) => <span key={line}>{line}</span>)}
      </div>
    );
  }

  return (
    <>
      <div className="market-index-compare-legend">
        {series.filter((item) => item.points.length).map((item, idx) => (
          <span key={item.index_code}>
            <i style={{ backgroundColor: colors[idx % colors.length] }} />
            {item.index_name || item.index_code}
          </span>
        ))}
      </div>
      <div className="market-index-chart-scroll market-index-compare-scroll compact">
      <svg className="market-index-compare-svg" viewBox={"0 0 " + width + " " + height} preserveAspectRatio="none" role="img" aria-label={TEXT.compareTitle}>
        {[0, 1, 2].map((grid) => {
          const yy = chartTop + (grid * (height - chartTop - chartBottom)) / 2;
          const tickValue = range.max - (grid * (range.max - range.min)) / 2;
          return <g key={grid}><line x1={chartX} x2={width - chartRight} y1={yy} y2={yy} className="market-index-grid" /><text x={chartX - 10} y={yy + 4} textAnchor="end" className="market-index-axis-label">{formatNumber(tickValue, 1)}</text></g>;
        })}
        {series.map((item, idx) => {
          const path = item.points
            .filter((point) => point.value !== null && point.value !== undefined && Number.isFinite(point.value))
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((point, pointIdx) => (pointIdx === 0 ? "M" : "L") + x(point.date).toFixed(1) + "," + y(point.value).toFixed(1))
            .join(" ");
          return <path key={item.index_code} d={path} fill="none" stroke={colors[idx % colors.length]} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />;
        })}
      </svg>
      </div>
    </>
  );
}

function MappingStatusPanel({ mappings }: { mappings: MarketIndexProviderMapping[] }) {
  if (!mappings.length) {
    return <div className="market-index-chart-empty">provider mapping 상태를 불러오지 못했습니다.</div>;
  }
  return (
    <SectionCard className="market-index-mapping-card">
      <div className="market-index-section-head">
        <div>
          <h3>Provider 매핑 상태</h3>
          <p>실제 수집에 사용할 provider symbol과 검증 상태를 확인합니다.</p>
        </div>
      </div>
      <div className="market-index-mapping-table-wrap">
        <table className="data-table compact-table market-index-mapping-table">
          <thead>
            <tr>
              <th>지표명</th>
              <th>코드</th>
              <th>provider</th>
              <th>api_type</th>
              <th>api_id</th>
              <th>endpoint</th>
              <th>symbol</th>
              <th>enabled</th>
              <th>verified</th>
              <th>최근 검증</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((mapping) => (
              <tr key={`${mapping.index_code}-${mapping.provider}`}>
                <td>{mapping.index_name || mapping.index_code}</td>
                <td className="mono-cell">{mapping.index_code}</td>
                <td>{mapping.provider}</td>
                <td>{mapping.api_type || "-"}</td>
                <td className="mono-cell">{mapping.api_id || "-"}</td>
                <td className="mono-cell">{mapping.endpoint_url || "-"}</td>
                <td className="mono-cell">{mapping.provider_symbol || "-"}</td>
                <td>{mapping.is_enabled ? "ON" : "OFF"}</td>
                <td>{mapping.is_verified ? "검증됨" : "미검증"}</td>
                <td>
                  <span className={`status-badge status-${String(mapping.last_test_status || "WAITING").toLowerCase()}`}>
                    {mapping.last_test_status || "WAITING"}
                  </span>
                  {mapping.last_test_message ? <p className="market-index-mapping-message">{mapping.last_test_message}</p> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function ProviderCodePanel({
  codes,
  marketType,
  onMarketTypeChange,
  onCollect,
  onAutoMatch,
  onTestCandidates,
  onActivateVerified,
  autoMatchMessage,
  loading,
}: {
  codes: MarketIndexProviderCode[];
  marketType: string;
  onMarketTypeChange: (value: string) => void;
  onCollect: () => void;
  onAutoMatch: () => void;
  onTestCandidates: () => void;
  onActivateVerified: () => void;
  autoMatchMessage: string | null;
  loading: boolean;
}) {
  const labels: Record<string, string> = { "0": "코스피", "1": "코스닥", "2": "KOSPI200", "4": "KOSPI100", "7": "KRX100" };
  const filteredCodes = marketType === "ALL" ? codes : codes.filter((item) => item.market_type === marketType);
  return (
    <SectionCard className="market-index-provider-code-card">
      <div className="market-index-section-head">
        <div>
          <h3>키움 업종코드 후보</h3>
          <p>ka10101 업종코드 후보를 수집하고 DrCT 지표와 매핑합니다.</p>
        </div>
        <div className="market-index-header-actions">
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={onCollect}>업종코드 수집</button>
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={onAutoMatch}>자동매칭 실행</button>
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={onTestCandidates}>1차 후보 검증</button>
          <button className="btn btn-primary" type="button" disabled={loading} onClick={onActivateVerified}>검증 매핑 활성화</button>
        </div>
      </div>
      <div className="market-index-filter-pills compact">
        {["ALL", "0", "1", "2"].map((value) => (
          <button key={value} className={`market-index-filter-pill ${marketType === value ? "active" : ""}`} type="button" onClick={() => onMarketTypeChange(value)}>{value === "ALL" ? "전체" : labels[value] || value}</button>
        ))}
      </div>
      {autoMatchMessage ? <p className="market-index-provider-code-message">{autoMatchMessage}</p> : null}
      <div className="market-index-mapping-table-wrap">
        <table className="data-table compact-table market-index-provider-code-table">
          <thead><tr><th>시장</th><th>코드</th><th>명칭</th><th>그룹</th><th>매칭 DrCT 지표</th><th>상태</th></tr></thead>
          <tbody>
            {filteredCodes.length ? filteredCodes.map((code) => (
              <tr key={`${code.market_type}-${code.code}`}>
                <td>{labels[code.market_type] || code.market_type}</td>
                <td className="mono-cell">{code.code}</td>
                <td>{code.name}</td>
                <td>{code.group_name || "-"}</td>
                <td className="mono-cell">{code.matched_index_code || "-"}</td>
                <td><span className={`status-badge status-${code.matched_index_code ? "success" : "waiting"}`}>{code.matched_index_code ? "MATCHED" : "WAITING"}</span></td>
              </tr>
            )) : <tr><td colSpan={6}>수집된 후보가 없습니다.</td></tr>}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function MarketIndexesPage() {
  const [indexes, setIndexes] = useState<MarketIndexItem[]>([]);
  const [generalIndicators, setGeneralIndicators] = useState<MarketIndicator[]>([]);
  const [selectedCode, setSelectedCode] = useState("KOSPI");
  const [selectedMetricKey, setSelectedMetricKey] = useState<MetricKey>(makeMetricKey("MARKET_INDEX", "KOSPI"));
  const [selectedCompareCodes, setSelectedCompareCodes] = useState<string[]>([makeMetricKey("MARKET_INDEX", "KOSPI"), makeMetricKey("MARKET_INDEX", "KOSDAQ")]);
  const [openCompareGroups, setOpenCompareGroups] = useState<CompareGroupKey[]>(["DOMESTIC"]);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("전체");
  const [searchText, setSearchText] = useState("");
  const [period, setPeriod] = useState<PeriodLabel>("6M");
  const [dailyRows, setDailyRows] = useState<MarketIndexDailyPriceItem[]>([]);
  const [indicatorRows, setIndicatorRows] = useState<MarketIndicatorValue[]>([]);
  const [compare, setCompare] = useState<MarketIndexCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [noticeType, setNoticeType] = useState<"success" | "error">("success");
  const [providerMappings, setProviderMappings] = useState<MarketIndexProviderMapping[]>([]);
  const [providerCodes, setProviderCodes] = useState<MarketIndexProviderCode[]>([]);
  const [providerCodeMarketType, setProviderCodeMarketType] = useState("ALL");
  const [autoMatchMessage, setAutoMatchMessage] = useState<string | null>(null);
  const [showAdminTools, setShowAdminTools] = useState(false);
  const [adminDrawerTab, setAdminDrawerTab] = useState<AdminDrawerTab>("mapping");
  const [showDeferredIndicators, setShowDeferredIndicators] = useState(false);
  const [externalProviderStatuses, setExternalProviderStatuses] = useState<ExternalProviderStatus[]>([]);

  const range = useMemo(() => getRange(period), [period]);
  const selectedMetric = useMemo(() => parseMetricKey(selectedMetricKey), [selectedMetricKey]);
  const selectedIndex = selectedMetric.source === "MARKET_INDEX" ? indexes.find((item) => item.index_code === selectedMetric.code) ?? null : null;
  const selectedGeneralIndicator = selectedMetric.source === "MARKET_INDICATOR" ? generalIndicators.find((item) => item.indicator_code === selectedMetric.code) ?? null : null;
  const selectedIndexName = selectedIndex ? getIndexName(selectedIndex) : getIndicatorName(selectedGeneralIndicator ?? { indicator_code: selectedMetric.code, indicator_name: selectedMetric.code });
  const selectedStatusValue = selectedIndex ? getStatusValue(selectedIndex.collection_status, Boolean(selectedIndex.latest_price_date)) : getStatusValue(selectedGeneralIndicator?.collection_status, Boolean(selectedGeneralIndicator?.latest_value_date));
  const chartRows = useMemo(
    () => dailyRows.filter((row) => row.close_price !== null && row.close_price !== undefined && Number.isFinite(row.close_price)),
    [dailyRows]
  );
  const indicatorChartRows = useMemo(() => indicatorRows.filter((row) => {
    const value = row.value ?? row.close_value;
    return value !== null && value !== undefined && Number.isFinite(value);
  }), [indicatorRows]);
  const chartRangeLabel = selectedMetric.source === "MARKET_INDICATOR"
    ? indicatorChartRows.length
      ? indicatorChartRows[0]?.value_date + " ~ " + indicatorChartRows[indicatorChartRows.length - 1]?.value_date
      : (range.startDate ?? TEXT.allPeriod) + " ~ " + range.endDate
    : chartRows.length
      ? chartRows[0]?.price_date + " ~ " + chartRows[chartRows.length - 1]?.price_date
      : (range.startDate ?? TEXT.allPeriod) + " ~ " + range.endDate;
  const normalizedQuery = searchText.trim().toLowerCase();
  const deferredIndexes = useMemo(
    () => indexes.filter((item) => isDeferredStatus(getStatusValue(item.collection_status, Boolean(item.latest_price_date)))),
    [indexes]
  );
  const activeGeneralIndicators = useMemo(
    () => generalIndicators.filter((item) => GENERAL_INDICATOR_CODES.includes(item.indicator_code as (typeof GENERAL_INDICATOR_CODES)[number]) && item.is_active),
    [generalIndicators]
  );

  const filteredIndexes = useMemo(
    () =>
      indexes.filter((item) => {
        const statusValue = getStatusValue(item.collection_status, Boolean(item.latest_price_date));
        const deferred = isDeferredStatus(statusValue);
        const category = item.category || "";
        const categoryMatched =
          categoryFilter === "전체"
            ? !deferred
            : categoryFilter === "주식시장"
              ? ["국내대표지수", "국내보조지수"].includes(category)
              : categoryFilter === "업종"
                ? category === "업종지수"
                : categoryFilter === "금현물"
                  ? category === "금현물"
                  : categoryFilter === "금리/환율"
                    ? false
                    : deferred;
        const keywordMatched =
          !normalizedQuery ||
          item.index_code.toLowerCase().includes(normalizedQuery) ||
          getIndexName(item).toLowerCase().includes(normalizedQuery) ||
          category.toLowerCase().includes(normalizedQuery);
        return categoryMatched && keywordMatched;
      }),
    [categoryFilter, indexes, normalizedQuery]
  );

  const selectorItems = useMemo<SelectorMetricItem[]>(() => {
    const indexItems = filteredIndexes.map((item) => ({
      key: makeMetricKey("MARKET_INDEX", item.index_code),
      source: "MARKET_INDEX" as const,
      code: item.index_code,
      name: getIndexName(item),
      category: item.category || "-",
      status: getStatusValue(item.collection_status, Boolean(item.latest_price_date)),
      latestValue: item.latest_close_price,
      latestDate: item.latest_price_date,
      return5: item.recent_5d_return_pct ?? item.recent_5d_return,
      return20: item.recent_20d_return_pct ?? item.recent_20d_return,
    }));
    const generalItems = (categoryFilter === "전체" || categoryFilter === "금리/환율" ? activeGeneralIndicators : []).map((item) => ({
      key: makeMetricKey("MARKET_INDICATOR", item.indicator_code),
      source: "MARKET_INDICATOR" as const,
      code: item.indicator_code,
      name: getIndicatorName(item),
      category: item.category === "RATE" ? "\uAE08\uB9AC" : item.category === "FX" ? "\uD658\uC728" : item.category,
      status: getStatusValue(item.collection_status, Boolean(item.latest_value_date)),
      latestValue: item.latest_value,
      latestDate: item.latest_value_date,
      changeValue: item.latest_change_value,
      changePct: item.latest_change_pct,
      unitLabel: item.unit_label || item.unit,
    }));
    return [...indexItems, ...generalItems].filter((item) => {
      if (!normalizedQuery) return true;
      return item.code.toLowerCase().includes(normalizedQuery) || item.name.toLowerCase().includes(normalizedQuery) || item.category.toLowerCase().includes(normalizedQuery);
    });
  }, [activeGeneralIndicators, categoryFilter, filteredIndexes, normalizedQuery]);

  const marketSummaryCards = useMemo(() => {
    const byCode = (code: string) => indexes.find((item) => item.index_code === code);
    const kospi = byCode("KOSPI");
    const kosdaq = byCode("KOSDAQ");
    const kospi5 = kospi?.recent_5d_return_pct ?? kospi?.recent_5d_return ?? null;
    const kosdaq5 = kosdaq?.recent_5d_return_pct ?? kosdaq?.recent_5d_return ?? null;
    const marketTone = (kospi5 ?? 0) > 0 && (kosdaq5 ?? 0) > 0 ? "반등" : (kospi5 ?? 0) < 0 && (kosdaq5 ?? 0) < 0 ? "약세" : "혼조";
    const sectorItems = indexes.filter((item) => item.category === "업종지수" && !isDeferredStatus(getStatusValue(item.collection_status, Boolean(item.latest_price_date))));
    const risingSectors = sectorItems.filter((item) => (item.recent_5d_return_pct ?? item.recent_5d_return ?? 0) > 0);
    const fallingSectors = sectorItems.filter((item) => (item.recent_5d_return_pct ?? item.recent_5d_return ?? 0) < 0);
    const sectorLeaders = [...sectorItems]
      .sort((a, b) => (b.recent_5d_return_pct ?? b.recent_5d_return ?? -999) - (a.recent_5d_return_pct ?? a.recent_5d_return ?? -999))
      .slice(0, 2)
      .map((item) => getIndexName(item))
      .join(" / ");
    const gold = byCode("GOLD_KRX");
    const gold5 = gold?.recent_5d_return_pct ?? gold?.recent_5d_return ?? null;
    const gold20 = gold?.recent_20d_return_pct ?? gold?.recent_20d_return ?? null;
    const customRequired = indexes.filter((item) => getStatusValue(item.collection_status, Boolean(item.latest_price_date)) === "CUSTOM_INDEX_REQUIRED").length;
    const noOfficial = indexes.filter((item) => ["NO_OFFICIAL_INDEX", "EXCLUDED"].includes(getStatusValue(item.collection_status, Boolean(item.latest_price_date)))).length;
    return [
      { title: "국내시장", value: marketTone, detail: `${"KOSPI"} ${TEXT.oneDay5} ${formatPercent(kospi5)} / ${"KOSDAQ"} ${TEXT.oneDay5} ${formatPercent(kosdaq5)}`, status: marketTone },
      { title: "보조지수", value: `KOSPI200 ${formatPercent(byCode("KOSPI200")?.recent_5d_return_pct ?? byCode("KOSPI200")?.recent_5d_return)}`, detail: `KOSDAQ150 ${formatPercent(byCode("KOSDAQ150")?.recent_5d_return_pct ?? byCode("KOSDAQ150")?.recent_5d_return)} / KRX100 ${formatPercent(byCode("KRX100")?.recent_5d_return_pct ?? byCode("KRX100")?.recent_5d_return)}`, status: "참고" },
      { title: "업종흐름", value: `상승 ${risingSectors.length} / 하락 ${fallingSectors.length}`, detail: sectorLeaders || "-", status: "흐름" },
      { title: "금현물", value: formatPercent(gold5), detail: `${TEXT.oneDay20} ${formatPercent(gold20)}`, status: (gold5 ?? 0) > 0 ? "상승" : (gold5 ?? 0) < 0 ? "하락" : "보합" },
      { title: "보류지표", value: `자체지수 필요 ${customRequired}`, detail: `제외/공식없음 ${noOfficial}`, status: "관리" },
    ];
  }, [indexes]);


  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [list, generalList] = await Promise.all([
        repositories.marketIndexes.list({ active_only: !(showDeferredIndicators || categoryFilter === "\uBCF4\uB958/\uC81C\uC678") }),
        repositories.marketIndicators.list({ active_only: true }),
      ]);
      const nextIndexes = list.items;
      const nextGeneralIndicators = generalList.items.filter((item) => GENERAL_INDICATOR_CODES.includes(item.indicator_code as (typeof GENERAL_INDICATOR_CODES)[number]));
      setIndexes(nextIndexes);
      setGeneralIndicators(nextGeneralIndicators);
      repositories.marketIndexes.listProviderMappings?.().then((response) => setProviderMappings(response.items)).catch(() => setProviderMappings([]));
      repositories.marketIndexes.listProviderCodes?.({ market_type: providerCodeMarketType === "ALL" ? undefined : providerCodeMarketType }).then((response) => setProviderCodes(response.items)).catch(() => setProviderCodes([]));
      repositories.marketIndicators.providerStatuses?.().then((response: ExternalProviderStatusListResponse) => setExternalProviderStatuses(response.items)).catch(() => setExternalProviderStatuses([]));

      const currentMetric = parseMetricKey(selectedMetricKey);
      const fallbackIndexCode = nextIndexes.find((item) => item.index_code === "KOSPI")?.index_code || nextIndexes[0]?.index_code || "KOSPI";
      const nextMetric = currentMetric.source === "MARKET_INDICATOR" && nextGeneralIndicators.some((item) => item.indicator_code === currentMetric.code)
        ? currentMetric
        : currentMetric.source === "MARKET_INDEX" && nextIndexes.some((item) => item.index_code === currentMetric.code)
          ? currentMetric
          : { source: "MARKET_INDEX" as const, code: fallbackIndexCode };
      const nextMetricKey = makeMetricKey(nextMetric.source, nextMetric.code);
      if (nextMetricKey !== selectedMetricKey) setSelectedMetricKey(nextMetricKey);
      if (nextMetric.source === "MARKET_INDEX" && nextMetric.code !== selectedCode) setSelectedCode(nextMetric.code);

      if (nextMetric.source === "MARKET_INDICATOR") {
        setDailyRows([]);
        const values = await repositories.marketIndicators.values(nextMetric.code, { start_date: range.startDate, end_date: range.endDate });
        setIndicatorRows(values.items);
      } else {
        setIndicatorRows([]);
        const daily = await repositories.marketIndexes.listDailyPrices(nextMetric.code);
        setDailyRows(daily.items);
      }

      const selectedMetrics = (selectedCompareCodes.length ? selectedCompareCodes : [makeMetricKey("MARKET_INDEX", "KOSPI"), makeMetricKey("MARKET_INDEX", "KOSDAQ")]).map(parseMetricKey);
      const indexCompareCodes = selectedMetrics.filter((item) => item.source === "MARKET_INDEX").map((item) => item.code);
      const indicatorCompareCodes = selectedMetrics.filter((item) => item.source === "MARKET_INDICATOR").map((item) => item.code);
      const compareSeries: MarketIndexCompareResponse["series"] = [];
      if (indexCompareCodes.length) {
        const compareResponse = await repositories.marketIndexes.compare({
          index_codes: indexCompareCodes,
          start_date: range.startDate,
          end_date: range.endDate,
          normalize: true,
        });
        compareSeries.push(...compareResponse.series.map((item) => ({ ...item, index_code: makeMetricKey("MARKET_INDEX", item.index_code) })));
      }
      const indicatorSeries = await Promise.all(indicatorCompareCodes.map(async (code) => {
        const indicator = nextGeneralIndicators.find((item) => item.indicator_code === code);
        const values = await repositories.marketIndicators.values(code, { start_date: range.startDate, end_date: range.endDate });
        const rows = values.items
          .map((row) => ({ date: row.value_date, rawValue: row.value ?? row.close_value ?? null }))
          .filter((row): row is { date: string; rawValue: number } => row.rawValue !== null && row.rawValue !== undefined && Number.isFinite(row.rawValue))
          .sort((a, b) => a.date.localeCompare(b.date));
        const base = rows.find((row) => row.rawValue !== 0)?.rawValue ?? null;
        return {
          index_code: makeMetricKey("MARKET_INDICATOR", code),
          index_name: getIndicatorName(indicator ?? { indicator_code: code, indicator_name: code }),
          points: rows.map((row) => ({ date: row.date, value: base ? (row.rawValue / base) * 100 : null, close_price: row.rawValue })),
        };
      }));
      compareSeries.push(...indicatorSeries);
      setCompare({ normalize: true, start_date: range.startDate, end_date: range.endDate, series: compareSeries });
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, providerCodeMarketType, range.endDate, range.startDate, selectedCode, selectedCompareCodes, selectedMetricKey, showDeferredIndicators]);

  useEffect(() => {
    loadAll().catch((error) => {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    });
  }, [loadAll]);

  useEffect(() => {
    const selected = parseMetricKey(selectedMetricKey);
    if (selected.source !== "MARKET_INDEX") return;
    if (!filteredIndexes.length) return;
    if (!filteredIndexes.some((item) => item.index_code === selected.code)) {
      const nextCode = filteredIndexes[0].index_code;
      setSelectedCode(nextCode);
      setSelectedMetricKey(makeMetricKey("MARKET_INDEX", nextCode));
    }
  }, [filteredIndexes, selectedMetricKey]);

  useEffect(() => {
    if (!showAdminTools) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowAdminTools(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showAdminTools]);

  const handleCollect = async (codes?: string[]) => {
    setLoading(true);
    try {
      const result = await repositories.marketIndexes.collect({ index_codes: codes });
      setNoticeType(result.failed_count > 0 ? "error" : "success");
      const waitingCount = result.waiting_count ?? result.results.filter((item) => String(item.status).toUpperCase() === "WAITING").length;
      const excludedCount = result.excluded_count ?? result.results.filter((item) => isDeferredStatus(String(item.status).toUpperCase())).length;
      const customCount = result.custom_index_required_count ?? result.results.filter((item) => String(item.status).toUpperCase() === "CUSTOM_INDEX_REQUIRED").length;
      const scopeLabel = codes?.length === 1 ? "선택 지표" : "전체 지표";
      setNotice(`${scopeLabel} 갱신 완료: 성공 ${result.success_count}개, 대기 ${waitingCount}개, 자체지수 필요/제외 ${excludedCount}개(${customCount}개), 오류 ${result.failed_count}개`);
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };


  const handleCollectProviderCodes = async () => {
    setLoading(true);
    try {
      const marketTypes = providerCodeMarketType === "ALL" ? ["0", "1", "2"] : [providerCodeMarketType];
      const result = await repositories.marketIndexes.collectProviderCodes?.({ provider: "KIWOOM_REST", market_types: marketTypes });
      setNoticeType(result && result.failed_count > 0 ? "error" : "success");
      setNotice(result ? `업종코드 수집 완료: 성공 ${result.success_count}개, 오류 ${result.failed_count}개` : "업종코드 수집 API를 사용할 수 없습니다.");
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const handleAutoMatchSectorCodes = async () => {
    setLoading(true);
    try {
      const result = await repositories.marketIndexes.autoMatchSectorCodes?.();
      const message = result ? `업종코드 자동매칭 완료: 매칭 ${result.matched_count}개, 대기 ${result.waiting_count}개` : "업종코드 자동매칭 API를 사용할 수 없습니다.";
      setAutoMatchMessage(message);
      setNoticeType("success");
      setNotice(message);
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };


  const handleTestFirstSectorCandidates = async () => {
    setLoading(true);
    try {
      const targets = FIRST_SECTOR_CANDIDATES.filter((code) => providerMappings.some((mapping) => mapping.index_code === code && mapping.provider_symbol));
      let success = 0;
      let waiting = 0;
      let failed = 0;
      for (const code of targets) {
        const result = await repositories.marketIndexes.testProviderMapping(code, { start_date: "2026-06-01", end_date: "2026-06-30", save_result: false });
        if (result.status === "SUCCESS") success += 1;
        else if (result.status === "WAITING") waiting += 1;
        else failed += 1;
      }
      const message = `1차 업종 후보 검증 완료: 성공 ${success}개, 대기 ${waiting}개, 오류 ${failed}개`;
      setAutoMatchMessage(message);
      setNoticeType(failed > 0 ? "error" : "success");
      setNotice(message);
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const handleActivateVerifiedMappings = async () => {
    setLoading(true);
    try {
      const targets = providerMappings.filter((mapping) => FIRST_SECTOR_CANDIDATES.includes(mapping.index_code as (typeof FIRST_SECTOR_CANDIDATES)[number]) && mapping.is_verified && !mapping.is_enabled);
      let activated = 0;
      let failed = 0;
      for (const mapping of targets) {
        try {
          await repositories.marketIndexes.activateProviderMapping(mapping.index_code);
          activated += 1;
        } catch {
          failed += 1;
        }
      }
      const message = `검증 완료 매핑 활성화 완료: 활성 ${activated}개, 오류 ${failed}개`;
      setAutoMatchMessage(message);
      setNoticeType(failed > 0 ? "error" : "success");
      setNotice(message);
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const compareGroups = useMemo(() => {
    const selectableItems = indexes.filter((item) => !isDeferredStatus(getStatusValue(item.collection_status, Boolean(item.latest_price_date))));
    const itemByCode = new Map(selectableItems.map((item) => [item.index_code, item]));
    const indicatorByCode = new Map(activeGeneralIndicators.map((item) => [item.indicator_code, item]));
    const usedIndexCodes = new Set<string>();

    return COMPARE_GROUPS.map((group) => {
      const orderedIndexItems = group.indexCodes
        .map((code) => itemByCode.get(code))
        .filter((item): item is MarketIndexItem => Boolean(item))
        .map((item) => ({ key: makeMetricKey("MARKET_INDEX", item.index_code), code: item.index_code, name: getIndexName(item) }));
      const orderedCodes = new Set(group.indexCodes);
      const extraIndexItems = group.prefix
        ? selectableItems
            .filter((item) => item.index_code.startsWith(group.prefix ?? "") && !orderedCodes.has(item.index_code) && !usedIndexCodes.has(item.index_code))
            .sort((a, b) => getIndexName(a).localeCompare(getIndexName(b), "ko-KR"))
            .map((item) => ({ key: makeMetricKey("MARKET_INDEX", item.index_code), code: item.index_code, name: getIndexName(item) }))
        : [];
      const indicatorItems = (group.indicatorCodes ?? [])
        .map((code) => indicatorByCode.get(code))
        .filter((item): item is MarketIndicator => Boolean(item))
        .map((item) => ({ key: makeMetricKey("MARKET_INDICATOR", item.indicator_code), code: item.indicator_code, name: getIndicatorName(item) }));
      const items = [...orderedIndexItems, ...extraIndexItems].filter((item) => {
        if (usedIndexCodes.has(item.code)) return false;
        usedIndexCodes.add(item.code);
        return true;
      });
      return { ...group, items: [...items, ...indicatorItems] };
    });
  }, [activeGeneralIndicators, indexes]);

  const visibleCompareGroups = useMemo(
    () => compareGroups.filter((group) => openCompareGroups.includes(group.key)),
    [compareGroups, openCompareGroups]
  );
  const selectableCompareCodes = useMemo(() => new Set(compareGroups.flatMap((group) => group.items.map((item) => item.key))), [compareGroups]);

  const toggleCompareGroup = (groupKey: CompareGroupKey) => {
    setOpenCompareGroups((prev) => (prev.includes(groupKey) ? prev.filter((key) => key !== groupKey) : [...prev, groupKey]));
  };

  const toggleCompareCode = (key: string) => {
    if (!selectableCompareCodes.has(key)) return;
    setSelectedCompareCodes((prev) => (prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]));
  };

  const handleSelectMetric = (item: SelectorMetricItem) => {
    setSelectedMetricKey(item.key);
    if (item.source === "MARKET_INDEX") setSelectedCode(item.code);
  };

  const handleCollectSelected = () => {
    const selected = parseMetricKey(selectedMetricKey);
    if (selected.source === "MARKET_INDICATOR") {
      setLoading(true);
      repositories.marketIndicators.collect({ indicator_codes: [selected.code] })
        .then((result) => {
          setNoticeType(result.failed_count > 0 ? "error" : "success");
          setNotice(result.message);
          return loadAll();
        })
        .catch((error) => {
          setNoticeType("error");
          setNotice(error instanceof Error ? error.message : String(error));
        })
        .finally(() => setLoading(false));
      return;
    }
    handleCollect([selected.code]);
  };

  return (
    <div className="market-index-page space-y-4">
      <PageHeader
        title={TEXT.pageTitle}
        description={TEXT.pageDescription}
        action={
          <div className="market-index-header-actions">
            <button className="btn btn-secondary" type="button" disabled={loading || !selectedCode} onClick={handleCollectSelected}>{TEXT.collectSelected}</button>
            <button className="btn btn-primary" type="button" disabled={loading} onClick={() => handleCollect()}>{TEXT.collectAll}</button>
            <button className={`btn btn-secondary ${showAdminTools ? "active" : ""}`} type="button" onClick={() => setShowAdminTools((prev) => !prev)}>관리 도구</button>
          </div>
        }
      />

      {notice ? <div className={`inline-result ${noticeType === "error" ? "inline-error" : "inline-success"}`}>{notice}</div> : null}

      <section className="market-indicator-summary-grid" aria-label="시장환경 요약">
        {marketSummaryCards.map((card) => (
          <div key={card.title} className="market-indicator-summary-card">
            <span className="market-indicator-summary-title">{card.title}</span>
            <strong className="market-indicator-summary-value">{card.value}</strong>
            <span className="market-indicator-summary-status">{card.status}</span>
            <p>{card.detail}</p>
          </div>
        ))}
      </section>

      <section className="market-index-toolbar" aria-label="시장 지표 필터">
        <div className="market-index-filter-pills">
          {CATEGORY_OPTIONS.map((category) => (
            <button key={category} className={`market-index-filter-pill ${categoryFilter === category ? "active" : ""}`} type="button" onClick={() => setCategoryFilter(category)}>{category}</button>
          ))}
        </div>
        <input
          className="market-index-search"
          type="search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
          placeholder="지표명 또는 코드 검색"
        />
      </section>
      <p className="market-index-collect-hint">{TEXT.collectHint}</p>
      {showAdminTools ? (
        <div className="market-indicator-admin-drawer-backdrop" role="presentation" onMouseDown={() => setShowAdminTools(false)}>
          <aside className="market-indicator-admin-drawer" role="dialog" aria-modal="true" aria-label="시장 지표 관리 도구" onMouseDown={(event) => event.stopPropagation()}>
            <div className="market-indicator-admin-drawer-header">
              <div>
                <strong>시장 지표 관리 도구</strong>
                <p>매핑, 업종코드, 보류 지표를 필요할 때만 확인합니다.</p>
              </div>
              <button className="btn btn-secondary" type="button" onClick={() => setShowAdminTools(false)}>닫기</button>
            </div>
            <div className="market-indicator-admin-drawer-tabs" role="tablist" aria-label="관리 도구 탭">
              {ADMIN_DRAWER_TABS.map((tab) => (
                <button key={tab.key} className={`market-indicator-admin-drawer-tab ${adminDrawerTab === tab.key ? "active" : ""}`} type="button" role="tab" aria-selected={adminDrawerTab === tab.key} onClick={() => setAdminDrawerTab(tab.key)}>{tab.label}</button>
              ))}
            </div>
            <div className="market-indicator-admin-drawer-body">
              {adminDrawerTab === "mapping" ? (
                <section className="market-indicator-admin-drawer-section">
                  <h3>provider 매핑 상태</h3>
                  <MappingStatusPanel mappings={providerMappings} />
                </section>
              ) : null}
              {adminDrawerTab === "kiwoom" ? (
                <section className="market-indicator-admin-drawer-section">
                  <h3>키움 업종코드</h3>
                  <ProviderCodePanel
                    codes={providerCodes}
                    marketType={providerCodeMarketType}
                    onMarketTypeChange={setProviderCodeMarketType}
                    onCollect={handleCollectProviderCodes}
                    onAutoMatch={handleAutoMatchSectorCodes}
                    onTestCandidates={handleTestFirstSectorCandidates}
                    onActivateVerified={handleActivateVerifiedMappings}
                    autoMatchMessage={autoMatchMessage}
                    loading={loading}
                  />
                </section>
              ) : null}
              {adminDrawerTab === "deferred" ? (
                <section className="market-indicator-admin-drawer-section">
                  <h3>보류/제외 지표</h3>
                  <div className="market-index-deferred-panel">
                    <strong>자체지수 검토 대상</strong>
                    <div>
                      {deferredIndexes.length ? deferredIndexes.map((item) => (
                        <span key={item.index_code} className={`status-badge status-${getStatusClass(getStatusValue(item.collection_status, Boolean(item.latest_price_date)))}`}>
                          {getIndexName(item)} / {getStatusLabel(item.collection_status, Boolean(item.latest_price_date))}
                        </span>
                      )) : <span>보류/제외 지표가 없습니다.</span>}
                    </div>
                  </div>
                </section>
              ) : null}
              {adminDrawerTab === "provider" ? (
                <section className="market-indicator-admin-drawer-section">
                  <h3>대체 provider</h3>
                  <ul className="market-indicator-provider-notes">
                    <li>KRX Open API 후보</li>
                    <li>KIWOOM ETF proxy 후보</li>
                    <li>DrCT 자체 테마지수 후보</li>
                  </ul>
                </section>
              ) : null}
              {adminDrawerTab === "external" ? (
                <section className="market-indicator-admin-drawer-section">
                  <h3>?? API ??</h3>
                  <div className="market-indicator-provider-status-list">
                    {externalProviderStatuses.length ? externalProviderStatuses.map((item) => (
                      <div key={item.provider} className={`market-indicator-provider-status-card ${item.configured ? "configured" : "missing"}`}>
                        <div>
                          <strong>{item.display_name}</strong>
                          <span>{item.provider}</span>
                        </div>
                        <span className="market-indicator-provider-status-state">{item.configured ? "\uC124\uC815\uB428" : "\uD0A4 \uC5C6\uC74C"}</span>
                        <code>{item.masked_key || "-"}</code>
                        <p>{item.message}</p>
                      </div>
                    )) : <div className="market-index-chart-empty compact-empty">외부 API 상태를 불러오지 못했습니다.</div>}
                  </div>
                </section>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}
      <section className="market-indicator-workspace">
        <aside className="market-indicator-selector-panel">
          <div className="market-indicator-selector-head">
            <div>
              <strong>지표 선택</strong>
              <span>{selectorItems.length} items</span>
            </div>
          </div>
          <div className="market-indicator-compact-list">
            {selectorItems.length ? selectorItems.map((item) => {
              const metric5 = item.source === "MARKET_INDEX" ? item.return5 : item.changeValue;
              const metric20 = item.source === "MARKET_INDEX" ? item.return20 : item.changePct;
              return (
                <button
                  key={item.key}
                  className={"market-indicator-compact-card " + (item.key === selectedMetricKey ? "active" : "")}
                  type="button"
                  onClick={() => handleSelectMetric(item)}
                >
                  <div className="market-indicator-compact-head">
                    <div className="market-indicator-compact-main">
                      <strong className="market-indicator-compact-name">{item.name}</strong>
                      <span className="market-indicator-compact-code" title={item.code}>{item.code}</span>
                    </div>
                    <span className={"status-badge market-indicator-compact-status status-" + getStatusClass(item.status)}>{item.source === "MARKET_INDICATOR" ? item.category : getStatusLabel(item.status, Boolean(item.latestDate))}</span>
                  </div>
                  <div className="market-indicator-compact-metrics">
                    <span className={"market-indicator-compact-chip " + ((metric5 ?? 0) >= 0 ? "positive" : "negative")}>{item.source === "MARKET_INDEX" ? TEXT.oneDay5 + " " + formatPercent(metric5) : formatNumber(metric5, 3)}</span>
                    <span className={"market-indicator-compact-chip " + ((metric20 ?? 0) >= 0 ? "positive" : "negative")}>{item.source === "MARKET_INDEX" ? TEXT.oneDay20 + " " + formatPercent(metric20) : formatPercent(metric20)}</span>
                    <span className="market-indicator-compact-chip">{formatNumber(item.latestValue, item.source === "MARKET_INDICATOR" ? 3 : 2)}{item.unitLabel ? " " + item.unitLabel : ""}</span>
                  </div>
                </button>
              );
            }) : (
              <div className="market-index-chart-empty compact-empty">No indicators.</div>
            )}          </div>
        </aside>

        <SectionCard className="market-index-chart-card market-index-candle-card market-indicator-chart-panel">
          <div className="market-index-section-head">
            <div>
              <h3>{`${selectedIndexName} 일봉 차트`}</h3>
              <p>{chartRangeLabel}</p>
            </div>
            <div className="market-index-periods">
              {PERIOD_OPTIONS.map((option) => (
                <button key={option.label} className={`btn btn-secondary ${period === option.label ? "active" : ""}`} type="button" onClick={() => setPeriod(option.label)}>{option.label}</button>
              ))}
            </div>
          </div>
          {selectedMetric.source === "MARKET_INDEX" && selectedIndex ? (
            <div className="market-indicator-selected-summary">
              <div><span>카테고리</span><strong>{selectedIndex.category || "-"}</strong></div>
              <div><span>최근가</span><strong>{formatNumber(selectedIndex.latest_close_price, 2)}</strong></div>
              <div><span>5일</span><strong className={(selectedIndex.recent_5d_return ?? 0) >= 0 ? "positive" : "negative"}>{formatPercent(selectedIndex.recent_5d_return_pct ?? selectedIndex.recent_5d_return)}</strong></div>
              <div><span>20일</span><strong className={(selectedIndex.recent_20d_return ?? 0) >= 0 ? "positive" : "negative"}>{formatPercent(selectedIndex.recent_20d_return_pct ?? selectedIndex.recent_20d_return)}</strong></div>
              <div><span>상태</span><strong>{getStatusLabel(selectedIndex.collection_status, Boolean(selectedIndex.latest_price_date))}</strong></div>
            </div>
          ) : selectedMetric.source === "MARKET_INDICATOR" && selectedGeneralIndicator ? (
            <div className="market-indicator-selected-summary">
              <div><span>Category</span><strong>{selectedGeneralIndicator.category}</strong></div>
              <div><span>Latest</span><strong>{formatNumber(selectedGeneralIndicator.latest_value, 3)}{selectedGeneralIndicator.unit_label ? " " + selectedGeneralIndicator.unit_label : ""}</strong></div>
              <div><span>Date</span><strong>{selectedGeneralIndicator.latest_value_date || "-"}</strong></div>
              <div><span>Change</span><strong className={(selectedGeneralIndicator.latest_change_value ?? 0) >= 0 ? "positive" : "negative"}>{formatNumber(selectedGeneralIndicator.latest_change_value, 3)}</strong></div>
              <div><span>Rate</span><strong className={(selectedGeneralIndicator.latest_change_pct ?? 0) >= 0 ? "positive" : "negative"}>{formatPercent(selectedGeneralIndicator.latest_change_pct)}</strong></div>
            </div>
          ) : null}
          {selectedMetric.source === "MARKET_INDEX" ? <div className="market-index-chart-legend">
            <span className="ma5">MA5</span><span className="ma20">MA20</span><span className="ma60">MA60</span><span className="ma120">MA120</span>
          </div> : null}
          {selectedMetric.source === "MARKET_INDICATOR" ? <MarketIndicatorLineChart rows={indicatorChartRows} indicatorName={selectedIndexName} unitLabel={selectedGeneralIndicator?.unit_label || selectedGeneralIndicator?.unit} /> : <CandleChart rows={chartRows} indexName={selectedIndexName} period={period} statusValue={selectedStatusValue} errorMessage={selectedIndex?.error_message} />}
        </SectionCard>
      </section>

      <SectionCard className="market-index-chart-card">
        <div className="market-index-section-head">
          <div>
            <h3>{TEXT.compareTitle}</h3>
            <p>{TEXT.compareDescription}</p>
          </div>
        </div>
        <div className="market-index-compare-tabs" aria-label="시장 지표 비교 그룹">
          {compareGroups.map((group) => {
            const isOpen = openCompareGroups.includes(group.key);
            return (
              <button
                key={group.key}
                className={`market-index-compare-tab ${isOpen ? "active" : ""}`}
                type="button"
                aria-pressed={isOpen}
                onClick={() => toggleCompareGroup(group.key)}
              >
                {group.label}
              </button>
            );
          })}
        </div>
        <div className="market-index-compare-panels">
          {visibleCompareGroups.length ? visibleCompareGroups.map((group) => (
            <section key={group.key} className="market-index-compare-active-panel" aria-label={group.label}>
              <div className="market-index-compare-group-title">{group.label}</div>
              {group.items.length ? (
                <div className="market-index-compare-check-grid">
                  {group.items.map((item) => (
                    <label key={item.key} className="market-index-compare-check-pill" title={item.name + " / " + item.code}>
                      <input type="checkbox" checked={selectedCompareCodes.includes(item.key)} onChange={() => toggleCompareCode(item.key)} />
                        <span>{item.name}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <div className="market-index-compare-empty">이 그룹에 표시할 수집 지표가 아직 없습니다.</div>
              )}
            </section>
          )) : (
            <div className="market-index-compare-empty-panel">비교할 지표 그룹을 선택해 주세요.</div>
          )}
        </div>
        <CompareChart compare={compare} />
      </SectionCard>
    </div>
  );
}

export default MarketIndexesPage;
