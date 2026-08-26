import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import MarketThemeDetailDrawer from "@/components/marketThemes/MarketThemeDetailDrawer";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";
import { repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import type { MarketDataCollectionRun } from "@/types/marketData";
import type { MarketCalendarEvent, MarketCalendarImportance } from "@/types/marketCalendar";
import type { MarketSignalCurrentStateItem } from "@/types/marketSignal";
import type { UsThemeDashboardSummary } from "@/types/usMarketTheme";
import type {
  MarketTheme,
  MarketThemeObservationResponse,
  MarketThemeMonthlyReturnResponse,
  MarketThemeMonthlyReturnThemeItem,
  MarketThemeReturnRefreshResponse,
} from "@/types/marketTheme";
import {
  buildNaverKoreaMarketChartUrl,
  buildNaverMarketIndexAreaChartUrl,
  buildNaverWorldIndexChartUrl,
  createNaverChartSidcode,
} from "@/utils/naverChart";

type DashboardIndicator = {
  title: string;
  category: string;
  imageUrl: string;
  helpType?: "dollar-index";
};

type ReadinessStatus = "FRESH" | "STALE" | "RUNNING" | "PARTIAL" | "FAILED";

type ThemeReadiness = {
  dataDate: string | null;
  lastSuccessAt: string | null;
  linkedStockCount: number;
  status: ReadinessStatus;
};

type MarketReadiness = {
  dataDate: string | null;
  lastRunAt: string | null;
  activeIndicatorCount: number;
  status: ReadinessStatus;
};

type ActionFeedback = {
  tone: "success" | "warning" | "error";
  message: string;
};

type ThemeSummaryRow = {
  themeId: number;
  themeName: string;
  themeGroupName: string | null;
  dailyReturn: number | null;
  rolling30dReturn: number | null;
  persistenceRate: number | null;
  positiveDays: number | null;
  observedDays: number | null;
};

type ThemeSummaryData = {
  dataDate: string;
  topGainers: ThemeSummaryRow[];
  topPersistence: ThemeSummaryRow[];
};

type MarketSignalSummaryRow = MarketSignalCurrentStateItem & {
  isTodayTransition: boolean;
};

type UpcomingCalendarData = {
  startDate: string;
  endDate: string;
  events: Array<MarketCalendarEvent & { displayDate: string }>;
};

const DOLLAR_INDEX_HELP_URL = "https://blog.naver.com/annalife_/224280737671?photoView=3";
const THEME_FLOW_COLLECTOR = "market_theme_price_flow_refresh";

const todayInKst = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());

const shiftKstDate = (dateValue: string, days: number) => {
  const date = new Date(`${dateValue}T12:00:00+09:00`);
  date.setDate(date.getDate() + days);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(date);
};

const shiftBusinessDay = (dateValue: string, direction: -1 | 1) => {
  const value = new Date(`${dateValue}T00:00:00Z`);
  do value.setUTCDate(value.getUTCDate() + direction);
  while (value.getUTCDay() === 0 || value.getUTCDay() === 6);
  return value.toISOString().slice(0, 10);
};

const latestExpectedTradingDate = () => {
  const today = todayInKst();
  const date = new Date(`${today}T12:00:00+09:00`);
  while (date.getDay() === 0 || date.getDay() === 6) date.setDate(date.getDate() - 1);
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(date);
};

const latestExpectedUsTradingDate = () => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const dateValue = `${value.year}-${value.month}-${value.day}`;
  const date = new Date(`${dateValue}T12:00:00Z`);
  if (date.getUTCDay() !== 0 && date.getUTCDay() !== 6 && Number(value.hour) >= 18) return dateValue;
  return shiftBusinessDay(dateValue, -1);
};

const maxDate = (values: Array<string | null | undefined>) =>
  values.reduce<string | null>((latest, value) => {
    const date = value?.slice(0, 10) ?? "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return latest;
    return latest == null || date > latest ? date : latest;
  }, null);

const maxTimestamp = (values: Array<string | null | undefined>) =>
  values.reduce<string | null>((latest, value) => {
    if (!value) return latest;
    return latest == null || value > latest ? value : latest;
  }, null);

const isRunningStatus = (status?: string | null) => {
  const normalized = String(status ?? "").toUpperCase();
  return normalized === "RUNNING" || normalized === "PENDING";
};

const resolveReadinessStatus = (dataDate: string | null, runStatus?: string | null, expectedDate = latestExpectedTradingDate()): ReadinessStatus => {
  const normalized = String(runStatus ?? "").toUpperCase();
  if (isRunningStatus(normalized)) return "RUNNING";
  if (normalized.includes("PARTIAL")) return "PARTIAL";
  if (normalized === "FAILED" || normalized === "FAILURE") return "FAILED";
  return dataDate && dataDate >= expectedDate ? "FRESH" : "STALE";
};

const formatDate = (value: string | null) => value || "확인되지 않음";

const formatDateTime = (value: string | null) => {
  if (!value) return "이력 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace("T", " ").slice(0, 16);
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
};

const statusPresentation: Record<ReadinessStatus, { label: string; tone: "emerald" | "amber" | "blue" | "rose" | "slate" }> = {
  FRESH: { label: "최신", tone: "emerald" },
  STALE: { label: "갱신 권장", tone: "amber" },
  RUNNING: { label: "갱신 중", tone: "blue" },
  PARTIAL: { label: "부분 완료", tone: "amber" },
  FAILED: { label: "실패", tone: "rose" },
};

const errorMessage = (error: unknown) =>
  error instanceof Error && error.message ? error.message : "요청을 처리하지 못했습니다.";

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const formatSignedPercent = (value: number | null) => {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
};

const SIGNAL_STATE_LABELS: Record<string, string> = {
  TREND_WEAKENING: "추세 약화",
  BREAK_CANDIDATE: "추세 이탈 후보",
  BREAK_CONFIRMED: "추세 이탈 확인",
  REVERSAL_CONFIRMED: "반전 확인",
  FALSE_BREAK: "일시 이탈 후 복귀",
  TREND_RESUMED: "기존 추세 재개",
  DATA_SHORTAGE: "데이터 부족",
  DATA_INSUFFICIENT: "데이터 부족",
  INSUFFICIENT_DATA: "데이터 부족",
  ERROR: "평가 오류",
  NOT_EVALUATED: "미평가",
};

const SIGNAL_SEVERITY: Record<string, number> = {
  ERROR: 0,
  BREAK_CONFIRMED: 1,
  REVERSAL_CONFIRMED: 2,
  BREAK_CANDIDATE: 3,
  TREND_WEAKENING: 4,
  FALSE_BREAK: 5,
  TREND_RESUMED: 6,
  DATA_SHORTAGE: 7,
  DATA_INSUFFICIENT: 7,
  INSUFFICIENT_DATA: 7,
  NOT_EVALUATED: 8,
};

const MAINTAINED_SIGNAL_STATES = new Set(["TREND_INTACT", "TREND_MAINTAINED", "MAINTAINED"]);

const signalTone = (state: string) => {
  if (["ERROR", "BREAK_CONFIRMED", "REVERSAL_CONFIRMED"].includes(state)) return "danger";
  if (["BREAK_CANDIDATE", "TREND_WEAKENING"].includes(state)) return "warning";
  if (["DATA_SHORTAGE", "DATA_INSUFFICIENT", "INSUFFICIENT_DATA", "NOT_EVALUATED"].includes(state)) return "neutral";
  return "info";
};

const calendarImportanceLabel: Record<MarketCalendarImportance, string> = {
  high: "중요",
  medium: "보통",
  low: "참고",
};

const calendarImportanceOrder: Record<MarketCalendarImportance, number> = { high: 0, medium: 1, low: 2 };

const OBSERVATION_STATE_LABELS: Record<string, string> = {
  FLOW_LEADING: "수급 선도",
  STRONG_CONTINUATION: "강세 지속",
  REVERSAL_WATCH: "반전 관찰",
  NEUTRAL: "중립",
  OVERHEAT_RISK: "과열 위험",
  FLOW_EXIT: "수급 이탈",
};

const observationDateLabel = (targetDate: string) => {
  return `관찰 대상 ${targetDate.slice(5).replace("-", ".")}`;
};

const formatCalendarDate = (value: string) => {
  const date = new Date(`${value}T12:00:00+09:00`);
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", weekday: "short" }).format(date);
};

const buildThemeSummary = (response: MarketThemeMonthlyReturnResponse): ThemeSummaryData | null => {
  const dataDate = maxDate(response.themes.flatMap((theme) => theme.daily_returns.map((item) => item.return_date)));
  if (!dataDate) return null;
  const toRow = (theme: MarketThemeMonthlyReturnThemeItem): ThemeSummaryRow => {
    const latest = theme.daily_returns.find((item) => item.return_date === dataDate);
    return {
      themeId: theme.theme_id,
      themeName: theme.theme_name,
      themeGroupName: theme.theme_group_name,
      dailyReturn: latest?.avg_change_rate ?? null,
      rolling30dReturn: latest?.rolling_30d_change_rate ?? theme.rolling_30d_change_rate ?? null,
      persistenceRate: theme.persistence_10d ?? null,
      positiveDays: theme.positive_days_10d ?? null,
      observedDays: theme.observed_days_10d ?? null,
    };
  };
  const rows = response.themes.map(toRow);
  return {
    dataDate,
    topGainers: rows
      .filter((row) => row.dailyReturn != null && row.dailyReturn > 0)
      .sort((a, b) => Number(b.dailyReturn) - Number(a.dailyReturn))
      .slice(0, 6),
    topPersistence: rows
      .filter((row) => row.persistenceRate != null && Number(row.observedDays) > 0)
      .sort((a, b) =>
        Number(b.persistenceRate) - Number(a.persistenceRate)
        || Number(b.positiveDays) - Number(a.positiveDays)
        || a.themeName.localeCompare(b.themeName, "ko-KR"))
      .slice(0, 6),
  };
};

type ThemeRankPanelProps = {
  kind: "gainers" | "persistence";
  rows: ThemeSummaryRow[];
  dataDate: string | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenAll: () => void;
  onRefreshTheme: () => void;
  refreshDisabled: boolean;
  title?: string;
  emptyMessage?: string;
  refreshLabel?: string;
};

function ThemeRankPanel({
  kind,
  rows,
  dataDate,
  loading,
  error,
  onRetry,
  onOpenTheme,
  onOpenAll,
  onRefreshTheme,
  refreshDisabled,
  title: titleOverride,
  emptyMessage,
  refreshLabel = "등락률&수급 갱신",
}: ThemeRankPanelProps) {
  const title = titleOverride ?? (kind === "gainers" ? "상승 테마 Top6" : "상승 지속 Top6");
  return (
    <article className="dashboard-v2-rank-panel">
      <div className="dashboard-v2-rank-head">
        <div><h4>{title}</h4><span>{dataDate ? `기준 ${dataDate}` : "최근 거래일 기준"}</span></div>
        <button type="button" className="dashboard-v2-text-button" onClick={onOpenAll}>전체 보기</button>
      </div>
      {loading ? (
        <div className="dashboard-v2-rank-skeleton" aria-label={`${title} 불러오는 중`}>
          {[0, 1, 2, 3, 4, 5].map((index) => <div key={index}><i /><span /><b /></div>)}
        </div>
      ) : error ? (
        <div className="dashboard-v2-rank-state error">
          <p>데이터를 불러오지 못했습니다.</p>
          <button type="button" className="btn btn-secondary" onClick={onRetry}>다시 시도</button>
        </div>
      ) : rows.length ? (
        <ol className="dashboard-v2-rank-list">
          {rows.map((row, index) => (
            <li key={`${kind}-${row.themeId}`}>
              <button type="button" onClick={() => onOpenTheme(row.themeId)} aria-label={`${row.themeName} 테마 상세 보기`} title={row.themeName}>
                <span className={`dashboard-v2-rank-badge ${index === 0 ? "first" : ""}`}>{index + 1}</span>
                <span className="dashboard-v2-rank-copy">
                  <strong title={row.themeName}>{row.themeName}</strong>
                  <small>
                    {kind === "gainers"
                      ? [row.themeGroupName, row.rolling30dReturn == null ? null : `30일 ${formatSignedPercent(row.rolling30dReturn)}`].filter(Boolean).join(" · ")
                      : row.positiveDays != null && row.observedDays != null ? `최근 ${row.observedDays}일 중 ${row.positiveDays}일 상승` : "기존 상승 지속 지표"}
                  </small>
                </span>
                <strong className={kind === "gainers" ? "dashboard-v2-return-value" : "dashboard-v2-persistence-value"}>
                  {kind === "gainers" ? formatSignedPercent(row.dailyReturn) : `${Math.round(Number(row.persistenceRate))}%`}
                </strong>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <div className="dashboard-v2-rank-state">
          <p>{emptyMessage ?? (kind === "gainers" ? "상승한 테마가 없습니다." : "상승 지속 데이터를 계산하기 위한 관측일수가 부족합니다.")}</p>
          {kind === "gainers" ? <button type="button" className="btn btn-secondary" onClick={onRefreshTheme} disabled={refreshDisabled}>{refreshLabel}</button> : null}
        </div>
      )}
    </article>
  );
}

function ReadinessSkeleton() {
  return (
    <article className="dashboard-v2-operation-card dashboard-v2-skeleton" aria-label="데이터 준비 상태 불러오는 중">
      <div className="dashboard-v2-skeleton-line dashboard-v2-skeleton-title" />
      <div className="dashboard-v2-skeleton-line" />
      <div className="dashboard-v2-skeleton-line" />
      <div className="dashboard-v2-skeleton-line dashboard-v2-skeleton-short" />
      <div className="dashboard-v2-skeleton-button" />
    </article>
  );
}

function DashboardPage() {
  const navigate = useNavigate();
  const [isDollarIndexHelpOpen, setIsDollarIndexHelpOpen] = useState(false);
  const [zoomedIndicator, setZoomedIndicator] = useState<{ url: string; alt: string } | null>(null);
  const [chartSidcode, setChartSidcode] = useState(() => createNaverChartSidcode());
  const [themeReadiness, setThemeReadiness] = useState<ThemeReadiness | null>(null);
  const [marketReadiness, setMarketReadiness] = useState<MarketReadiness | null>(null);
  const [themeError, setThemeError] = useState("");
  const [marketError, setMarketError] = useState("");
  const [themeFeedback, setThemeFeedback] = useState<ActionFeedback | null>(null);
  const [marketFeedback, setMarketFeedback] = useState<ActionFeedback | null>(null);
  const [isReadinessLoading, setIsReadinessLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isThemeRunning, setIsThemeRunning] = useState(false);
  const [isMarketRunning, setIsMarketRunning] = useState(false);
  const [themeSummary, setThemeSummary] = useState<ThemeSummaryData | null>(null);
  const [isThemeSummaryLoading, setIsThemeSummaryLoading] = useState(true);
  const [themeSummaryError, setThemeSummaryError] = useState("");
  const [usThemeSummary, setUsThemeSummary] = useState<UsThemeDashboardSummary | null>(null);
  const [isUsThemeSummaryLoading, setIsUsThemeSummaryLoading] = useState(true);
  const [usThemeError, setUsThemeError] = useState("");
  const [usThemeFeedback, setUsThemeFeedback] = useState<ActionFeedback | null>(null);
  const [isUsThemeRunning, setIsUsThemeRunning] = useState(false);
  const [marketSignals, setMarketSignals] = useState<MarketSignalSummaryRow[]>([]);
  const [isMarketSignalsLoading, setIsMarketSignalsLoading] = useState(true);
  const [marketSignalsError, setMarketSignalsError] = useState("");
  const [upcomingCalendar, setUpcomingCalendar] = useState<UpcomingCalendarData | null>(null);
  const [isUpcomingCalendarLoading, setIsUpcomingCalendarLoading] = useState(true);
  const [upcomingCalendarError, setUpcomingCalendarError] = useState("");
  const [observationSummary, setObservationSummary] = useState<MarketThemeObservationResponse | null>(null);
  const [isObservationLoading, setIsObservationLoading] = useState(true);
  const [observationError, setObservationError] = useState("");
  const [observationTargetDate, setObservationTargetDate] = useState("");
  const [observationCalculationOpen, setObservationCalculationOpen] = useState(false);
  const [isObservationCalculating, setIsObservationCalculating] = useState(false);
  const [observationCalculationError, setObservationCalculationError] = useState("");
  const [observationCalculationFeedback, setObservationCalculationFeedback] = useState("");
  const [themeDetailRequest, setThemeDetailRequest] = useState<{ themeId: number; dataDate: string | null } | null>(null);
  const themePollingTokenRef = useRef(0);

  const dashboardIndicators = useMemo<DashboardIndicator[]>(
    () => [
      { title: "코스피", category: "국내지수 · 90일", imageUrl: buildNaverKoreaMarketChartUrl("KOSPI", chartSidcode) },
      { title: "코스닥", category: "국내지수 · 90일", imageUrl: buildNaverKoreaMarketChartUrl("KOSDAQ", chartSidcode) },
      { title: "국제 금", category: "원자재 · 3개월", imageUrl: buildNaverMarketIndexAreaChartUrl("CMDT_GC", "month3", chartSidcode) },
      { title: "다우지수", category: "해외증시 · 3개월", imageUrl: buildNaverWorldIndexChartUrl("DJI@DJI", "month3", chartSidcode) },
      { title: "나스닥", category: "해외증시 · 3개월", imageUrl: buildNaverWorldIndexChartUrl("NAS@IXIC", "month3", chartSidcode) },
      { title: "S&P500", category: "해외증시 · 3개월", imageUrl: buildNaverWorldIndexChartUrl("SPI@SPX", "month3", chartSidcode) },
      { title: "달러 환율", category: "환율 · 3개월", imageUrl: buildNaverMarketIndexAreaChartUrl("FX_USDKRW", "month3", chartSidcode) },
      {
        title: "달러 인덱스",
        category: "환율·지수 · 3개월",
        imageUrl: buildNaverMarketIndexAreaChartUrl("FX_USDX", "month3", chartSidcode),
        helpType: "dollar-index",
      },
      { title: "WTI", category: "원자재 · 3개월", imageUrl: buildNaverMarketIndexAreaChartUrl("OIL_CL", "month3") },
    ],
    [chartSidcode],
  );

  const loadReadiness = useCallback(async (silent = false): Promise<string | null> => {
    let resolvedThemeDate: string | null = null;
    if (!silent) setIsReadinessLoading(true);
    const [themeResult, marketResult] = await Promise.allSettled([
      Promise.all([
        repositories.marketThemes.list({ is_active: 1, limit: 500, offset: 0 }),
        repositories.collectionRuns.listCollectionRuns({ collector_name: THEME_FLOW_COLLECTOR, limit: 10, offset: 0 }),
      ]),
      Promise.all([
        repositories.marketIndexes.list({ active_only: true }),
        repositories.marketIndicators.list({ active_only: true }),
        repositories.marketData.listRuns({ limit: 20 }),
      ]),
    ]);

    if (themeResult.status === "fulfilled") {
      const [themes, collectionRuns] = themeResult.value;
      const activeThemes = (themes as MarketTheme[]).filter((theme) => theme.is_active === 1 && theme.theme_level === "THEME");
      const latestRun = collectionRuns.items[0] as CollectionRun | undefined;
      const dataDate = maxDate(activeThemes.map((theme) => theme.latest_return?.return_date));
      resolvedThemeDate = dataDate;
      setThemeReadiness({
        dataDate,
        lastSuccessAt: maxTimestamp(activeThemes.map((theme) => theme.latest_return?.last_refreshed_at)),
        linkedStockCount: activeThemes.reduce((sum, theme) => sum + Number(theme.linked_stock_count ?? theme.stock_count ?? 0), 0),
        status: resolveReadinessStatus(dataDate, latestRun?.status),
      });
      setThemeError("");
    } else {
      setThemeError(errorMessage(themeResult.reason));
    }

    if (marketResult.status === "fulfilled") {
      const [indexes, indicators, runs] = marketResult.value;
      const activeIndexes = indexes.items.filter((item) => item.is_active);
      const activeIndicators = indicators.items.filter((item) => item.is_active);
      const latestRun = runs.items.find((run: MarketDataCollectionRun) => run.run_type === "INCREMENTAL_ALL") ?? runs.items[0];
      const dataDate = maxDate([
        ...activeIndexes.map((item) => item.latest_price_date),
        ...activeIndicators.map((item) => item.latest_value_date),
      ]);
      setMarketReadiness({
        dataDate,
        lastRunAt: latestRun?.finished_at ?? latestRun?.started_at ?? null,
        activeIndicatorCount: activeIndexes.length + activeIndicators.length,
        status: resolveReadinessStatus(dataDate, latestRun?.status),
      });
      setMarketError("");
    } else {
      setMarketError(errorMessage(marketResult.reason));
    }
    setIsReadinessLoading(false);
    return resolvedThemeDate;
  }, []);

  const loadThemeSummary = useCallback(async (dataDate?: string | null) => {
    setIsThemeSummaryLoading(true);
    setThemeSummaryError("");
    try {
      const response = await repositories.marketThemes.listRangeReturns({
        end_date: dataDate || todayInKst(),
        days: 30,
        active_only: true,
        sort_by: "CURRENT_STRENGTH",
      });
      setThemeSummary(buildThemeSummary(response));
    } catch (error) {
      setThemeSummaryError(errorMessage(error));
    } finally {
      setIsThemeSummaryLoading(false);
    }
  }, []);

  const loadUsThemeSummary = useCallback(async () => {
    setIsUsThemeSummaryLoading(true);
    setUsThemeError("");
    try {
      setUsThemeSummary(await repositories.usMarketThemes.dashboardSummary());
    } catch (error) {
      setUsThemeError(errorMessage(error));
    } finally {
      setIsUsThemeSummaryLoading(false);
    }
  }, []);

  const loadMarketSignals = useCallback(async () => {
    setIsMarketSignalsLoading(true);
    setMarketSignalsError("");
    try {
      const [transitionResult, currentResult] = await Promise.allSettled([
        repositories.marketSignals.todayTransitions(),
        repositories.marketSignals.currentStates(),
      ]);
      if (transitionResult.status === "rejected" && currentResult.status === "rejected") throw currentResult.reason;
      const todayTransitions = transitionResult.status === "fulfilled" ? transitionResult.value : { items: [] };
      const currentStates = currentResult.status === "fulfilled" ? currentResult.value : todayTransitions;
      const transitionsById = new Map(todayTransitions.items.map((item) => [item.definition_id, item]));
      const rows = currentStates.items
        .map((item): MarketSignalSummaryRow => ({
          ...item,
          ...(transitionsById.get(item.definition_id) ?? {}),
          isTodayTransition: transitionsById.has(item.definition_id),
        }))
        .filter((item) => !MAINTAINED_SIGNAL_STATES.has(item.current_state))
        .sort((a, b) =>
          Number(b.isTodayTransition) - Number(a.isTodayTransition)
          || (SIGNAL_SEVERITY[a.current_state] ?? 99) - (SIGNAL_SEVERITY[b.current_state] ?? 99)
          || String(b.last_transition_at ?? b.evaluated_at ?? "").localeCompare(String(a.last_transition_at ?? a.evaluated_at ?? ""))
          || String(a.title ?? "").localeCompare(String(b.title ?? ""), "ko-KR"))
        .slice(0, 5);
      setMarketSignals(rows);
    } catch (error) {
      setMarketSignalsError(errorMessage(error));
    } finally {
      setIsMarketSignalsLoading(false);
    }
  }, []);

  const loadUpcomingCalendar = useCallback(async () => {
    setIsUpcomingCalendarLoading(true);
    setUpcomingCalendarError("");
    try {
      const startDate = todayInKst();
      const endDate = shiftKstDate(startDate, 7);
      const months = Array.from(new Set([startDate.slice(0, 7), endDate.slice(0, 7)]));
      const responses = await Promise.all(months.map((month) => repositories.marketCalendar.listMonthly({ month })));
      const deduplicated = new Map<number, MarketCalendarEvent>();
      responses.flatMap((response) => response.events).forEach((event) => deduplicated.set(event.id, event));
      const events = Array.from(deduplicated.values())
        .filter((event) => event.is_active === 1 && event.period_type === "D" && event.start_date <= endDate && event.end_date >= startDate)
        .map((event) => ({ ...event, displayDate: event.start_date < startDate ? startDate : event.start_date }))
        .sort((a, b) =>
          a.displayDate.localeCompare(b.displayDate)
          || calendarImportanceOrder[a.importance] - calendarImportanceOrder[b.importance]
          || a.title.localeCompare(b.title, "ko-KR"));
      setUpcomingCalendar({ startDate, endDate, events });
    } catch (error) {
      setUpcomingCalendarError(errorMessage(error));
    } finally {
      setIsUpcomingCalendarLoading(false);
    }
  }, []);

  const loadObservationSummary = useCallback(async () => {
    setIsObservationLoading(true);
    setObservationError("");
    try {
      setObservationSummary(await repositories.marketThemes.getLatestObservationPriority());
    } catch (error) {
      setObservationError(errorMessage(error));
    } finally {
      setIsObservationLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const [dataDate] = await Promise.all([
        loadReadiness(),
        loadMarketSignals(),
        loadUpcomingCalendar(),
        loadObservationSummary(),
        loadUsThemeSummary(),
      ]);
      await loadThemeSummary(dataDate as string | null);
    })();
    return () => {
      themePollingTokenRef.current += 1;
    };
  }, [loadReadiness, loadThemeSummary, loadMarketSignals, loadUpcomingCalendar, loadObservationSummary, loadUsThemeSummary]);

  useEffect(() => {
    if (themeReadiness?.dataDate) setObservationTargetDate(shiftBusinessDay(themeReadiness.dataDate, 1));
  }, [themeReadiness?.dataDate]);

  useEffect(() => {
    if (!observationCalculationOpen || isObservationCalculating) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setObservationCalculationOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [isObservationCalculating, observationCalculationOpen]);

  const handleRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setChartSidcode(createNaverChartSidcode());
    const [dataDate] = await Promise.all([
      loadReadiness(true),
      loadMarketSignals(),
      loadUpcomingCalendar(),
      loadObservationSummary(),
      loadUsThemeSummary(),
    ]);
    await loadThemeSummary(dataDate as string | null);
    setIsRefreshing(false);
  };

  const handleThemeRefresh = async () => {
    if (isThemeRunning) return;
    const token = themePollingTokenRef.current + 1;
    themePollingTokenRef.current = token;
    setIsThemeRunning(true);
    setThemeError("");
    setThemeFeedback(null);
    setThemeReadiness((previous) => previous ? { ...previous, status: "RUNNING" } : previous);
    try {
      const started = await repositories.marketThemes.startPriceFlowRefresh({ scope: "all_active" });
      let job = await repositories.marketThemes.getPriceFlowRefreshJob(started.job_id);
      while ((job.status === "PENDING" || job.status === "RUNNING") && themePollingTokenRef.current === token) {
        await wait(1000);
        job = await repositories.marketThemes.getPriceFlowRefreshJob(started.job_id);
      }
      if (themePollingTokenRef.current !== token) return;
      if (job.status === "FAILED" || !job.result) throw new Error(job.error || job.message || "등락률·수급 갱신에 실패했습니다.");
      const result = job.result as MarketThemeReturnRefreshResponse;
      const failedCount = Number(result.failed_stock_count ?? result.price_failed_count ?? 0);
      setThemeFeedback({
        tone: job.status === "PARTIAL" || failedCount > 0 ? "warning" : "success",
        message: `${result.theme_count.toLocaleString()}개 테마 · ${Number(result.unique_stock_count ?? result.stock_count).toLocaleString()}개 종목 처리 · 저장 ${Number(result.inserted_count + result.updated_count).toLocaleString()}건${failedCount ? ` · 실패 ${failedCount.toLocaleString()}건` : ""}`,
      });
      const dataDate = await loadReadiness(true);
      await loadThemeSummary(dataDate ?? result.return_date);
    } catch (error) {
      const message = errorMessage(error);
      setThemeError(message);
      setThemeFeedback({ tone: "error", message });
      setThemeReadiness((previous) => previous ? { ...previous, status: "FAILED" } : previous);
    } finally {
      if (themePollingTokenRef.current === token) setIsThemeRunning(false);
    }
  };

  const handleMarketRefresh = async () => {
    if (isMarketRunning) return;
    setIsMarketRunning(true);
    setMarketError("");
    setMarketFeedback(null);
    setMarketReadiness((previous) => previous ? { ...previous, status: "RUNNING" } : previous);
    try {
      const result = await repositories.marketData.collect({ mode: "INCREMENTAL_ALL", triggered_by: "DASHBOARD" });
      const signals = result.signal_evaluation;
      const partial = result.failed_count > 0 || result.status.toUpperCase().includes("PARTIAL");
      setMarketFeedback({
        tone: partial ? "warning" : "success",
        message: `${result.success_count.toLocaleString()}/${result.target_count.toLocaleString()}개 지표 완료 · 저장 ${Number(result.inserted_count + result.updated_count).toLocaleString()}건${signals ? ` · 신호 ${signals.evaluated_count.toLocaleString()}건 평가, 전환 ${signals.transition_count.toLocaleString()}건` : ""}${result.failed_count ? ` · 실패 ${result.failed_count.toLocaleString()}건` : ""}`,
      });
      await Promise.all([loadReadiness(true), loadMarketSignals()]);
    } catch (error) {
      const message = errorMessage(error);
      setMarketError(message);
      setMarketFeedback({ tone: "error", message });
      setMarketReadiness((previous) => previous ? { ...previous, status: "FAILED" } : previous);
    } finally {
      setIsMarketRunning(false);
    }
  };

  const handleUsThemeRefresh = async () => {
    if (isUsThemeRunning) return;
    setIsUsThemeRunning(true);
    setUsThemeFeedback(null);
    setUsThemeError("");
    try {
      const result = await repositories.usMarketThemes.refresh();
      const failedCount = Number(result.price.failed_stock_count ?? 0);
      setUsThemeFeedback({
        tone: failedCount > 0 ? "warning" : "success",
        message: `${result.price.success_stock_count.toLocaleString()}/${result.price.requested_stock_count.toLocaleString()}개 종목 · ${result.returns.processed_theme_count.toLocaleString()}개 테마 처리${failedCount ? ` · 실패 ${failedCount.toLocaleString()}건` : ""}`,
      });
      await loadUsThemeSummary();
    } catch (error) {
      const message = errorMessage(error);
      setUsThemeError(message);
      setUsThemeFeedback({ tone: "error", message });
    } finally {
      setIsUsThemeRunning(false);
    }
  };

  const observationTargetDateError = () => {
    if (!observationTargetDate) return "관찰 대상일을 선택해 주세요.";
    const day = new Date(`${observationTargetDate}T00:00:00`).getDay();
    if (day === 0 || day === 6) return "관찰 대상일은 평일이어야 합니다.";
    if (themeReadiness?.dataDate && observationTargetDate <= themeReadiness.dataDate) {
      return "관찰 대상일은 데이터 기준일 이후의 평일이어야 합니다.";
    }
    return "";
  };

  const prepareObservationCalculation = () => {
    const message = observationTargetDateError();
    setObservationCalculationError(message);
    setObservationCalculationFeedback("");
    if (!message) setObservationCalculationOpen(true);
  };

  const handleObservationCalculation = async (refreshMarketIndicators: boolean) => {
    const validationError = observationTargetDateError();
    if (validationError || isObservationCalculating) {
      setObservationCalculationError(validationError);
      return;
    }
    setObservationCalculationError("");
    setObservationCalculationFeedback("");
    setIsObservationCalculating(true);
    try {
      const result = await repositories.marketThemes.calculateObservationPriority(observationTargetDate, refreshMarketIndicators);
      setObservationCalculationFeedback(`${result.run?.target_date ?? observationTargetDate} 관찰순위 계산 완료`);
      setObservationCalculationOpen(false);
      await loadObservationSummary();
    } catch (error) {
      setObservationCalculationError(errorMessage(error));
    } finally {
      setIsObservationCalculating(false);
    }
  };

  const themeStatus = statusPresentation[isThemeRunning ? "RUNNING" : (themeReadiness?.status ?? "STALE")];
  const marketStatus = statusPresentation[isMarketRunning ? "RUNNING" : (marketReadiness?.status ?? "STALE")];
  const usReadinessStatus = resolveReadinessStatus(usThemeSummary?.latest_date ?? null, null, latestExpectedUsTradingDate());
  const usStatus = statusPresentation[isUsThemeRunning ? "RUNNING" : usReadinessStatus];
  const usStrengthRows: ThemeSummaryRow[] = (usThemeSummary?.top_strength ?? []).map((row) => ({
    themeId: row.theme_id, themeName: row.theme_name, themeGroupName: row.theme_group_name,
    dailyReturn: row.theme_strength, rolling30dReturn: row.rolling_30d_return,
    persistenceRate: row.persistence_rate, positiveDays: row.positive_days, observedDays: row.observed_days,
  }));
  const usPersistenceRows: ThemeSummaryRow[] = (usThemeSummary?.top_persistence ?? []).map((row) => ({
    themeId: row.theme_id, themeName: row.theme_name, themeGroupName: row.theme_group_name,
    dailyReturn: row.theme_strength, rolling30dReturn: row.rolling_30d_return,
    persistenceRate: row.persistence_rate, positiveDays: row.positive_days, observedDays: row.observed_days,
  }));

  return (
    <div className="space-y-4 dashboard-v2">
      <PageHeader
        title="DrCT 대시보드"
        description="시장 흐름과 오늘의 데이터 준비 상태를 확인합니다."
        action={(
          <div className="dashboard-v2-header-actions">
            <StatusBadge label={`기준일 ${todayInKst()}`} tone="slate" />
            <button type="button" className="btn btn-secondary" onClick={() => void handleRefresh()} disabled={isRefreshing}>
              {isRefreshing ? <span className="dashboard-v2-spinner" aria-hidden="true" /> : null}
              {isRefreshing ? "새로고침 중" : "새로고침"}
            </button>
          </div>
        )}
      />

      <SectionCard className="dashboard-v2-indicator-section">
        <div className="dashboard-v2-section-heading dashboard-v2-indicator-heading">
          <div>
            <h3 className="section-title">주요 지표 흐름</h3>
            <p>국내지수, 해외증시, 환율·원자재 흐름을 네이버 차트 기준으로 빠르게 확인합니다.</p>
          </div>
        </div>
        <div className="dashboard-indicator-panel">
          <div className="dashboard-indicator-grid">
            {dashboardIndicators.map((indicator) => (
              <article key={indicator.title} className="dashboard-indicator-card">
                <div className="dashboard-indicator-card-title">
                  <div><strong>{indicator.title}</strong><span>{indicator.category}</span></div>
                  {indicator.helpType === "dollar-index" ? (
                    <button type="button" className="dashboard-indicator-help-button" aria-label="달러 인덱스 설명 보기" onClick={() => setIsDollarIndexHelpOpen(true)}>?</button>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="dashboard-indicator-chart-button"
                  onClick={() => setZoomedIndicator({ url: indicator.imageUrl, alt: `${indicator.title} 흐름 차트` })}
                  aria-label={`${indicator.title} 차트 크게 보기`}
                >
                  <img src={indicator.imageUrl} alt={`${indicator.title} 흐름 차트`} className="dashboard-indicator-chart" loading="lazy" />
                </button>
              </article>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard className="dashboard-v2-readiness-section">
        <div className="dashboard-v2-section-heading">
          <div>
            <h3 className="section-title">오늘의 데이터 준비</h3>
            <p>대시보드 분석에 필요한 핵심 데이터의 최신 상태를 확인하고 바로 갱신합니다.</p>
          </div>
          <span>최신 거래일 기준 {latestExpectedTradingDate()}</span>
        </div>

        <div className="dashboard-v2-operation-grid">
          {isReadinessLoading && !themeReadiness ? <ReadinessSkeleton /> : (
            <article className={`dashboard-v2-operation-card dashboard-v2-status-${themeReadiness?.status.toLowerCase() ?? "stale"}`}>
              <div className="dashboard-v2-operation-head">
                <div><span className="dashboard-v2-operation-eyebrow">시장 테마</span><h4>테마 등락률·수급</h4></div>
                <StatusBadge label={themeStatus.label} tone={themeStatus.tone} />
              </div>
              <dl className="dashboard-v2-metrics dashboard-v2-card-metrics">
                <div><dt>데이터 기준일</dt><dd>{formatDate(themeReadiness?.dataDate ?? null)}</dd></div>
                <div><dt>연결 종목</dt><dd>{(themeReadiness?.linkedStockCount ?? 0).toLocaleString()}개</dd></div>
                <div className="dashboard-v2-metric-wide"><dt>최근 성공</dt><dd>{formatDateTime(themeReadiness?.lastSuccessAt ?? null)}</dd></div>
              </dl>
              <div className="dashboard-v2-operation-footer">
              {!themeFeedback && !themeError ? <p className="dashboard-v2-operation-summary">최근 {(themeReadiness?.linkedStockCount ?? 0).toLocaleString()}종목 처리 상태 확인</p> : null}
              {themeFeedback ? <p className={`dashboard-v2-feedback ${themeFeedback.tone}`}>{themeFeedback.message}</p> : null}
              {!themeFeedback && themeError ? <p className="dashboard-v2-feedback error">상태 조회 실패: {themeError}</p> : null}
              <button type="button" className="btn btn-primary dashboard-v2-action-button" onClick={() => void handleThemeRefresh()} disabled={isThemeRunning}>
                {isThemeRunning ? <span className="dashboard-v2-spinner" aria-hidden="true" /> : null}
                {isThemeRunning ? "등락률·수급 갱신 중" : "등락률&수급 갱신"}
              </button>
              </div>
            </article>
          )}

          {isUsThemeSummaryLoading && !usThemeSummary ? <ReadinessSkeleton /> : (
            <article className={`dashboard-v2-operation-card dashboard-v2-status-${(isUsThemeRunning ? "running" : usReadinessStatus.toLowerCase())}`}>
              <div className="dashboard-v2-operation-head">
                <div><span className="dashboard-v2-operation-eyebrow">미국 테마</span><h4>미국 종가 · 테마</h4></div>
                <StatusBadge label={usStatus.label} tone={usStatus.tone} />
              </div>
              <dl className="dashboard-v2-metrics dashboard-v2-card-metrics">
                <div><dt>최신 미국 데이터</dt><dd>{formatDate(usThemeSummary?.latest_date ?? null)}</dd></div>
                <div><dt>활성 테마</dt><dd>{(usThemeSummary?.active_theme_count ?? 0).toLocaleString()}개</dd></div>
                <div className="dashboard-v2-metric-wide"><dt>최근 성공</dt><dd>{formatDateTime(usThemeSummary?.latest_refreshed_at ?? null)}</dd></div>
              </dl>
              <div className="dashboard-v2-operation-footer">
                {!usThemeFeedback && !usThemeError ? <p className="dashboard-v2-operation-summary">기존 미국 가격·테마 갱신 흐름을 실행합니다.</p> : null}
                {usThemeFeedback ? <p className={`dashboard-v2-feedback ${usThemeFeedback.tone}`}>{usThemeFeedback.message}</p> : null}
                {!usThemeFeedback && usThemeError ? <p className="dashboard-v2-feedback error">상태 조회 실패: {usThemeError}</p> : null}
                <button type="button" className="btn btn-primary dashboard-v2-action-button" onClick={() => void handleUsThemeRefresh()} disabled={isUsThemeRunning}>
                  {isUsThemeRunning ? <span className="dashboard-v2-spinner" aria-hidden="true" /> : null}
                  {isUsThemeRunning ? "미국 테마 갱신 중" : "미국종가·테마 갱신"}
                </button>
              </div>
            </article>
          )}

          {isReadinessLoading && !marketReadiness ? <ReadinessSkeleton /> : (
            <article className={`dashboard-v2-operation-card dashboard-v2-status-${marketReadiness?.status.toLowerCase() ?? "stale"}`}>
              <div className="dashboard-v2-operation-head">
                <div><span className="dashboard-v2-operation-eyebrow">시장 지표</span><h4>시장지표·신호</h4></div>
                <StatusBadge label={marketStatus.label} tone={marketStatus.tone} />
              </div>
              <dl className="dashboard-v2-metrics dashboard-v2-card-metrics">
                <div><dt>데이터 기준일</dt><dd>{formatDate(marketReadiness?.dataDate ?? null)}</dd></div>
                <div><dt>활성 지표</dt><dd>{(marketReadiness?.activeIndicatorCount ?? 0).toLocaleString()}개</dd></div>
                <div className="dashboard-v2-metric-wide"><dt>최근 전체 증분</dt><dd>{formatDateTime(marketReadiness?.lastRunAt ?? null)}</dd></div>
              </dl>
              <div className="dashboard-v2-operation-footer">
              {!marketFeedback && !marketError ? <p className="dashboard-v2-operation-summary">활성 {(marketReadiness?.activeIndicatorCount ?? 0).toLocaleString()}개 지표 상태 확인</p> : null}
              {marketFeedback ? <p className={`dashboard-v2-feedback ${marketFeedback.tone}`}>{marketFeedback.message}</p> : null}
              {!marketFeedback && marketError ? <p className="dashboard-v2-feedback error">상태 조회 실패: {marketError}</p> : null}
              <button type="button" className="btn btn-primary dashboard-v2-action-button" onClick={() => void handleMarketRefresh()} disabled={isMarketRunning}>
                {isMarketRunning ? <span className="dashboard-v2-spinner" aria-hidden="true" /> : null}
                {isMarketRunning ? "전체 증분 갱신 중" : "전체 증분 갱신"}
              </button>
              </div>
            </article>
          )}

          <article className="dashboard-v2-operation-card dashboard-v2-status-fresh dashboard-v2-observation-action-card">
            <div className="dashboard-v2-operation-head">
              <div><span className="dashboard-v2-operation-eyebrow">테마 관찰</span><h4>테마 관찰순위</h4></div>
              <StatusBadge label="D+1" tone="blue" />
            </div>
            <div className="dashboard-v2-observation-action-row">
              <label className="dashboard-v2-observation-date">
                <span>관찰 대상일</span>
                <input
                  type="date"
                  className="input-control"
                  value={observationTargetDate}
                  onChange={(event) => {
                    setObservationTargetDate(event.target.value);
                    setObservationCalculationError("");
                    setObservationCalculationFeedback("");
                  }}
                />
              </label>
              <button type="button" className="btn btn-primary dashboard-v2-action-button dashboard-v2-observation-calculate" onClick={prepareObservationCalculation} disabled={isObservationCalculating || !observationTargetDate}>
                {isObservationCalculating ? <span className="dashboard-v2-spinner" aria-hidden="true" /> : null}
                {isObservationCalculating ? "관찰순위 계산 중..." : "관찰순위 계산"}
              </button>
            </div>
            {observationCalculationFeedback ? <p className="dashboard-v2-feedback success dashboard-v2-observation-feedback">{observationCalculationFeedback}</p> : null}
            {observationCalculationError ? <p className="dashboard-v2-feedback error dashboard-v2-observation-feedback">{observationCalculationError}</p> : null}
          </article>

          <article className="dashboard-v2-operation-card dashboard-v2-status-fresh dashboard-v2-navigation-card">
            <div className="dashboard-v2-operation-head">
              <div><span className="dashboard-v2-operation-eyebrow">시장 수급</span><h4>테마 · 종목</h4></div>
              <StatusBadge label="분석" tone="slate" />
            </div>
            <p className="dashboard-v2-operation-summary">시장 수급 테마와 연결 종목의 흐름을 확인합니다.</p>
            <div className="dashboard-v2-operation-footer">
              <button type="button" className="btn btn-secondary dashboard-v2-action-button" onClick={() => navigate("/market-trends")}>수급 분석 보기 →</button>
            </div>
          </article>

          <article className="dashboard-v2-operation-card dashboard-v2-status-stale dashboard-v2-extension-card">
            <div className="dashboard-v2-operation-head">
              <div><span className="dashboard-v2-operation-eyebrow">향후 확장</span><h4>데이터 슬롯</h4></div>
              <StatusBadge label="준비 중" tone="slate" />
            </div>
            <p className="dashboard-v2-operation-summary">추가 분석 데이터 연결을 위한 확장 공간입니다.</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard className="dashboard-v3-market-check-section">
        <div className="dashboard-v2-section-heading dashboard-v3-market-check-heading">
          <div>
            <h3 className="section-title">시장 : 오늘의 시장 체크</h3>
            <p>시장 변화 신호와 앞으로 예정된 주요 일정을 확인합니다.</p>
          </div>
        </div>
        <div className="dashboard-v3-market-check-grid">
          <article className="dashboard-v3-check-panel">
            <header>
              <div><h4>시장 변화 신호</h4><p>추세 유지 상태를 제외한 현재 신호입니다.</p></div>
              <button type="button" className="dashboard-v2-text-button" onClick={() => navigate("/market-indexes/signals")}>전체 보기</button>
            </header>
            {isMarketSignalsLoading ? (
              <div className="dashboard-v3-list-skeleton" aria-label="시장 변화 신호 불러오는 중">{[0, 1, 2].map((index) => <i key={index} />)}</div>
            ) : marketSignalsError ? (
              <div className="dashboard-v3-panel-state error"><p>신호를 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={() => void loadMarketSignals()}>다시 시도</button></div>
            ) : marketSignals.length ? (
              <div className="dashboard-v3-signal-list">
                {marketSignals.map((signal) => (
                  <button key={signal.definition_id} type="button" onClick={() => navigate(`/market-indexes/signals?signal=${signal.definition_id}`)} aria-label={`${signal.title || signal.signal_code || "시장 신호"} 신호 상세 보기`}>
                    <span className={`dashboard-v3-signal-icon ${signalTone(signal.current_state)}`} aria-hidden="true" />
                    <span className="dashboard-v3-signal-copy">
                      <strong>{signal.title || signal.signal_code || "시장 신호"}</strong>
                      <small>{signal.missing_reason || signal.explanation || `기준 ${signal.effective_date || "확인 중"}`}</small>
                    </span>
                    <span className={`dashboard-v3-state-badge ${signalTone(signal.current_state)}`}>{signal.isTodayTransition ? "오늘 전환 · " : ""}{SIGNAL_STATE_LABELS[signal.current_state] || signal.current_state}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="dashboard-v3-panel-state"><p>현재 확인이 필요한 시장 변화 신호가 없습니다.</p></div>
            )}
          </article>

          <article className="dashboard-v3-check-panel">
            <header>
              <div><h4>향후 7일 증시 일정</h4><p>{upcomingCalendar ? `${upcomingCalendar.startDate} ~ ${upcomingCalendar.endDate}` : "KST 오늘부터 7일 후까지"}</p></div>
              <button type="button" className="dashboard-v2-text-button" onClick={() => navigate("/market-calendar")}>전체 보기</button>
            </header>
            {isUpcomingCalendarLoading ? (
              <div className="dashboard-v3-list-skeleton" aria-label="증시 일정 불러오는 중">{[0, 1, 2].map((index) => <i key={index} />)}</div>
            ) : upcomingCalendarError ? (
              <div className="dashboard-v3-panel-state error"><p>일정을 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={() => void loadUpcomingCalendar()}>다시 시도</button></div>
            ) : upcomingCalendar?.events.length ? (
              <div className="dashboard-v3-calendar-list">
                {Array.from(new Set(upcomingCalendar.events.slice(0, 8).map((event) => event.displayDate))).map((date) => (
                  <section key={date}>
                    <div className="dashboard-v3-calendar-date">
                      <strong>{formatCalendarDate(date)}</strong>
                      {date === upcomingCalendar.startDate ? <span>오늘</span> : null}
                      {date === shiftKstDate(upcomingCalendar.startDate, 1) ? <span>내일</span> : null}
                    </div>
                    <div>
                      {upcomingCalendar.events.slice(0, 8).filter((event) => event.displayDate === date).map((event) => (
                        <button key={event.id} type="button" onClick={() => navigate("/market-calendar")} aria-label={`${formatCalendarDate(date)} ${event.title} 증시 일정 상세 보기`}>
                          <span className={`dashboard-v3-importance ${event.importance}`}>{calendarImportanceLabel[event.importance]}</span>
                          <span><strong>{event.title}</strong><small>{[event.theme_name, event.start_date !== event.end_date ? `${event.start_date} ~ ${event.end_date}` : null].filter(Boolean).join(" · ")}</small></span>
                        </button>
                      ))}
                    </div>
                  </section>
                ))}
                {upcomingCalendar.events.length > 8 ? <button type="button" className="dashboard-v3-more-button" onClick={() => navigate("/market-calendar")}>+{upcomingCalendar.events.length - 8}개 더 있음</button> : null}
              </div>
            ) : (
              <div className="dashboard-v3-panel-state"><p>향후 7일 내 등록된 증시 일정이 없습니다.</p><button type="button" className="btn btn-secondary" onClick={() => navigate("/market-calendar")}>일정 관리</button></div>
            )}
          </article>
        </div>
      </SectionCard>

      <SectionCard className="dashboard-v2-theme-summary-section">
        <div className="dashboard-v2-section-heading dashboard-v2-theme-summary-heading">
          <div>
            <h3 className="section-title">테마 : 미국 테마 강도 순위</h3>
            <p>전일 미국 시장의 테마 강도와 최근 10개 관측일의 상승 지속 흐름을 확인합니다.</p>
          </div>
          <span>{usThemeSummary?.latest_date ? `미국 데이터 기준일 ${usThemeSummary.latest_date}` : "미국 데이터 기준일 확인 중"}</span>
        </div>
        <div className="dashboard-v2-rank-grid">
          <ThemeRankPanel
            kind="gainers" title="미국 테마 강도 Top6" rows={usStrengthRows}
            dataDate={usThemeSummary?.latest_date ?? null} loading={isUsThemeSummaryLoading} error={usThemeError}
            onRetry={() => void loadUsThemeSummary()} onOpenTheme={() => navigate("/market-themes")}
            onOpenAll={() => navigate("/market-themes")} onRefreshTheme={() => void handleUsThemeRefresh()}
            refreshDisabled={isUsThemeRunning} refreshLabel="미국종가·테마 갱신"
            emptyMessage="최근 미국 테마 데이터가 없습니다. 오늘의 데이터 준비에서 미국종가·테마 갱신을 실행해 주세요."
          />
          <ThemeRankPanel
            kind="persistence" title="미국 상승 지속 Top6" rows={usPersistenceRows}
            dataDate={usThemeSummary?.latest_date ?? null} loading={isUsThemeSummaryLoading} error={usThemeError}
            onRetry={() => void loadUsThemeSummary()} onOpenTheme={() => navigate("/market-themes")}
            onOpenAll={() => navigate("/market-themes")} onRefreshTheme={() => void handleUsThemeRefresh()}
            refreshDisabled={isUsThemeRunning}
            emptyMessage="최근 미국 테마 데이터가 없습니다. 오늘의 데이터 준비에서 미국종가·테마 갱신을 실행해 주세요."
          />
        </div>
      </SectionCard>

      <SectionCard className="dashboard-v2-theme-summary-section">
        <div className="dashboard-v2-section-heading dashboard-v2-theme-summary-heading">
          <div>
            <h3 className="section-title">테마/종목 : 국내 테마 강도 순위</h3>
            <p>최신 거래일의 상승 강도와 최근 10일 상승 지속 강도를 확인합니다.</p>
          </div>
          <span>{themeSummary?.dataDate ? `국내 데이터 기준일 ${themeSummary.dataDate}` : "국내 데이터 기준일 확인 중"}</span>
        </div>
        <div className="dashboard-v2-rank-grid">
          <ThemeRankPanel
            kind="gainers" rows={themeSummary?.topGainers ?? []} dataDate={themeSummary?.dataDate ?? themeReadiness?.dataDate ?? null}
            loading={isThemeSummaryLoading} error={themeSummaryError} onRetry={() => void loadThemeSummary(themeReadiness?.dataDate)}
            onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: themeSummary?.dataDate ?? themeReadiness?.dataDate ?? null })}
            onOpenAll={() => navigate("/market-themes")} onRefreshTheme={() => void handleThemeRefresh()} refreshDisabled={isThemeRunning}
          />
          <ThemeRankPanel
            kind="persistence" rows={themeSummary?.topPersistence ?? []} dataDate={themeSummary?.dataDate ?? themeReadiness?.dataDate ?? null}
            loading={isThemeSummaryLoading} error={themeSummaryError} onRetry={() => void loadThemeSummary(themeReadiness?.dataDate)}
            onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: themeSummary?.dataDate ?? themeReadiness?.dataDate ?? null })}
            onOpenAll={() => navigate("/market-themes")} onRefreshTheme={() => void handleThemeRefresh()} refreshDisabled={isThemeRunning}
          />
        </div>
      </SectionCard>

      <SectionCard className="dashboard-v4-observation-section">
        <div className="dashboard-v2-section-heading dashboard-v4-section-heading">
          <div>
            <h3 className="section-title">테마/종목 : 오늘의 국내 테마 관찰 순위</h3>
            <p>오늘 우선 관찰할 국내 테마와 구조적 강도를 확인합니다.</p>
          </div>
        </div>
        <div className="dashboard-v4-grid">
          <article className="dashboard-v4-panel">
            <header>
              <div><h4>테마 관찰우선순위</h4><p>저장된 최신 관찰 결과 Top4</p></div>
              {observationSummary?.run ? <span>{observationDateLabel(observationSummary.run.target_date)}</span> : null}
            </header>
            {isObservationLoading ? (
              <div className="dashboard-v4-radar-skeleton" aria-label="관찰우선순위 불러오는 중">{[0, 1, 2, 3].map((index) => <i key={index} />)}</div>
            ) : observationError ? (
              <div className="dashboard-v4-state error"><p>관찰우선순위를 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={() => void loadObservationSummary()}>다시 시도</button></div>
            ) : observationSummary?.run && observationSummary.items.length ? (
              <div className="dashboard-v4-radar-wrap">
                <ObservationRadarGrid
                  items={observationSummary.items.slice(0, 4)}
                  statusNames={OBSERVATION_STATE_LABELS}
                  onThemeClick={(themeId) => navigate(`/market-themes?view=prediction&target_date=${observationSummary.run!.target_date}&theme_id=${themeId}`)}
                />
                <button type="button" className="dashboard-v4-footer-button" onClick={() => navigate("/market-themes?view=prediction")}>전체 관찰순위 보기</button>
              </div>
            ) : (
              <div className="dashboard-v4-state"><p>저장된 관찰우선순위 결과가 없습니다.</p><button type="button" className="btn btn-secondary" onClick={() => navigate("/market-themes?view=prediction")}>관찰순위 화면으로 이동</button></div>
            )}
          </article>
        </div>
      </SectionCard>

      <MarketThemeDetailDrawer
        open={Boolean(themeDetailRequest)}
        themeId={themeDetailRequest?.themeId ?? null}
        dataDate={themeDetailRequest?.dataDate}
        onClose={() => setThemeDetailRequest(null)}
      />

      {observationCalculationOpen ? (
        <div className="theme-observation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !isObservationCalculating) setObservationCalculationOpen(false); }}>
          <section className="theme-observation-modal" role="dialog" aria-modal="true" aria-labelledby="dashboard-market-refresh-choice-title">
            <header>
              <div><small>관찰순위 계산</small><h3 id="dashboard-market-refresh-choice-title">시장지표를 갱신하고 계산할까요?</h3></div>
              <button type="button" aria-label="닫기" disabled={isObservationCalculating} onClick={() => setObservationCalculationOpen(false)}>×</button>
            </header>
            <p>직전 관찰결과를 최신 실측으로 먼저 검증한 뒤 D+1 관찰순위를 계산합니다. 최신 시장환경 반영 여부를 선택해 주세요.</p>
            <dl>
              <dt>현재 시장지표 최근 갱신</dt><dd>{formatDateTime(observationSummary?.market_indicator_latest_refreshed_at ?? null)}</dd>
              <dt>테마·종목 기준일</dt><dd>{themeReadiness?.dataDate ?? "-"}</dd>
              <dt>관찰 대상일</dt><dd>{observationTargetDate}</dd>
            </dl>
            {isObservationCalculating ? <div className="theme-observation-modal-progress" role="status">최근 관찰결과 검증과 D+1 관찰순위 계산을 진행하고 있습니다...</div> : null}
            <div className="theme-observation-modal-actions">
              <button className="btn btn-secondary" type="button" disabled={isObservationCalculating} onClick={() => void handleObservationCalculation(false)}>현재 지표로 계산</button>
              <button className="btn btn-primary" type="button" disabled={isObservationCalculating} onClick={() => void handleObservationCalculation(true)}>전체지표 갱신 후 계산<small>시장지표 전체갱신 후 관찰순위를 계산합니다.</small></button>
            </div>
          </section>
        </div>
      ) : null}

      {zoomedIndicator ? (
        <div className="dashboard-chart-zoom-modal" onClick={() => setZoomedIndicator(null)} role="presentation">
          <img src={zoomedIndicator.url} alt={zoomedIndicator.alt} className="dashboard-chart-zoom-image" />
        </div>
      ) : null}
      {isDollarIndexHelpOpen ? (
        <div className="dashboard-indicator-modal" role="presentation" onClick={() => setIsDollarIndexHelpOpen(false)}>
          <div className="dashboard-indicator-modal-panel" role="dialog" aria-modal="true" aria-labelledby="dollar-index-help-title" onClick={(event) => event.stopPropagation()}>
            <div className="dashboard-indicator-modal-header">
              <div><h3 id="dollar-index-help-title">달러 인덱스 설명</h3><p>네이버 블로그 자료를 참고해 달러 인덱스 의미와 흐름을 확인합니다.</p></div>
              <button type="button" className="btn btn-secondary" onClick={() => setIsDollarIndexHelpOpen(false)}>닫기</button>
            </div>
            <iframe title="달러 인덱스 설명" src={DOLLAR_INDEX_HELP_URL} className="dashboard-indicator-modal-frame" />
            <a className="dashboard-indicator-modal-link" href={DOLLAR_INDEX_HELP_URL} target="_blank" rel="noreferrer">새 창에서 보기</a>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default DashboardPage;
