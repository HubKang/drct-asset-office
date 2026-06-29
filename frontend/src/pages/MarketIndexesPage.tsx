import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { MarketIndexCompareResponse, MarketIndexDailyPriceItem, MarketIndexItem } from "@/types/marketIndex";

const PERIOD_OPTIONS = [
  { label: "1M", days: 31 },
  { label: "3M", days: 93 },
  { label: "6M", days: 186 },
  { label: "1Y", days: 365 },
  { label: "ALL", days: null },
] as const;

const CATEGORY_OPTIONS = ["전체", "국내대표지수", "국내보조지수", "업종지수", "금현물"] as const;

type PeriodLabel = (typeof PERIOD_OPTIONS)[number]["label"];
type CategoryFilter = (typeof CATEGORY_OPTIONS)[number];

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
};

const COMPARE_PRESETS = [
  { label: "국내 대표", codes: ["KOSPI", "KOSDAQ", "KOSPI200", "KOSDAQ150"] },
  { label: "반도체", codes: ["KOSDAQ_SEMICONDUCTOR", "KOSPI_ELECTRONICS", "KOSDAQ", "KOSPI200"] },
  { label: "바이오", codes: ["KOSDAQ_PHARMA", "KOSPI_PHARMA", "KOSDAQ"] },
  { label: "위험회피", codes: ["GOLD_KRX", "KOSPI", "KOSDAQ"] },
];

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
  if (status === "READY" || !status) return hasPrice ? "LATEST" : "NOT_COLLECTED";
  return STATUS_LABELS[status] ? status : hasPrice ? "LATEST" : "NOT_COLLECTED";
};

const getStatusLabel = (raw?: string | null, hasPrice = false) => STATUS_LABELS[getStatusValue(raw, hasPrice)] ?? TEXT.notCollected;

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

function CandleChart({ rows, indexName }: { rows: MarketIndexDailyPriceItem[]; indexName: string }) {
  const visibleRows = rows.filter((row) => row.close_price !== null && row.close_price !== undefined);
  const candleSlot = 24;
  const width = Math.max(720, visibleRows.length * candleSlot + 96);
  const priceHeight = 520;
  const volumeHeight = 130;
  const height = priceHeight + volumeHeight + 52;
  const chartX = 44;
  const chartRight = 28;
  const chartWidth = width - chartX - chartRight;
  const gap = visibleRows.length > 1 ? chartWidth / visibleRows.length : chartWidth;
  const candleWidth = Math.max(8, Math.min(14, gap * 0.58));
  const priceRange = minMax(visibleRows.flatMap((row) => [row.open_price, row.high_price, row.low_price, row.close_price, row.ma5, row.ma20, row.ma60, row.ma120]));
  const volumeMax = Math.max(...visibleRows.map((row) => row.volume ?? 0), 1);
  const y = (value?: number | null) => {
    if (value === null || value === undefined) return priceHeight;
    return 16 + ((priceRange.max - value) / (priceRange.max - priceRange.min)) * (priceHeight - 32);
  };
  const x = (idx: number) => chartX + idx * gap + gap / 2;
  const linePath = (key: "ma5" | "ma20" | "ma60" | "ma120") =>
    visibleRows
      .map((row, idx) => (row[key] === null || row[key] === undefined ? null : `${idx === 0 ? "M" : "L"}${x(idx).toFixed(1)},${y(row[key]).toFixed(1)}`))
      .filter(Boolean)
      .join(" ");

  if (!visibleRows.length) {
    return (
      <div className="market-index-chart-empty">
        <strong>{`수집된 ${indexName} 일봉 데이터가 없습니다.`}</strong>
        <span>상단의 선택 지표 갱신 또는 전체 지표 갱신을 실행해 주세요.</span>
      </div>
    );
  }

  return (
    <div className="market-index-chart-scroll">
      <svg className="market-index-candle-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${indexName} 일봉 차트`}>
        {[0, 1, 2, 3, 4].map((grid) => {
          const yy = 18 + (grid * (priceHeight - 36)) / 4;
          return <line key={grid} x1={chartX} x2={width - chartRight} y1={yy} y2={yy} className="market-index-grid" />;
        })}
        <line x1={chartX} x2={width - chartRight} y1={priceHeight + volumeHeight + 18} y2={priceHeight + volumeHeight + 18} className="market-index-volume-baseline" />
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
              <rect x={cx - candleWidth / 2} y={priceHeight + 18 + (volumeHeight - volumeH)} width={candleWidth} height={volumeH} rx="0" className={up ? "market-index-volume-up" : "market-index-volume-down"} />
            </g>
          );
        })}
        <path d={linePath("ma5")} className="market-index-ma ma5" />
        <path d={linePath("ma20")} className="market-index-ma ma20" />
        <path d={linePath("ma60")} className="market-index-ma ma60" />
        <path d={linePath("ma120")} className="market-index-ma ma120" />
        <text x={chartX} y={height - 8} className="market-index-axis-label">{visibleRows[0]?.price_date}</text>
        <text x={width - 24} y={height - 8} textAnchor="end" className="market-index-axis-label">{visibleRows[visibleRows.length - 1]?.price_date}</text>
      </svg>
    </div>
  );
}

function CompareChart({ compare }: { compare: MarketIndexCompareResponse | null }) {
  const width = 960;
  const height = 260;
  const series = compare?.series ?? [];
  const values = series.flatMap((item) => item.points.map((point) => point.value));
  const range = minMax(values);
  const maxLength = Math.max(...series.map((item) => item.points.length), 0);
  const x = (idx: number) => 28 + (idx / Math.max(maxLength - 1, 1)) * (width - 52);
  const y = (value?: number | null) => (value === null || value === undefined ? height - 24 : 18 + ((range.max - value) / (range.max - range.min)) * (height - 48));
  const colors = ["#2563eb", "#ef4444", "#0f9f6e", "#a855f7", "#f59e0b", "#14b8a6"];

  if (!series.some((item) => item.points.length)) {
    return (
      <div className="market-index-chart-empty">
        {TEXT.emptyCompare.split("\n").map((line) => <span key={line}>{line}</span>)}
      </div>
    );
  }

  return (
    <div className="market-index-chart-scroll compact">
      <svg className="market-index-compare-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={TEXT.compareTitle}>
        {[0, 1, 2].map((grid) => {
          const yy = 18 + (grid * (height - 48)) / 2;
          return <line key={grid} x1={28} x2={width - 24} y1={yy} y2={yy} className="market-index-grid" />;
        })}
        {series.map((item, idx) => {
          const path = item.points
            .map((point, pointIdx) => (point.value === null || point.value === undefined ? null : `${pointIdx === 0 ? "M" : "L"}${x(pointIdx).toFixed(1)},${y(point.value).toFixed(1)}`))
            .filter(Boolean)
            .join(" ");
          return <path key={item.index_code} d={path} fill="none" stroke={colors[idx % colors.length]} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />;
        })}
      </svg>
    </div>
  );
}

function MarketIndexesPage() {
  const [indexes, setIndexes] = useState<MarketIndexItem[]>([]);
  const [selectedCode, setSelectedCode] = useState("KOSPI");
  const [selectedCompareCodes, setSelectedCompareCodes] = useState<string[]>(["KOSPI", "KOSDAQ"]);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("전체");
  const [searchText, setSearchText] = useState("");
  const [period, setPeriod] = useState<PeriodLabel>("ALL");
  const [dailyRows, setDailyRows] = useState<MarketIndexDailyPriceItem[]>([]);
  const [compare, setCompare] = useState<MarketIndexCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [noticeType, setNoticeType] = useState<"success" | "error">("success");

  const range = useMemo(() => getRange(period), [period]);
  const selectedIndex = indexes.find((item) => item.index_code === selectedCode) ?? indexes[0];
  const selectedIndexName = getIndexName(selectedIndex ?? { index_code: selectedCode, index_name: selectedCode });
  const normalizedQuery = searchText.trim().toLowerCase();
  const filteredIndexes = useMemo(
    () =>
      indexes.filter((item) => {
        const categoryMatched = categoryFilter === "전체" || item.category === categoryFilter;
        const keywordMatched =
          !normalizedQuery ||
          item.index_code.toLowerCase().includes(normalizedQuery) ||
          getIndexName(item).toLowerCase().includes(normalizedQuery) ||
          (item.category || "").toLowerCase().includes(normalizedQuery);
        return categoryMatched && keywordMatched;
      }),
    [categoryFilter, indexes, normalizedQuery]
  );

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const list = await repositories.marketIndexes.list({ active_only: true });
      const nextIndexes = list.items;
      setIndexes(nextIndexes);
      const nextSelected = nextIndexes.some((item) => item.index_code === selectedCode) ? selectedCode : nextIndexes.find((item) => item.index_code === "KOSPI")?.index_code || nextIndexes[0]?.index_code || "KOSPI";
      if (nextSelected !== selectedCode) setSelectedCode(nextSelected);
      const daily = await repositories.marketIndexes.listDailyPrices(nextSelected, {
        start_date: range.startDate,
        end_date: range.endDate,
      });
      setDailyRows(daily.items);
      const compareResponse = await repositories.marketIndexes.compare({
        index_codes: selectedCompareCodes.length ? selectedCompareCodes : ["KOSPI", "KOSDAQ"],
        start_date: range.startDate,
        end_date: range.endDate,
        normalize: true,
      });
      setCompare(compareResponse);
    } finally {
      setLoading(false);
    }
  }, [range.endDate, range.startDate, selectedCode, selectedCompareCodes]);

  useEffect(() => {
    loadAll().catch((error) => {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    });
  }, [loadAll]);

  const handleCollect = async (codes?: string[]) => {
    setLoading(true);
    try {
      const result = await repositories.marketIndexes.collect({ index_codes: codes });
      setNoticeType(result.failed_count > 0 ? "error" : "success");
      const waitingCount = result.results.filter((item) => String(item.status).toUpperCase() === "WAITING").length;
      if (result.failed_count > 0 && result.success_count > 0) {
        setNotice("일부 시장 지표 데이터 갱신에 실패했습니다. 오류 상태를 확인해 주세요.");
      } else if (result.failed_count > 0) {
        setNotice("시장 지표 데이터 갱신 중 오류가 발생했습니다.");
      } else if (waitingCount > 0) {
        setNotice(`시장 지표 갱신 요청을 처리했습니다. ${waitingCount}개 지표는 provider mapping 확인 전까지 수집대기 상태입니다.`);
      } else {
        setNotice(result.message);
      }
      await loadAll();
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const toggleCompareCode = (code: string) => {
    setSelectedCompareCodes((prev) => (prev.includes(code) ? prev.filter((item) => item !== code) : [...prev, code]));
  };

  const applyPreset = (codes: string[]) => {
    const available = codes.filter((code) => indexes.some((item) => item.index_code === code));
    setSelectedCompareCodes(available.length ? available : codes);
  };

  return (
    <div className="market-index-page space-y-4">
      <PageHeader
        title={TEXT.pageTitle}
        description={TEXT.pageDescription}
        action={
          <div className="market-index-header-actions">
            <button className="btn btn-secondary" type="button" disabled={loading || !selectedCode} onClick={() => handleCollect([selectedCode])}>{TEXT.collectSelected}</button>
            <button className="btn btn-primary" type="button" disabled={loading} onClick={() => handleCollect()}>{TEXT.collectAll}</button>
          </div>
        }
      />

      {notice ? <div className={`inline-result ${noticeType === "error" ? "inline-error" : "inline-success"}`}>{notice}</div> : null}

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
      {categoryFilter === "업종지수" ? <p className="market-index-guide">{TEXT.industryGuide}</p> : null}

      <section className="market-index-card-grid">
        {filteredIndexes.map((item) => {
          const displayName = getIndexName(item);
          const statusValue = getStatusValue(item.collection_status, Boolean(item.latest_price_date));
          return (
            <button
              key={item.index_code}
              className={`market-index-summary-card ${item.index_code === selectedCode ? "selected" : ""}`}
              type="button"
              onClick={() => setSelectedCode(item.index_code)}
            >
              <span className={`status-badge status-${statusValue.toLowerCase().replace("_", "-")}`}>{getStatusLabel(item.collection_status, Boolean(item.latest_price_date))}</span>
              <strong>{displayName}</strong>
              <span className="market-index-code">{item.index_code} / {item.category || "시장지표"} / {item.provider}</span>
              <dl className="market-index-card-metrics">
                <div><dt>{TEXT.latestClose}</dt><dd>{formatNumber(item.latest_close_price, 2)}</dd></div>
                <div><dt>{TEXT.latestDate}</dt><dd>{item.latest_price_date ?? "-"}</dd></div>
                <div><dt>{TEXT.oneDay5}</dt><dd className={(item.recent_5d_return ?? 0) >= 0 ? "positive" : "negative"}>{formatPercent(item.recent_5d_return)}</dd></div>
                <div><dt>{TEXT.oneDay20}</dt><dd className={(item.recent_20d_return ?? 0) >= 0 ? "positive" : "negative"}>{formatPercent(item.recent_20d_return)}</dd></div>
                <div><dt>{TEXT.tradingValue}</dt><dd>{formatTradingValue(item.latest_trading_value)}</dd></div>
                <div><dt>{TEXT.status}</dt><dd>{getStatusLabel(item.collection_status, Boolean(item.latest_price_date))}</dd></div>
              </dl>
              {(statusValue === "ERROR" || statusValue === "WAITING") && item.error_message ? <p className="market-index-error-text">{item.error_message}</p> : null}
            </button>
          );
        })}
      </section>

      <SectionCard className="market-index-chart-card">
        <div className="market-index-section-head">
          <div>
            <h3>{`${selectedIndexName} 일봉 차트`}</h3>
            <p>{range.startDate ?? TEXT.allPeriod} ~ {range.endDate}</p>
          </div>
          <div className="market-index-periods">
            {PERIOD_OPTIONS.map((option) => (
              <button key={option.label} className={`btn btn-secondary ${period === option.label ? "active" : ""}`} type="button" onClick={() => setPeriod(option.label)}>{option.label}</button>
            ))}
          </div>
        </div>
        <div className="market-index-chart-legend">
          <span className="ma5">MA5</span><span className="ma20">MA20</span><span className="ma60">MA60</span><span className="ma120">MA120</span>
        </div>
        <CandleChart rows={dailyRows} indexName={selectedIndexName} />
      </SectionCard>

      <SectionCard className="market-index-chart-card">
        <div className="market-index-section-head">
          <div>
            <h3>{TEXT.compareTitle}</h3>
            <p>{TEXT.compareDescription}</p>
          </div>
        </div>
        <div className="market-index-compare-toolbar">
          <div className="market-index-presets">
            {COMPARE_PRESETS.map((preset) => (
              <button key={preset.label} className="btn btn-secondary" type="button" onClick={() => applyPreset(preset.codes)}>{preset.label}</button>
            ))}
          </div>
          <div className="market-index-checks market-index-check-scroll">
            {filteredIndexes.map((item) => (
              <label key={item.index_code}>
                <input type="checkbox" checked={selectedCompareCodes.includes(item.index_code)} onChange={() => toggleCompareCode(item.index_code)} />
                {getIndexName(item)}
              </label>
            ))}
          </div>
        </div>
        <CompareChart compare={compare} />
      </SectionCard>
    </div>
  );
}

export default MarketIndexesPage;
