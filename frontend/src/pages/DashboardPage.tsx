import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import MarketThemeDetailDrawer from "@/components/marketThemes/MarketThemeDetailDrawer";
import RealtimeThemeDetailDrawer from "@/components/marketThemes/RealtimeThemeDetailDrawer";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";
import { InsightDrawer, type DrawerTab, type IntradayView } from "@/pages/DrctInsightPage";
import { repositories } from "@/services";
import {
  ensureRealtimeThemeSnapshot,
  getRealtimeThemeSchedulerState,
  refreshRealtimeTheme,
  setRealtimeThemeSuspended,
  subscribeRealtimeThemeScheduler,
} from "@/services/realtimeThemeScheduler";
import type { MarketCalendarEvent, MarketCalendarImportance } from "@/types/marketCalendar";
import type { UsThemeDashboardSummary } from "@/types/usMarketTheme";
import type { UsKrTodayObservation, UsKrTodayObservationItem } from "@/types/usKrThemeLink";
import type { DrctInsightPerformance, DrctInsightStock, DrctInsightToday, DrctIntradayFocusSignal } from "@/types/drctInsight";
import type { NewsItem } from "@/types/news";
import type { TelegramItem } from "@/types/telegram";
import type { Disclosure } from "@/types/disclosure";
import type { DailyThemeFlowResponse } from "@/types/marketTrend";
import type {
  MarketThemeObservationResponse,
  MarketThemeMonthlyReturnResponse,
  MarketThemeMonthlyReturnThemeItem,
  MarketThemeReturnRefreshResponse,
  RealtimeThemeStocksResponse,
} from "@/types/marketTheme";
import {
  buildNaverKoreaMarketChartUrl,
  buildNaverMarketIndexAreaChartUrl,
  buildNaverWorldIndexChartUrl,
  createNaverChartSidcode,
} from "@/utils/naverChart";
import {
  marketSignalStateLabel,
  marketSignalTone,
  selectMeaningfulMarketSignals,
  type MarketSignalChangeItem,
} from "@/utils/marketSignalChange";

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

type DashboardStage = "plan" | "verify" | "review";

type UpcomingCalendarData = {
  startDate: string;
  endDate: string;
  events: Array<MarketCalendarEvent & { displayDate: string }>;
};

type ReviewBriefing = {
  news: NewsItem[];
  newsTotal: number | null;
  telegram: TelegramItem[];
  telegramTotal: number | null;
  disclosures: Disclosure[];
};

const DOLLAR_INDEX_HELP_URL = "https://blog.naver.com/annalife_/224280737671?photoView=3";
const stageMeta: Record<DashboardStage, { number: string; kicker: string; title: string; question: string; description: string }> = {
  plan: { number: "01", kicker: "장전", title: "PLAN", question: "오늘 어디를 볼 것인가?", description: "전일 미국시장과 국내 시장환경을 확인하고 오늘 우선 관찰할 테마와 종목을 정합니다." },
  verify: { number: "02", kicker: "장중", title: "VERIFY", question: "예상한 곳에 실제 돈이 들어오는가?", description: "장전 집중테마와 현재 시장의 실시간 강세를 비교하여 가설을 검증합니다." },
  review: { number: "03", kicker: "장후", title: "REVIEW", question: "예상과 실제는 어떻게 달랐는가?", description: "오늘 시장에서 실제로 강했던 테마와 수급·뉴스·지표·후보성과를 확인합니다." },
};

const resolveDefaultStage = (): DashboardStage => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  if (values.weekday === "Sat" || values.weekday === "Sun") return "review";
  const minutes = Number(values.hour) * 60 + Number(values.minute);
  if (minutes < 9 * 60) return "plan";
  if (minutes < 15 * 60 + 30) return "verify";
  return "review";
};

const defaultDashboardStage = (): DashboardStage => {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Seoul", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  if (values.weekday === "Sat" || values.weekday === "Sun") return "review";
  const minutes = Number(values.hour) * 60 + Number(values.minute);
  if (minutes < 9 * 60) return "plan";
  if (minutes < 15 * 60 + 30) return "verify";
  return "review";
};

const todayInKst = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());

const formatMarketSignalEvaluationDate = (value: string | null) => {
  if (!value) return "미평가";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "미평가";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(date);
};

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

const directionCardClass = (value: number | null) =>
  value == null || !Number.isFinite(value) ? "is-neutral" : value > 0 ? "is-positive" : value < 0 ? "is-negative" : "is-neutral";

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
      .slice(0, 12),
    topPersistence: rows
      .filter((row) => row.persistenceRate != null && Number(row.observedDays) > 0)
      .sort((a, b) =>
        Number(b.persistenceRate) - Number(a.persistenceRate)
        || Number(b.positiveDays) - Number(a.positiveDays)
        || a.themeName.localeCompare(b.themeName, "ko-KR"))
      .slice(0, 6),
  };
};

type RealtimeThemeRankPanelProps = {
  rows: ReturnType<typeof getRealtimeThemeSchedulerState>["snapshot"]["themes"];
  snapshotAt: string | null;
  intervalMinutes: string;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenAll: () => void;
};

type RealtimeThemeRows = ReturnType<typeof getRealtimeThemeSchedulerState>["snapshot"]["themes"];

function patternQualityLabel(stock: DrctInsightStock) {
  if (!stock.success_sample_count) return "사례 부족";
  if (stock.pattern_status === "VERIFIED" || stock.success_similarity >= 70) return "양호";
  if (stock.pattern_status === "WEAK" || (stock.pattern_edge ?? 1) <= 0) return "확인 필요";
  return "보통";
}

type UsKrLeadStatus = "strong" | "priority" | "linked" | "reference" | "shortage";

const US_KR_LEAD_STATUS: Record<UsKrLeadStatus, { label: string }> = {
  strong: { label: "강한 연계" },
  priority: { label: "우선 관찰" },
  linked: { label: "연계 확인" },
  reference: { label: "참고" },
  shortage: { label: "데이터 부족" },
};

const resolveUsKrLeadStatus = (row: UsKrTodayObservationItem, d1Rank: number | null, flowGate: string | null): UsKrLeadStatus => {
  if (!row.available || row.sample_count < 5 || row.response_rate == null) return "shortage";
  const responseRate = Number(row.response_rate);
  if (Number(row.latest_value) > 0 && responseRate >= 60 && (d1Rank ?? 99) <= 5 && flowGate === "PASS") return "strong";
  if (Number(row.latest_value) > 0 && responseRate >= 55 && ((d1Rank ?? 99) <= 10 || flowGate === "PASS")) return "priority";
  if (Number(row.latest_value) > 0 && responseRate >= 50) return "linked";
  return "reference";
};

function UsKrLeadObservationPanel({ observation, d1, insight, usSummary, loading, error, onRetry, onOpenTheme, onOpenAll }: {
  observation: UsKrTodayObservation | null;
  d1: MarketThemeObservationResponse | null;
  insight: DrctInsightToday | null;
  usSummary: UsThemeDashboardSummary | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenAll: () => void;
}) {
  const d1ByTheme = new Map((d1?.items ?? []).map((row) => [row.theme_id, row]));
  const insightByTheme = new Map((insight?.themes ?? []).map((row) => [row.theme_id, row]));
  const persistenceByTheme = new Map(
    [...(usSummary?.top_strength ?? []), ...(usSummary?.top_persistence ?? [])]
      .map((row) => [row.theme_id, row] as const),
  );
  const rows = (observation?.items ?? [])
    .filter((row) => row.available && row.latest_value != null)
    .map((row) => {
      const d1Item = d1ByTheme.get(row.kr_theme_id);
      const insightItem = insightByTheme.get(row.kr_theme_id);
      const d1Rank = d1Item?.observation_rank ?? insightItem?.observation_rank ?? null;
      const flowGate = insightItem?.gates.flow ?? null;
      return { row, d1Rank, flowGate, persistence: persistenceByTheme.get(row.us_theme_id), status: resolveUsKrLeadStatus(row, d1Rank, flowGate) };
    })
    .sort((left, right) =>
      Number(right.row.latest_value) - Number(left.row.latest_value)
      || left.row.us_theme_name.localeCompare(right.row.us_theme_name, "ko-KR"))
    .slice(0, 6);
  const flowLabel = (gate: string | null) => gate === "PASS" ? "수급 통과" : gate === "WATCH" ? "수급 관찰" : gate === "WEAK" ? "수급 약화" : "수급 대기";

  return <SectionCard className="dashboard-us-kr-lead-section dashboard-routine-us-themes">
    <div className="dashboard-v2-section-heading dashboard-us-kr-lead-heading">
      <div>
        <h3 className="section-title">미국 선행 → 국내 테마 관찰</h3>
        <p>전일 미국 테마 흐름과 과거 국내 반응, 오늘의 D+1 가격·수급 후보를 한 번에 연결합니다.</p>
      </div>
      <span>US D-1 → KR D0</span>
    </div>
    {loading ? <div className="dashboard-us-kr-lead-grid is-loading" aria-label="한미 테마 연계 관찰 불러오는 중">{[0, 1, 2, 3, 4, 5].map((index) => <i key={index} />)}</div>
      : error ? <div className="dashboard-v2-rank-state error"><p>한미 테마 연계 데이터를 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={onRetry}>다시 시도</button></div>
      : rows.length ? <div className="dashboard-us-kr-lead-grid">
        {rows.map(({ row, d1Rank, flowGate, persistence, status }, index) => <button type="button" className={`dashboard-us-kr-lead-card ${Number(row.latest_value) > 0 ? "is-positive" : Number(row.latest_value) < 0 ? "is-negative" : "is-neutral"}`} key={row.link_id} onClick={() => onOpenTheme(row.kr_theme_id)} aria-label={`${row.us_theme_name}에서 ${row.kr_theme_name} 연계 상세 보기`}>
          <span className="dashboard-us-kr-lead-rank">{index + 1}</span>
          <div className="dashboard-us-kr-lead-us">
            <small>미국 D-1</small><strong title={row.us_theme_name}>{row.us_theme_name}</strong>
            <b>{formatSignedPercent(row.latest_value)}</b>
            <em>{persistence ? `최근 ${persistence.observed_days}일 중 ${persistence.positive_days}일 상승` : "상승 지속 데이터 확인 중"}</em>
          </div>
          <div className="dashboard-us-kr-lead-relation">
            <span>↓</span><strong>{row.response_rate == null ? "반응 데이터 부족" : `과거 상승 반응 ${Math.round(row.response_rate)}%`}</strong><small>{row.sample_count ? `${row.sample_count}건 기준` : row.sample_guidance}</small>
          </div>
          <div className="dashboard-us-kr-lead-kr">
            <small>국내 D0 관찰</small><strong title={row.kr_theme_name}>{row.kr_theme_name}</strong>
            <span>{d1Rank == null ? "D+1 비상위" : `D+1 #${d1Rank}`} · {flowLabel(flowGate)}</span>
          </div>
          <span className={`dashboard-us-kr-lead-status ${status}`}>{US_KR_LEAD_STATUS[status].label}</span>
        </button>)}
      </div> : <div className="dashboard-v2-rank-state"><p>미국 테마와 연결된 국내 관찰 테마가 없습니다.</p></div>}
    <footer className="dashboard-us-kr-lead-footer"><span>{observation?.latest_us_date ? `미국 ${observation.latest_us_date} 기준` : "미국 데이터 기준일 확인 중"}{d1?.run?.target_date ? ` · 국내 관찰 ${d1.run.target_date}` : ""}</span><button type="button" onClick={onOpenAll}>한미테마비교 전체 보기 →</button></footer>
  </SectionCard>;
}

const compareRealtimeThemeChange = (left: DrctInsightToday["themes"][number], right: DrctInsightToday["themes"][number]) =>
  (right.realtime_avg_change_rate ?? Number.NEGATIVE_INFINITY) - (left.realtime_avg_change_rate ?? Number.NEGATIVE_INFINITY)
  || (right.theme_strength ?? Number.NEGATIVE_INFINITY) - (left.theme_strength ?? Number.NEGATIVE_INFINITY)
  || left.theme_name.localeCompare(right.theme_name, "ko-KR");

function LiveThemePanel({ title, description, badge, themes, emptyMessage, onOpen }: {
  title: string;
  description: string;
  badge: string;
  themes: DrctInsightToday["themes"];
  emptyMessage: string;
  onOpen: (themeId: number) => void;
}) {
  return <article className="dashboard-live-theme-panel">
    <header><div><h4>{title}</h4><p>{description}</p></div><span>{themes.length}개</span></header>
    <div>{themes.length ? themes.map((theme) => <button type="button" className={directionCardClass(theme.realtime_avg_change_rate)} key={theme.theme_id} onClick={() => onOpen(theme.theme_id)}>
      <div className="dashboard-live-theme-title"><strong>{theme.theme_name}</strong><em>{badge}</em></div>
      <p>D+1 #{theme.observation_rank ?? "-"} → {theme.realtime_rank == null ? "실시간 대기" : `실시간 #${theme.realtime_rank}`}</p>
      <dl>
        <div className={directionCardClass(theme.realtime_avg_change_rate)}><dt>실시간</dt><dd>{formatSignedPercent(theme.realtime_avg_change_rate)}</dd></div>
        <div className={directionCardClass(theme.theme_strength)}><dt>테마강도</dt><dd>{formatSignedPercent(theme.theme_strength)}</dd></div>
        <div className="is-neutral"><dt>상승확산</dt><dd>{theme.valid_stock_count ? `${theme.up_count}/${theme.valid_stock_count}` : "대기"}</dd></div>
      </dl>
      <small>{badge === "신규" ? "장중 신규 강세" : badge === "확인" ? "선행 가설이 장중에서도 확인됨" : theme.insight_status === "MISMATCH" ? "장전 선행 신호와 실제 흐름 불일치" : "장전 후보 대비 장중 흐름 약화"}</small>
    </button>) : <p className="dashboard-insight-empty">{emptyMessage}</p>}</div>
  </article>;
}

function IntradayMarketStructure({ insight, previousInsight, onOpenTheme }: {
  insight: DrctInsightToday | null;
  previousInsight: DrctInsightToday | null;
  onOpenTheme: (themeId: number) => void;
}) {
  const validThemes = (insight?.themes ?? []).filter((theme) =>
    theme.realtime_snapshot_at
    && theme.valid_stock_count > 0
    && theme.realtime_avg_change_rate != null
    && Number.isFinite(theme.realtime_avg_change_rate));
  const positiveThemes = validThemes.filter((theme) => (theme.realtime_avg_change_rate ?? 0) > 0);
  const breadthThemes = validThemes.filter((theme) => theme.breadth_ratio != null && Number.isFinite(theme.breadth_ratio));
  const averageBreadth = breadthThemes.length
    ? breadthThemes.reduce((sum, theme) => sum + Number(theme.breadth_ratio), 0) / breadthThemes.length
    : null;
  const positiveStrengthThemes = validThemes
    .filter((theme) => (theme.theme_strength ?? 0) > 0)
    .sort((a, b) => Number(b.theme_strength) - Number(a.theme_strength));
  const positiveStrengthTotal = positiveStrengthThemes.reduce((sum, theme) => sum + Number(theme.theme_strength), 0);
  const leadingThemes = positiveStrengthThemes.slice(0, 3);
  const topThreeConcentration = positiveStrengthTotal > 0
    ? leadingThemes.reduce((sum, theme) => sum + Number(theme.theme_strength), 0) / positiveStrengthTotal
    : null;
  const previousRanks = new Map((previousInsight?.themes ?? [])
    .filter((theme) => theme.realtime_rank != null)
    .map((theme) => [theme.theme_id, theme.realtime_rank as number]));
  const rankMoves = validThemes.flatMap((theme) => {
    const previousRank = previousRanks.get(theme.theme_id);
    if (previousRank == null || theme.realtime_rank == null) return [];
    return [{ theme, previousRank, currentRank: theme.realtime_rank, delta: previousRank - theme.realtime_rank }];
  });
  const risingMoves = rankMoves.filter((move) => move.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, 2);
  const fallingMove = rankMoves.filter((move) => move.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, 1);
  const displayedMoves = [...risingMoves, ...fallingMove];
  const strongRatio = validThemes.length ? positiveThemes.length / validThemes.length : null;
  const hasMajorMove = displayedMoves.some((move) => Math.abs(move.delta) >= 3);
  const interpretation = !validThemes.length
    ? "현재 Snapshot만으로 시장 구조 판단을 대기합니다."
    : strongRatio != null && strongRatio >= .5 && averageBreadth != null && averageBreadth >= .55 && (topThreeConcentration ?? 1) < .6
      ? hasMajorMove && risingMoves.length ? `시장 강세가 여러 테마와 종목으로 확산되는 가운데 ${risingMoves.map((move) => move.theme.theme_name).join("·")}으로 주도권 이동이 관찰됩니다.` : "시장 강세가 여러 테마와 종목으로 확산되는 흐름입니다."
      : strongRatio != null && strongRatio < .4 && (topThreeConcentration ?? 0) >= .6
        ? "상승이 소수 주도 테마에 집중된 흐름입니다."
        : strongRatio != null && strongRatio >= .5 && averageBreadth != null && averageBreadth < .5
          ? "강세 테마 수는 많지만 테마 내부 종목 확산은 제한적입니다."
          : hasMajorMove && risingMoves.length
            ? `기존 흐름에서 ${risingMoves.map((move) => move.theme.theme_name).join("·")}으로 주도권 이동이 관찰됩니다.`
            : "현재 시장의 확산과 주도 집중 변화를 함께 관찰하는 구간입니다.";

  return <section className="dashboard-market-structure">
    <header><div><h4>장중 시장 구조</h4><p>현재 시장의 상승 확산·주도 집중·주도권 이동을 보여줍니다.</p></div><span>{insight?.summary.last_updated_at?.slice(11, 16) ?? "Snapshot 대기"}</span></header>
    <div className="dashboard-market-structure-grid">
      <article><h5>시장 확산</h5><dl><div><dt>강세 테마</dt><dd>{validThemes.length ? <><b className="is-up">{positiveThemes.length}</b> / {validThemes.length}</> : "계산 대기"}</dd></div><div><dt>평균 상승확산</dt><dd>{averageBreadth == null ? "계산 대기" : `${Math.round(averageBreadth * 100)}%`}</dd></div></dl><p>{strongRatio == null ? "유효 실시간 테마 대기" : strongRatio >= .5 ? "강세가 여러 테마로 퍼지는지 확인" : "일부 테마 중심의 상승 흐름"}</p></article>
      <article><h5>주도 집중</h5><dl><div><dt>상위 3개 집중</dt><dd>{topThreeConcentration == null ? "계산 대기" : `${Math.round(topThreeConcentration * 100)}%`}</dd></div></dl><div className="dashboard-market-leaders">{leadingThemes.length ? leadingThemes.map((theme) => <button type="button" key={theme.theme_id} onClick={() => onOpenTheme(theme.theme_id)}>{theme.theme_name}</button>) : <span>주도 테마 계산 대기</span>}</div></article>
      <article className="dashboard-market-movement"><h5>주도권 이동</h5>{displayedMoves.length ? <div>{displayedMoves.map((move) => <button type="button" key={move.theme.theme_id} onClick={() => onOpenTheme(move.theme.theme_id)}><strong>{move.theme.theme_name}</strong><span>#{move.previousRank} → #{move.currentRank}</span><b className={move.delta > 0 ? "is-up" : "is-down"}>{move.delta > 0 ? "↑" : "↓"}{Math.abs(move.delta)}</b></button>)}</div> : <p className="dashboard-market-rank-wait">순위 비교 대기</p>}</article>
    </div>
    <footer><strong>시장 해석</strong><p>{interpretation}</p></footer>
  </section>;
}

type DashboardReviewThemeRow = {
  id: number; name: string; premarket: string; intraday: string; close: string;
  value?: number | null; verdict: string; tone: string;
};

const reviewValueTone = (value: string) => /\+\d/.test(value) ? "is-positive" : /-\d/.test(value) ? "is-negative" : "is-neutral";

type IntradaySignalReviewStatus = "강화" | "유지" | "약화" | "반전" | "비교 대기";

function intradaySignalReviewStatus(signal: DrctIntradayFocusSignal): IntradaySignalReviewStatus {
  const detected = signal.stock_return;
  const closed = signal.outcome?.d0_return;
  if (detected == null || closed == null) return "비교 대기";
  if ((detected > 0 && closed < 0) || (detected < 0 && closed > 0)) return "반전";
  const delta = closed - detected;
  if (delta >= 1) return "강화";
  if (delta <= -1) return "약화";
  return "유지";
}

const intradaySignalStatusClass = (status: IntradaySignalReviewStatus) => ({
  "강화": "is-strengthened", "유지": "is-maintained", "약화": "is-weakened",
  "반전": "is-reversed", "비교 대기": "is-pending",
}[status]);

function PostMarketReviewWorkspace({ insight, rows, counts, supply, supplyError, onRetrySupply, onOpenTheme, onOpenStock, onOpenSupply, onOpenHistory }: {
  insight: DrctInsightToday | null;
  rows: DashboardReviewThemeRow[];
  counts: { focus: number; confirmed: number; partial: number; weakened: number; new: number };
  supply: DailyThemeFlowResponse | null;
  supplyError: string;
  onRetrySupply: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenStock: (stock: DrctInsightStock) => void;
  onOpenSupply: () => void;
  onOpenHistory: () => void;
}) {
  const [showAllIntradaySignals, setShowAllIntradaySignals] = useState(false);
  const plannedRows = rows.filter((row) => row.tone !== "new");
  const newRows = rows.filter((row) => row.tone === "new");
  const top5New = newRows.filter((row) => /^#[1-5](?:\D|$)/.test(row.close)).length;
  const top10New = newRows.filter((row) => /^#(?:[1-9]|10)(?:\D|$)/.test(row.close)).length;
  const plannedStocks = (insight?.stocks ?? []).filter((stock) => stock.focus_candidate).sort((a, b) => (a.focus_rank ?? 999) - (b.focus_rank ?? 999)).slice(0, 6);
  const stockById = new Map((insight?.stocks ?? []).map((stock) => [stock.stock_id, stock]));
  const intradaySignals = [...(insight?.intraday_focus_signals ?? [])];
  const intradayStatusCounts = intradaySignals.reduce((countsByStatus, signal) => {
    const status = intradaySignalReviewStatus(signal);
    countsByStatus[status] = (countsByStatus[status] ?? 0) + 1;
    return countsByStatus;
  }, {} as Record<IntradaySignalReviewStatus, number>);
  const reviewPriority: Record<IntradaySignalReviewStatus, number> = { "강화": 0, "약화": 1, "반전": 1, "유지": 2, "비교 대기": 3 };
  const representativeSignals = [...intradaySignals].sort((a, b) =>
    reviewPriority[intradaySignalReviewStatus(a)] - reviewPriority[intradaySignalReviewStatus(b)]
    || a.signal_rank - b.signal_rank);
  const displayedIntradaySignals = showAllIntradaySignals ? intradaySignals : representativeSignals.slice(0, 6);
  const closeReturn = (stock: DrctInsightStock) => stock.outcome?.d0_return ?? stock.change_rate;
  const focusPositive = plannedStocks.filter((stock) => (closeReturn(stock) ?? 0) > 0).length;
  const focusAverage = plannedStocks.length ? plannedStocks.reduce((sum, stock) => sum + (closeReturn(stock) ?? 0), 0) / plannedStocks.length : null;
  const themeTone = new Map(rows.map((row) => [row.id, row.tone]));
  const supplyGroups = [
    { key: "confirmed", label: "가설 확인", rows: (supply?.items ?? []).filter((item) => themeTone.get(item.theme_id) === "confirmed") },
    { key: "weakened", label: "가설 약화", rows: (supply?.items ?? []).filter((item) => ["partial", "weakened"].includes(themeTone.get(item.theme_id) ?? "")) },
    { key: "new", label: "장중 신규", rows: (supply?.items ?? []).filter((item) => themeTone.get(item.theme_id) === "new") },
  ];
  const themeRecommendations = [...plannedRows.filter((row) => row.tone === "weakened"), ...newRows].slice(0, 4);
  const signalRecommendations = representativeSignals.filter((signal) => intradaySignalReviewStatus(signal) !== "유지").slice(0, Math.max(0, 7 - themeRecommendations.length));
  const confirmedNames = plannedRows.filter((row) => row.tone === "confirmed").map((row) => row.name).slice(0, 2);
  const weakenedNames = plannedRows.filter((row) => row.tone === "weakened").map((row) => row.name).slice(0, 2);
  const newNames = newRows.map((row) => row.name).slice(0, 3);
  const recap = [
    confirmedNames.length ? `${confirmedNames.join("·")}의 장전 가설은 종가까지 확인됐습니다.` : null,
    weakenedNames.length ? `${weakenedNames.join("·")}은 장중 이후 약화되어 복기가 필요합니다.` : null,
    newNames.length ? `${newNames.join("·")}은 장전 후보 밖에서 장중 신규 강세로 탐지됐습니다.` : null,
  ].filter(Boolean).join(" ") || "평가 가능한 종가 결과가 쌓이면 오늘의 복기 요약을 제공합니다.";
  const totalPlanned = Math.max(1, counts.focus);

  return <>
    <SectionCard className="dashboard-post-review dashboard-routine-review-table">
      <div className="dashboard-v2-section-heading"><div><h3 className="section-title">오늘의 가설 리뷰</h3><p>장전 가설과 장중 신규 탐지를 분리해 종가 결과까지 확인합니다.</p></div><span>장전 → 장중 → 종가</span></div>
      <section className="dashboard-review-distribution"><div><strong>장전 가설 {counts.focus}</strong><span>장중 신규는 포함하지 않습니다.</span></div><dl>{[
        ["confirmed", "확인", counts.confirmed], ["partial", "부분 확인", counts.partial], ["weakened", "약화", counts.weakened],
      ].map(([tone, label, value]) => <div key={String(tone)}><dt>{label}</dt><dd><i><b className={`is-${tone}`} style={{ width: `${Number(value) / totalPlanned * 100}%` }}/></i><strong>{value} · {Math.round(Number(value) / totalPlanned * 100)}%</strong></dd></div>)}</dl></section>
      <div className="dashboard-review-flow-grid">{plannedRows.length ? plannedRows.map((row) => <button type="button" key={row.id} className={`is-${row.tone}`} onClick={() => onOpenTheme(row.id)}><header><strong>{row.name}</strong><em>{row.verdict}</em></header><div className="dashboard-review-trajectory"><span><small>장전</small><b>{row.premarket}</b></span><i>→</i><span className={reviewValueTone(row.intraday)}><small>장중</small><b>{row.intraday}</b></span><i>→</i><span className={reviewValueTone(row.close)}><small>종가</small><b>{row.close}</b></span></div><p>{row.tone === "confirmed" ? "장전 가설이 장중과 종가까지 확인됨" : row.tone === "partial" ? "일부 강세는 유지됐으나 추가 확인 필요" : "장중부터 선행 가설과 다른 흐름 발생"}</p></button>) : <p className="dashboard-review-empty">평가할 장전 가설이 없습니다.</p>}</div>
      <section className="dashboard-review-new-themes"><header><div><h4>장중 새로 발견한 테마</h4><p>장전 후보 밖의 변화를 종가 유지 여부로 확인합니다.</p></div><dl><div><dt>신규 발견</dt><dd>{newRows.length}</dd></div><div><dt>종가 Top5</dt><dd>{top5New}</dd></div><div><dt>종가 Top10</dt><dd>{top10New}</dd></div></dl></header><div>{newRows.length ? newRows.map((row) => <button type="button" className={reviewValueTone(row.close)} key={row.id} onClick={() => onOpenTheme(row.id)}><strong>{row.name}</strong><span>집중 대상 아님 <i>→</i> 장중 신규 <i>→</i> <b>{row.close}</b></span><em>{/^#(?:[1-9]|10)(?:\D|$)/.test(row.close) ? "종가 유지" : "종가 확인 필요"}</em></button>) : <p>장중 신규 탐지 테마가 없습니다.</p>}</div></section>
    </SectionCard>

    <SectionCard className="dashboard-stock-review dashboard-routine-stock-review">
      <div className="dashboard-v2-section-heading"><div><h3 className="section-title">종목 대응 리뷰</h3><p>장전 Focus와 장중 반응 탐지를 서로 다른 기준으로 확인합니다.</p></div></div>
      <div className="dashboard-stock-review-grid">
        <article><header><div><h4>장전 Focus</h4><p>{plannedStocks.length}개 중 {focusPositive}개 상승 · 평균 {formatSignedPercent(focusAverage)}</p></div></header><div>{plannedStocks.length ? plannedStocks.map((stock) => <button type="button" className={directionCardClass(closeReturn(stock))} key={stock.stock_id} onClick={() => onOpenStock(stock)}><span><strong>{stock.stock_name}</strong><small>장전 Focus #{stock.focus_rank ?? "-"}</small></span><b>종가 {formatSignedPercent(closeReturn(stock))}</b></button>) : <p>장전 Focus 결과가 없습니다.</p>}</div></article>
        <article className="dashboard-intraday-signal-review"><header><div><h4>장중 Focus Signal</h4><p>{intradaySignals.length ? `탐지 ${intradaySignals.length} · 강화 ${intradayStatusCounts["강화"] ?? 0} · 유지 ${intradayStatusCounts["유지"] ?? 0} · 약화 ${intradayStatusCounts["약화"] ?? 0} · 반전 ${intradayStatusCounts["반전"] ?? 0}` : "장중 실제 탐지 기록을 기준으로 복기합니다."}</p></div></header><div>{displayedIntradaySignals.length ? displayedIntradaySignals.map((signal) => { const stock = stockById.get(signal.stock_id); const status = intradaySignalReviewStatus(signal); const detectedTime = signal.snapshot_at.slice(11, 16); return <button type="button" className={`${directionCardClass(signal.outcome?.d0_return ?? null)} dashboard-intraday-review-card ${intradaySignalStatusClass(status)}`} key={signal.stock_id} disabled={!stock} onClick={() => stock && onOpenStock(stock)}><span className="dashboard-intraday-review-title"><strong>{signal.stock_name}</strong><em>{status}</em></span><small>장중 탐지 {detectedTime || "시간 미보존"} · 첫 진입 #{signal.signal_rank}{signal.best_rank < signal.signal_rank ? ` · 최고 #${signal.best_rank}` : ""}</small><span className="dashboard-intraday-review-metrics"><i>당시 {formatSignedPercent(signal.stock_return)}</i><i>테마 대비 {signal.relative_strength == null ? "미보존" : `${formatSignedPercent(signal.relative_strength)}p`}</i><i>패턴 {signal.pattern_score == null ? "미보존" : `${Math.round(signal.pattern_score)} · ${signal.pattern_status ?? "대기"}`}</i><b>→ 종가 {formatSignedPercent(signal.outcome?.d0_return ?? null)}</b></span></button>; }) : <p>{insight?.analysis_date ? "장중 Signal 기록 없음" : "장중 상세값 미보존"}</p>}</div>{intradaySignals.length > 6 ? <button type="button" className="dashboard-intraday-review-toggle" onClick={() => setShowAllIntradaySignals((value) => !value)}>{showAllIntradaySignals ? "대표 6개 보기" : `전체 ${intradaySignals.length}개 보기`} →</button> : null}</article>
      </div>
      {(insight?.my_watch.length ?? 0) > 0 ? <details className="dashboard-watchlist-review"><summary>내 관심종목 오늘의 변화 {insight?.my_watch.length ?? 0} <span>›</span></summary><div>{insight?.my_watch.map((stock) => <button type="button" className={directionCardClass(closeReturn(stock))} key={stock.stock_id} onClick={() => onOpenStock(stock)}><strong>{stock.stock_name}</strong><span>종가 {formatSignedPercent(closeReturn(stock))} · 테마 대비 {stock.outcome?.relative_return == null ? "대기" : `${formatSignedPercent(stock.outcome.relative_return)}p`}</span></button>)}</div></details> : null}
    </SectionCard>

    <SectionCard className="dashboard-routine-supply dashboard-review-supply-linked">
      <div className="dashboard-v2-section-heading"><div><h3 className="section-title">오늘의 수급 요약</h3><p>가설 확인·약화·신규 테마와 오늘 포착된 수급 이벤트를 연결합니다.</p></div><button type="button" className="dashboard-v2-text-button" onClick={onOpenSupply}>수급 분석 열기 →</button></div>
      {supplyError ? <div className="dashboard-review-state error"><span>수급 요약을 불러오지 못했습니다.</span><button type="button" onClick={onRetrySupply}>다시 시도</button></div> : supply ? <div className="dashboard-review-supply-groups">{supplyGroups.map((group) => <article className={`is-${group.key}`} key={group.key}><h4>{group.label}</h4>{group.rows.length ? group.rows.slice(0, 3).map((item) => <button type="button" className={directionCardClass(item.avg_change_rate)} key={item.theme_id} onClick={() => onOpenTheme(item.theme_id)}><strong>{item.theme_name}</strong><span>{item.detected_stock_count}종목 · 거래대금 {item.total_trading_value_krw_100m.toLocaleString()}억원</span><b>{formatSignedPercent(item.avg_change_rate)}</b></button>) : <p>연결된 수급 이벤트 없음</p>}</article>)}</div> : <div className="dashboard-review-state">수급 요약을 불러오는 중입니다.</div>}
    </SectionCard>

    <SectionCard className="dashboard-review-learning dashboard-routine-learning">
      <div className="dashboard-v2-section-heading"><div><h3 className="section-title">복기 추천</h3><p>실패·신규·장중 Signal 변화·Pattern 사례를 우선 확인합니다.</p></div><span>{themeRecommendations.length + signalRecommendations.length}건</span></div>
      <div className="dashboard-review-recommendations">{themeRecommendations.map((row) => <button type="button" className={reviewValueTone(row.close)} key={`theme-${row.id}`} onClick={() => onOpenTheme(row.id)}><em>{row.tone === "new" ? "신규 발견 사례" : "가설 약화 사례"}</em><strong>{row.name}</strong><span>{row.premarket} → {row.intraday} → {row.close}</span></button>)}{signalRecommendations.map((signal) => { const stock = stockById.get(signal.stock_id); const status = intradaySignalReviewStatus(signal); return stock ? <button type="button" className={directionCardClass(signal.outcome?.d0_return ?? null)} key={`signal-${signal.stock_id}`} onClick={() => onOpenStock(stock)}><em>장중 Signal {status} 사례</em><strong>{signal.stock_name}</strong><span>첫 진입 #{signal.signal_rank} · 당시 {formatSignedPercent(signal.stock_return)} → 종가 {formatSignedPercent(signal.outcome?.d0_return ?? null)}</span></button> : null; })}{!themeRecommendations.length && !signalRecommendations.length ? <p>현재 우선 복기할 사례가 없습니다.</p> : null}</div>
      <footer><strong>오늘의 복기 요약</strong><p>{recap}</p><button type="button" onClick={onOpenHistory}>과거 판단 검증 →</button></footer>
    </SectionCard>
  </>;
}

function TodayInsightPanel({ stage, insight, previousInsight, themeSummary, reviewCounts, reviewRows, failed, realtimeThemePanel, onOpen, onOpenTheme, onOpenStock }: {
  stage: DashboardStage;
  insight: DrctInsightToday | null;
  previousInsight: DrctInsightToday | null;
  themeSummary: ThemeSummaryData | null;
  reviewCounts?: { focus: number; confirmed: number; partial: number; weakened: number; new: number };
  reviewRows?: DashboardReviewThemeRow[];
  failed: boolean;
  realtimeThemePanel?: ReactNode;
  onOpen: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenStock: (stock: DrctInsightStock) => void;
}) {
  const focusThemes = (insight?.themes ?? [])
    .filter((row) => row.focus_candidate_count > 0)
    .sort((a, b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999));
  const displayedThemes = (stage === "verify" ? [...focusThemes].sort(compareRealtimeThemeChange) : focusThemes).slice(0, 3);
  const planFocusStocks = (insight?.stocks ?? [])
    .filter((row) => row.focus_candidate)
    .sort((a, b) => (a.focus_rank ?? 999) - (b.focus_rank ?? 999))
    .slice(0, 4);
  const realtimeHotStocks = (insight?.stocks ?? [])
    .filter((row) => row.change_rate != null && Number.isFinite(row.change_rate) && row.gates.execution !== "INVALID")
    .sort((a, b) =>
      (b.change_rate ?? -Infinity) - (a.change_rate ?? -Infinity)
      || (b.relative_strength ?? -Infinity) - (a.relative_strength ?? -Infinity)
      || (b.theme_strength ?? -Infinity) - (a.theme_strength ?? -Infinity)
      || b.success_similarity - a.success_similarity)
    .slice(0, 12);
  const focusStocks = stage === "verify" ? realtimeHotStocks : planFocusStocks;
  const confirmedCount = focusThemes.filter((row) => ["STRENGTHENING", "STABLE"].includes(row.insight_status)).length;
  const weakenedCount = focusThemes.filter((row) => ["WEAKENING", "MISMATCH"].includes(row.insight_status)).length;
  const surpriseThemes = (insight?.themes ?? [])
    .filter((row) => row.insight_status === "NEW")
    .sort(compareRealtimeThemeChange)
    .slice(0, 12);
  const liveConfirmedThemes = focusThemes.filter((row) => ["STRENGTHENING", "STABLE"].includes(row.insight_status)).sort(compareRealtimeThemeChange);
  const liveWeakenedThemes = focusThemes.filter((row) => ["WEAKENING", "MISMATCH"].includes(row.insight_status)).sort(compareRealtimeThemeChange);
  const relativeStrongCount = focusStocks.filter((row) => (row.relative_strength ?? 0) > 0).length;
  const selectedNames = focusThemes.slice(0, 2).map((row) => row.theme_name).join(" · ") || "상위 관찰 테마";
  const sourceDate = themeSummary?.dataDate ?? insight?.analysis_date ?? "확인 중";
  const sourceLabel = stage === "plan"
    ? `전일 종가 기준 ${sourceDate}`
    : insight?.summary.last_updated_at ? `실시간 Snapshot ${insight.summary.last_updated_at.slice(0, 19).replace("T", " ")}` : "실시간 Snapshot 대기 중";
  if (stage === "review") {
    const counts = reviewCounts ?? { focus: focusThemes.length, confirmed: 0, partial: 0, weakened: 0, new: 0 };
    const outcome = insight?.outcome_summary;
    const newTop10 = (reviewRows ?? []).filter((row) => row.tone === "new" && /^#(?:[1-9]|10)(?:\D|$)/.test(row.close)).length;
    return <SectionCard className="dashboard-insight-panel dashboard-routine-insight dashboard-stage-insight is-review">
      <div className="dashboard-insight-head"><div><small>REVIEW · ACTUAL</small><h3>오늘의 결과</h3></div><div className="dashboard-insight-head-tools"><span>종가 기준 {themeSummary?.dataDate ?? insight?.analysis_date ?? "확인 중"}</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>상세 →</button></div></div>
      {failed ? <p className="dashboard-insight-error">인사이트 요약을 불러오지 못했습니다.</p> : <>
        <section className="dashboard-insight-decision"><span>오늘의 결론</span><strong>장전 집중 {counts.focus}개 중 {counts.confirmed}개 확인 · {counts.partial}개 부분 · {counts.weakened}개 약화</strong><p>장중 신규 {counts.new}개 중 {newTop10}개가 종가 Top10을 유지했습니다.</p></section>
        <div className="dashboard-review-result-bar" aria-label="오늘의 결과 요약"><span>장전 집중 <b>{counts.focus}</b></span><span className="is-confirmed">확인 <b>{counts.confirmed}</b></span><span className="is-partial">부분 <b>{counts.partial}</b></span><span className="is-weakened">약화 <b>{counts.weakened}</b></span><span className="is-new">장중 신규 <b>{counts.new}</b></span><span>종가 Top10 <b>{newTop10}</b></span><span>Focus 후보 <b>{outcome?.focus_count ?? 0}</b></span><span className="is-confirmed">상승 종목 <b>{outcome?.positive_count ?? 0}</b></span><span className="is-key">복기 추천 <b>{outcome?.review_count ?? 0}</b></span></div>
      </>}
    </SectionCard>;
  }

  if (stage === "verify") {
    return <SectionCard className="dashboard-insight-panel dashboard-routine-insight dashboard-stage-insight is-verify dashboard-live-workspace">
      <div className="dashboard-insight-head"><div><small>VERIFY · LIVE SNAPSHOT</small><h3>DrCT 실시간 인사이트</h3></div><div className="dashboard-insight-head-tools"><span>{sourceLabel}</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>인사이트 열기 →</button></div></div>
      {failed ? <p className="dashboard-insight-error">인사이트 요약을 불러오지 못했습니다.</p> : <>
        <section className="dashboard-insight-decision"><span>현재 판단</span><strong>집중테마 {focusThemes.length}개 중 {confirmedCount}개 확인 · {weakenedCount}개 약화</strong><p>장중 신규 테마 {surpriseThemes.length}개 탐지 · 현재 시장 반응이 강한 종목 {focusStocks.length}개를 확인합니다.</p></section>
        <div className="dashboard-insight-strip" aria-label="장중 가설 검증 요약"><span>집중테마 <b>{focusThemes.length}</b></span><span className="is-confirmed">가설 확인 <b>{confirmedCount}</b></span><span className="is-weakened">가설 약화 <b>{weakenedCount}</b></span><span className="is-new">장중 신규 <b>{surpriseThemes.length}</b></span><span className="is-key">Focus 강세 <b>{relativeStrongCount}</b></span></div>
        <div className="dashboard-live-theme-grid">
          <LiveThemePanel title="장중 신규 발견" description="장전 집중 대상 밖의 급부상 테마" badge="신규" themes={surpriseThemes} emptyMessage="현재 새롭게 부상한 테마가 없습니다." onOpen={onOpenTheme}/>
          <LiveThemePanel title="예상 + 실제 강세" description="장전 관찰 후 실시간 강세 확인" badge="확인" themes={liveConfirmedThemes} emptyMessage="현재 확인된 집중테마가 없습니다." onOpen={onOpenTheme}/>
          <LiveThemePanel title="예상했지만 약화" description="장전 후보의 실시간 약화 점검" badge="약화" themes={liveWeakenedThemes} emptyMessage="현재 약화된 집중테마가 없습니다." onOpen={onOpenTheme}/>
        </div>
        <div className="dashboard-live-top12-grid">
          {realtimeThemePanel}
          <article className="dashboard-v2-rank-panel dashboard-focus-top12-panel">
            <div className="dashboard-v2-rank-head"><div><h4>Focus 실시간 Signal Top12</h4><span title="현재 실시간 등락률, 테마 대비 상대강도, 테마강도를 기준으로 확인 가치가 높은 종목을 보여줍니다. 매매 적합성을 의미하지 않습니다.">현재 시장 반응이 강한 종목 순입니다. ⓘ</span></div></div>
            {focusStocks.length ? <ol className="dashboard-v2-rank-list dashboard-focus-top12-list">{focusStocks.map((stock, index) => <li key={stock.stock_id}><button type="button" className={directionCardClass(stock.change_rate)} onClick={() => onOpenStock(stock)}>
              <span className={`dashboard-v2-rank-badge ${index === 0 ? "first" : ""}`}>{index + 1}</span>
              <span className="dashboard-v2-rank-copy"><strong>{stock.stock_name}</strong><small>{stock.theme_name ?? "테마 미지정"} · 테마 대비 {stock.relative_strength == null ? "대기" : `${formatSignedPercent(stock.relative_strength)}p`} · 패턴 {Math.round(stock.success_similarity)} · {patternQualityLabel(stock)}</small></span>
              <strong className={(stock.change_rate ?? 0) > 0 ? "dashboard-v2-return-value" : (stock.change_rate ?? 0) < 0 ? "dashboard-v2-realtime-negative-value" : "is-neutral"}>{formatSignedPercent(stock.change_rate)}</strong>
            </button></li>)}</ol> : <p className="dashboard-insight-empty">현재 확인 가능한 실시간 종목이 없습니다.</p>}
            <button type="button" className="dashboard-insight-all" onClick={onOpen}>실시간 인사이트 전체 →</button>
          </article>
        </div>
        <IntradayMarketStructure insight={insight} previousInsight={previousInsight} onOpenTheme={onOpenTheme}/>
      </>}
    </SectionCard>;
  }

  return <SectionCard className="dashboard-insight-panel dashboard-routine-insight dashboard-stage-insight is-plan">
    <div className="dashboard-insight-head">
      <div><small>PLAN · PREVIOUS CLOSE</small><h3>DrCT 실시간 인사이트</h3></div>
      <div className="dashboard-insight-head-tools"><span>{sourceLabel}</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>인사이트 열기 →</button></div>
    </div>
    {failed ? <p className="dashboard-insight-error">인사이트 요약을 불러오지 못했습니다.</p> : <>
      <section className="dashboard-insight-decision">
        <span>오늘의 판단</span>
        <strong>{selectedNames}를 우선 관찰합니다.</strong><p>{insightThemeReason(displayedThemes[0])} 장중에는 실제 강도와 확산을 확인합니다.</p>
      </section>
      <div className="dashboard-insight-strip" aria-label="장전 준비 요약">
        <span>관찰 <b>{insight?.summary.observed_theme_count ?? "-"}</b></span><span className="is-key">집중테마 <b>{focusThemes.length}</b></span><span className="is-key">Focus <b>{insight?.summary.focus_candidate_count ?? "-"}</b></span><span>검증 <b>{insight?.summary.final_candidate_count ?? "-"}</b></span><span>내관찰 <b>{insight?.summary.my_watch_count ?? "-"}</b></span>
      </div>
      <div className="dashboard-insight-columns">
        <div className="dashboard-insight-theme-panels is-plan">
        <article className="dashboard-insight-signal-list dashboard-insight-theme-list">
          <header><div><h4>오늘 우선 볼 테마</h4><p>전일 확정 데이터 기준</p></div><span>{focusThemes.length}개</span></header>
          <div>{displayedThemes.length ? displayedThemes.map((theme, index) => {
            return <button type="button" className="dashboard-insight-theme-row" key={theme.theme_id} onClick={() => onOpenTheme(theme.theme_id)}>
              <div className="dashboard-insight-row-title"><span>#{theme.observation_rank ?? index + 1}</span><strong>{theme.theme_name}</strong><em>Focus {theme.focus_candidate_count}</em></div>
              <p>{insightThemeReason(theme)}</p><dl><div><dt>전일 D+1</dt><dd>{theme.d1_candidate_score == null ? "대기" : Math.round(theme.d1_candidate_score)}</dd></div><div><dt>수급</dt><dd>{theme.gates.flow === "PASS" ? "강함" : theme.gates.flow === "NO_DATA" ? "대기" : "관찰"}</dd></div></dl>
            </button>;
          }) : <p className="dashboard-insight-empty">현재 집중테마가 없습니다.</p>}</div>
          {focusThemes.length > displayedThemes.length ? <button type="button" className="dashboard-insight-all" onClick={onOpen}>집중테마 전체 {focusThemes.length} →</button> : null}
        </article>
        </div>
        <article className="dashboard-insight-signal-list dashboard-insight-stock-list">
          <header><div><h4>지금 볼 종목</h4><p>패턴 의미와 전일 종가</p></div><span>Top {focusStocks.length}</span></header>
          <div>{focusStocks.length ? focusStocks.map((stock) => <button type="button" className="dashboard-insight-stock-row" key={stock.stock_id} onClick={() => onOpenStock(stock)}>
              <div><strong>{stock.stock_name}</strong><small>{stock.theme_name ?? "테마 미지정"}</small></div>
              <div className="dashboard-insight-similarity" title="현재 차트와 조건이 과거 성공 Marker 사례와 얼마나 유사한지 나타냅니다."><span>패턴 유사도 {Math.round(stock.success_similarity)} · {patternQualityLabel(stock)}</span><i><b style={{ width: `${Math.max(0, Math.min(100, stock.success_similarity))}%` }} /></i></div>
              <b className={(stock.change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>전일 {formatSignedPercent(stock.change_rate)}</b>
              <em>관찰</em>
            </button>) : <p className="dashboard-insight-empty">현재 Focus 종목이 없습니다.</p>}</div>
          <button type="button" className="dashboard-insight-all" onClick={onOpen}>Focus 전체 {insight?.summary.focus_candidate_count ?? 0} →</button>
        </article>
      </div>
      <footer className="dashboard-insight-checks"><strong>장이 열리면 확인</strong><span>○ 우선 테마의 강도가 실제로 강화되는가</span><span>○ 상승 종목이 테마 전체로 확산되는가</span><span>○ 관심 종목이 테마보다 강하게 움직이는가</span><span>○ 전일 패턴 가설이 실제 흐름과 일치하는가</span></footer>
    </>}
  </SectionCard>;
}

function RealtimeThemeRankPanel({
  rows,
  snapshotAt,
  intervalMinutes,
  loading,
  error,
  onRetry,
  onOpenTheme,
  onOpenAll,
}: RealtimeThemeRankPanelProps) {
  const rankedRows = [...rows]
    .filter((row) => row.theme_strength != null && Number.isFinite(row.theme_strength))
    .sort((a, b) => Number(b.theme_strength) - Number(a.theme_strength) || a.theme_name.localeCompare(b.theme_name, "ko-KR"))
    .slice(0, 12);
  const snapshotTime = snapshotAt?.slice(11, 19) || null;

  return (
    <article className="dashboard-v2-rank-panel dashboard-v2-realtime-rank-panel">
      <div className="dashboard-v2-rank-head">
        <div>
          <h4>실시간 테마 강도 Top12</h4>
          <span>{snapshotTime ? `최근 Snapshot ${snapshotTime} · ${intervalMinutes}분 주기` : "실시간 Snapshot 대기 중"}</span>
        </div>
      </div>
      {loading ? (
        <div className="dashboard-v2-rank-skeleton dashboard-v2-realtime-rank-skeleton" aria-label="실시간 테마 순위 불러오는 중">
          {Array.from({ length: 12 }, (_, index) => <div key={index}><i /><span /><b /></div>)}
        </div>
      ) : error ? (
        <div className="dashboard-v2-rank-state error">
          <p>실시간 테마 데이터를 불러오지 못했습니다.</p>
          <button type="button" className="btn btn-secondary" onClick={onRetry}>다시 시도</button>
        </div>
      ) : rankedRows.length ? (
        <ol className="dashboard-v2-rank-list dashboard-v2-realtime-rank-list">
          {rankedRows.map((row, index) => (
            <li key={`realtime-${row.theme_id}`}>
              <button type="button" onClick={() => onOpenTheme(row.theme_id)} aria-label={`${row.theme_name} 실시간 테마 보기`} title={row.theme_name}>
                <span className={`dashboard-v2-rank-badge ${index === 0 ? "first" : ""}`}>{index + 1}</span>
                <span className="dashboard-v2-rank-copy">
                  <strong title={row.theme_name}>{row.theme_name}</strong>
                  <small>강도 {formatSignedPercent(row.theme_strength)} · 확산 {row.valid_stock_count}/{row.linked_stock_count}</small>
                </span>
                <strong className={Number(row.avg_change_rate) > 0 ? "dashboard-v2-return-value" : Number(row.avg_change_rate) < 0 ? "dashboard-v2-realtime-negative-value" : "is-neutral"}>
                  {formatSignedPercent(row.avg_change_rate)}
                </strong>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <div className="dashboard-v2-rank-state">
          <p>저장된 실시간 Snapshot이 없습니다. 실시간 테마 트리맵에서 수집을 시작해 주세요.</p>
          <button type="button" className="btn btn-secondary" onClick={onOpenAll}>실시간 트리맵으로 이동</button>
        </div>
      )}
    </article>
  );
}

const dashboardStockView = (stock: DrctInsightStock): IntradayView => {
  const state = stock.gates.execution === "INVALID"
    ? "WARNING"
    : (stock.relative_strength ?? 0) > 0
      ? "STRENGTHENING"
      : (stock.relative_strength ?? 0) < 0 ? "WEAKENING" : "STABLE";
  return {
    state,
    reasons: [stock.relative_strength == null ? "테마 대비 강도 데이터 대기" : `테마 대비 강도 ${formatSignedPercent(stock.relative_strength)}p`],
    themeDelta: null,
    themeChangeDelta: null,
    initialThemeDelta: null,
    breadthDelta: null,
    executionAssist: state === "WARNING" ? "CAUTION" : state === "STRENGTHENING" ? "CONSIDER_READY" : "KEEP_WATCH",
  };
};

const insightThemeLead = (theme: DrctInsightToday["themes"][number] | undefined) => {
  if (!theme) return "집중 대상";
  const us = theme.us_lead.strength === "STRONG" ? "US 강" : theme.us_lead.strength === "MODERATE" ? "US 보통" : theme.us_lead.linked ? "US 약" : "US 없음";
  const flow = theme.gates.flow === "PASS" ? "수급 양호" : theme.gates.flow === "WEAK" ? "수급 약함" : theme.gates.flow === "NO_DATA" ? "수급 대기" : "수급 관찰";
  return [`관찰 #${theme.observation_rank ?? "-"}`, us, flow].join(" · ");
};

const insightThemeReason = (theme: DrctInsightToday["themes"][number] | undefined) => {
  if (!theme) return "가격·수급·패턴 신호를 함께 확인했습니다.";
  if (theme.signal_key_reason && !/호환 표시|기존 저장 결과/.test(theme.signal_key_reason)) return theme.signal_key_reason;
  return `${insightThemeLead(theme)} · ${theme.signal_stage_label || "가격·수급 신호"}`;
};

function CloseThemeTop12Panel({ rows, dataDate, loading, error, onRetry, onOpenTheme, onOpenAll }: {
  rows: ThemeSummaryRow[]; dataDate: string | null; loading: boolean; error: string;
  onRetry: () => void; onOpenTheme: (themeId: number) => void; onOpenAll: () => void;
}) {
  return <SectionCard className="dashboard-routine-close-top12">
    <div className="dashboard-v2-section-heading"><div><h3 className="section-title">국내 · 전일 종가 테마 강도 Top12</h3><p>전 거래일 최종 수집된 종가 기준으로 국내 테마 강도를 확인합니다.</p></div><span>{dataDate ? `종가 기준 ${dataDate}` : "종가 기준일 확인 중"}</span></div>
    {loading ? <div className="dashboard-close-top12-skeleton">{Array.from({ length: 12 }, (_, index) => <i key={index} />)}</div> : error ? <div className="dashboard-performance-state error">종가 테마 순위를 불러오지 못했습니다.<button type="button" onClick={onRetry}>다시 시도</button></div> : rows.length ? <ol className="dashboard-close-top12-list">{rows.slice(0, 12).map((row, index) => <li key={row.themeId}><button type="button" onClick={() => onOpenTheme(row.themeId)}><span>{index + 1}</span><strong title={row.themeName}>{row.themeName}</strong><b>{formatSignedPercent(row.dailyReturn)}</b></button></li>)}</ol> : <div className="dashboard-performance-state">전일 종가 테마 데이터가 없습니다.</div>}
    <button type="button" className="dashboard-v2-text-button dashboard-close-top12-more" onClick={onOpenAll}>전체 종가 순위 보기 →</button>
  </SectionCard>;
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
  const [activeStage, setActiveStage] = useState<DashboardStage>(resolveDefaultStage);
  const realtimeThemeScheduler = useSyncExternalStore(
    subscribeRealtimeThemeScheduler,
    getRealtimeThemeSchedulerState,
    getRealtimeThemeSchedulerState,
  );
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
  const [usKrObservation, setUsKrObservation] = useState<UsKrTodayObservation | null>(null);
  const [isUsKrObservationLoading, setIsUsKrObservationLoading] = useState(true);
  const [usKrObservationError, setUsKrObservationError] = useState("");
  const [usThemeFeedback, setUsThemeFeedback] = useState<ActionFeedback | null>(null);
  const [isUsThemeRunning, setIsUsThemeRunning] = useState(false);
  const [marketSignals, setMarketSignals] = useState<MarketSignalChangeItem[]>([]);
  const [marketSignalsEvaluatedAt, setMarketSignalsEvaluatedAt] = useState<string | null>(null);
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
  const [themeDetailRequest, setThemeDetailRequest] = useState<{
    themeId: number; dataDate: string | null;
    realtime?: { themeName: string; rank: number | null; strength: number | null; validStockCount: number; linkedStockCount: number; snapshotAt: string | null; hypothesis: "CONFIRMED" | "WEAKENING" | "NEW" };
  } | null>(null);
  const [realtimeThemeDetail, setRealtimeThemeDetail] = useState<RealtimeThemeStocksResponse | null>(null);
  const [isRealtimeThemeDetailLoading, setIsRealtimeThemeDetailLoading] = useState(false);
  const [realtimeThemeDetailError, setRealtimeThemeDetailError] = useState("");
  const [realtimeThemeDetailMetric, setRealtimeThemeDetailMetric] = useState<"average" | "strength">("strength");
  const [insightStockDetail, setInsightStockDetail] = useState<DrctInsightStock | null>(null);
  const [insightStockTab, setInsightStockTab] = useState<DrawerTab>("summary");
  const [insight, setInsight] = useState<DrctInsightToday | null>(() => repositories.drctInsight.peekToday());
  const previousInsightSnapshotRef = useRef<DrctInsightToday | null>(null);
  const [insightError, setInsightError] = useState("");
  const [performance, setPerformance] = useState<DrctInsightPerformance | null>(null);
  const [performanceError, setPerformanceError] = useState("");
  const [isPerformanceLoading, setIsPerformanceLoading] = useState(false);
  const [reviewBriefing, setReviewBriefing] = useState<ReviewBriefing | null>(null);
  const [reviewBriefingError, setReviewBriefingError] = useState("");
  const [isReviewBriefingLoading, setIsReviewBriefingLoading] = useState(false);
  const [reviewSupply, setReviewSupply] = useState<DailyThemeFlowResponse | null>(null);
  const [reviewSupplyError, setReviewSupplyError] = useState("");
  const themePollingTokenRef = useRef(0);
  const realtimeThemeDetailRequestRef = useRef(0);

  const loadRealtimeThemeDetail = useCallback(async (themeId: number, keepData = false) => {
    const requestId = ++realtimeThemeDetailRequestRef.current;
    if (!keepData) setRealtimeThemeDetail(null);
    setIsRealtimeThemeDetailLoading(true);
    setRealtimeThemeDetailError("");
    try {
      const data = await repositories.marketThemes.getRealtimeThemeStocks(themeId);
      if (requestId === realtimeThemeDetailRequestRef.current) setRealtimeThemeDetail(data);
    } catch (error) {
      if (requestId === realtimeThemeDetailRequestRef.current) {
        setRealtimeThemeDetailError(error instanceof Error ? error.message : "실시간 테마 상세 조회에 실패했습니다.");
      }
    } finally {
      if (requestId === realtimeThemeDetailRequestRef.current) setIsRealtimeThemeDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!themeDetailRequest?.realtime) {
      realtimeThemeDetailRequestRef.current += 1;
      setRealtimeThemeDetail(null);
      setRealtimeThemeDetailError("");
      setIsRealtimeThemeDetailLoading(false);
      return;
    }
    setRealtimeThemeDetailMetric("strength");
    void loadRealtimeThemeDetail(themeDetailRequest.themeId);
    return () => { realtimeThemeDetailRequestRef.current += 1; };
  }, [loadRealtimeThemeDetail, themeDetailRequest?.realtime, themeDetailRequest?.themeId]);

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
    if (!silent) setIsReadinessLoading(true);
    try {
      const response = await repositories.dashboard.readiness();
      const dataDate = response.theme.data_date;
      setThemeReadiness({
        dataDate,
        lastSuccessAt: response.theme.last_success_at,
        linkedStockCount: response.theme.linked_stock_count,
        status: resolveReadinessStatus(dataDate, response.theme.run_status),
      });
      setMarketReadiness({
        dataDate: response.market.data_date,
        lastRunAt: response.market.last_run_at,
        activeIndicatorCount: response.market.active_indicator_count,
        status: resolveReadinessStatus(response.market.data_date, response.market.run_status),
      });
      setThemeError("");
      setMarketError("");
      return dataDate;
    } catch (error) {
      const message = errorMessage(error);
      setThemeError(message);
      setMarketError(message);
      return null;
    } finally {
      setIsReadinessLoading(false);
    }
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

  const loadUsKrObservation = useCallback(async () => {
    setIsUsKrObservationLoading(true);
    setUsKrObservationError("");
    try {
      setUsKrObservation(await repositories.usKrThemeLinks.todayObservation(120, "theme_strength"));
    } catch (error) {
      setUsKrObservationError(errorMessage(error));
    } finally {
      setIsUsKrObservationLoading(false);
    }
  }, []);

  const loadMarketSignals = useCallback(async () => {
    setIsMarketSignalsLoading(true);
    setMarketSignalsError("");
    setMarketSignalsEvaluatedAt(null);
    try {
      const [transitionResult, currentResult] = await Promise.allSettled([
        repositories.marketSignals.todayTransitions(),
        repositories.marketSignals.currentStates(),
      ]);
      if (transitionResult.status === "rejected" && currentResult.status === "rejected") throw currentResult.reason;
      const todayTransitions = transitionResult.status === "fulfilled" ? transitionResult.value : { items: [], last_evaluated_at: null };
      const currentStates = currentResult.status === "fulfilled" ? currentResult.value : todayTransitions;
      const rows = selectMeaningfulMarketSignals(currentStates.items, todayTransitions.items).slice(0, 5);
      setMarketSignals(rows);
      setMarketSignalsEvaluatedAt(currentStates.last_evaluated_at ?? todayTransitions.last_evaluated_at ?? null);
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

  const loadInsight = useCallback(async (force = false) => {
    const controller = new AbortController();
    setInsightError("");
    try {
      const nextInsight = await repositories.drctInsight.today(controller.signal, force);
      setInsight((currentInsight) => {
        if (currentInsight?.summary.last_updated_at
          && currentInsight.summary.last_updated_at !== nextInsight.summary.last_updated_at) {
          previousInsightSnapshotRef.current = currentInsight;
        }
        return nextInsight;
      });
    } catch (error) {
      if (!controller.signal.aborted) setInsightError(errorMessage(error));
    }
    return () => controller.abort();
  }, []);

  const loadPerformance = useCallback(async () => {
    setIsPerformanceLoading(true);
    setPerformanceError("");
    try {
      setPerformance(await repositories.drctInsight.evaluations({ period: "20", page: 1, page_size: 20 }));
    } catch (error) {
      setPerformanceError(errorMessage(error));
    } finally {
      setIsPerformanceLoading(false);
    }
  }, []);

  const loadReviewBriefing = useCallback(async () => {
    setIsReviewBriefingLoading(true);
    setReviewBriefingError("");
    const today = todayInKst();
    const [newsResult, telegramResult, disclosureResult] = await Promise.allSettled([
      repositories.news.listNewsPage({ limit: 3, offset: 0 }),
      repositories.telegram.listItems({ collection_date: today, limit: 3, offset: 0 }),
      repositories.disclosures.listDisclosures({ limit: 3, offset: 0 }),
    ]);
    setReviewBriefing({
      news: newsResult.status === "fulfilled" ? newsResult.value.items : [],
      newsTotal: newsResult.status === "fulfilled" ? newsResult.value.total_count : null,
      telegram: telegramResult.status === "fulfilled" ? telegramResult.value.items : [],
      telegramTotal: telegramResult.status === "fulfilled" ? telegramResult.value.total_count : null,
      disclosures: disclosureResult.status === "fulfilled" ? disclosureResult.value : [],
    });
    if ([newsResult, telegramResult, disclosureResult].every((result) => result.status === "rejected")) setReviewBriefingError("장후 소식 요약을 불러오지 못했습니다.");
    setIsReviewBriefingLoading(false);
  }, []);

  const loadReviewSupply = useCallback(async () => {
    setReviewSupplyError("");
    try {
      setReviewSupply(await repositories.marketTrends.getDailyThemeFlow({ trade_date: todayInKst(), only_supply_theme: true }));
    } catch (error) {
      setReviewSupplyError(errorMessage(error));
    }
  }, []);

  useEffect(() => () => {
    themePollingTokenRef.current += 1;
    setRealtimeThemeSuspended(false);
  }, []);

  useEffect(() => {
    if (activeStage === "plan") {
      setRealtimeThemeSuspended(true);
      void Promise.all([loadReadiness(), loadUsThemeSummary(), loadUsKrObservation(), loadMarketSignals(), loadUpcomingCalendar(), loadObservationSummary(), loadInsight(), loadThemeSummary()]);
      return;
    }
    if (activeStage === "verify") {
      setRealtimeThemeSuspended(false);
      void Promise.all([ensureRealtimeThemeSnapshot(), loadThemeSummary()]);
      return;
    }
    setRealtimeThemeSuspended(true);
    void Promise.all([loadThemeSummary(), loadInsight(), loadPerformance(), loadReviewBriefing(), loadReviewSupply()]);
  }, [activeStage, loadInsight, loadMarketSignals, loadObservationSummary, loadPerformance, loadReadiness, loadReviewBriefing, loadReviewSupply, loadThemeSummary, loadUpcomingCalendar, loadUsKrObservation, loadUsThemeSummary]);

  useEffect(() => {
    const snapshotAt = realtimeThemeScheduler.snapshot.snapshot_at;
    if (activeStage !== "verify" || !snapshotAt) return;
    void loadInsight(true);
  }, [activeStage, loadInsight, realtimeThemeScheduler.snapshot.snapshot_at]);

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
    if (activeStage === "plan") {
      setChartSidcode(createNaverChartSidcode());
      await Promise.all([loadReadiness(true), loadUsThemeSummary(), loadUsKrObservation(), loadThemeSummary(), loadMarketSignals(), loadUpcomingCalendar(), loadObservationSummary(), loadInsight()]);
    }
    if (activeStage === "verify") await Promise.all([refreshRealtimeTheme(), loadThemeSummary()]);
    if (activeStage === "review") await Promise.all([loadThemeSummary(), loadInsight(), loadPerformance(), loadReviewBriefing(), loadReviewSupply()]);
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
      await Promise.all([loadUsThemeSummary(), loadUsKrObservation()]);
    } catch (error) {
      const message = errorMessage(error);
      setUsThemeError(message);
      setUsThemeFeedback({ tone: "error", message });
    } finally {
      setIsUsThemeRunning(false);
    }
  };

  const observationTargetDateError = () => {
    if (!observationTargetDate) return "신호 대상일을 선택해 주세요.";
    const day = new Date(`${observationTargetDate}T00:00:00`).getDay();
    if (day === 0 || day === 6) return "신호 대상일은 평일이어야 합니다.";
    if (themeReadiness?.dataDate && observationTargetDate <= themeReadiness.dataDate) {
      return "신호 대상일은 데이터 기준일 이후의 평일이어야 합니다.";
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
      setObservationCalculationFeedback(`${result.run?.target_date ?? observationTargetDate} 가격·수급 신호 계산 완료`);
      setObservationCalculationOpen(false);
      await Promise.all([
        loadObservationSummary(),
        ...(refreshMarketIndicators ? [loadReadiness(true), loadMarketSignals()] : []),
      ]);
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
  const realtimeRows = [...realtimeThemeScheduler.snapshot.themes]
    .filter((row) => row.theme_strength != null && Number.isFinite(row.theme_strength))
    .sort((a, b) => Number(b.theme_strength) - Number(a.theme_strength) || a.theme_name.localeCompare(b.theme_name, "ko-KR"))
    .slice(0, 12);
  const focusThemes = (insight?.themes ?? []).filter((row) => row.focus_candidate_count > 0);
  const focusThemeIds = new Set(focusThemes.map((row) => row.theme_id));
  const selectedRealtimeContext = themeDetailRequest?.realtime ? (() => {
    const live = realtimeRows.find((row) => row.theme_id === themeDetailRequest.themeId);
    return live ? { ...themeDetailRequest.realtime, themeName: live.theme_name, rank: realtimeRows.findIndex((row) => row.theme_id === live.theme_id) + 1, strength: live.theme_strength, validStockCount: live.valid_stock_count, linkedStockCount: live.linked_stock_count, snapshotAt: realtimeThemeScheduler.snapshot.snapshot_at } : themeDetailRequest.realtime;
  })() : undefined;
  const selectedRealtimeTheme = themeDetailRequest?.realtime
    ? realtimeThemeScheduler.snapshot.themes.find((row) => row.theme_id === themeDetailRequest.themeId) ?? null
    : null;
  const selectedRealtimeMetricValue = realtimeThemeDetailMetric === "strength"
    ? selectedRealtimeTheme?.theme_strength ?? selectedRealtimeContext?.strength ?? null
    : selectedRealtimeTheme?.avg_change_rate ?? realtimeThemeDetail?.theme_change_rate ?? null;
  const selectedRealtimeMetricRank = themeDetailRequest?.realtime ? (() => {
    const metricValue = (row: RealtimeThemeRows[number]) => realtimeThemeDetailMetric === "strength" ? row.theme_strength : row.avg_change_rate;
    const ranked = [...realtimeThemeScheduler.snapshot.themes]
      .filter((row) => metricValue(row) != null && Number.isFinite(metricValue(row)))
      .sort((a, b) => Number(metricValue(b)) - Number(metricValue(a)) || a.theme_name.localeCompare(b.theme_name, "ko-KR"));
    const rank = ranked.findIndex((row) => row.theme_id === themeDetailRequest.themeId);
    return rank >= 0 ? rank + 1 : selectedRealtimeContext?.rank ?? null;
  })() : null;
  const reviewThemeRows = [
    ...focusThemes.map((theme) => {
      const actual = themeSummary?.topGainers.find((row) => row.themeId === theme.theme_id);
      const closeRank = actual ? (themeSummary?.topGainers.findIndex((row) => row.themeId === theme.theme_id) ?? -1) + 1 : null;
      const tone = closeRank == null ? "weakened" : closeRank <= 6 ? "confirmed" : "partial";
      const verdict = tone === "confirmed" ? "✓ 확인" : tone === "partial" ? "△ 부분확인" : "✕ 약화";
      return { id: theme.theme_id, name: theme.theme_name, premarket: insightThemeLead(theme), intraday: theme.theme_strength == null ? "장중 데이터 대기" : `${theme.theme_strength > 0 ? "강세" : "약화"} · ${formatSignedPercent(theme.theme_strength)} · 확산 ${theme.valid_stock_count}/${theme.linked_stock_count}`, close: actual ? `#${closeRank} · ${formatSignedPercent(actual.dailyReturn)}` : "상위권 이탈", value: actual?.dailyReturn ?? null, verdict, tone };
    }),
    ...(themeSummary?.topGainers ?? []).slice(0, 6).filter((row) => !focusThemeIds.has(row.themeId)).slice(0, 3).map((row) => ({ id: row.themeId, name: row.themeName, premarket: "집중 대상 아님", intraday: "장중 신규 부상", close: `#${(themeSummary?.topGainers.findIndex((item) => item.themeId === row.themeId) ?? -1) + 1} · ${formatSignedPercent(row.dailyReturn)}`, value: row.dailyReturn, verdict: "NEW 신규발견", tone: "new" })),
  ];
  const reviewCounts = {
    focus: focusThemes.length,
    confirmed: reviewThemeRows.filter((row) => row.tone === "confirmed").length,
    partial: reviewThemeRows.filter((row) => row.tone === "partial").length,
    weakened: reviewThemeRows.filter((row) => row.tone === "weakened").length,
    new: reviewThemeRows.filter((row) => row.tone === "new").length,
  };
  const currentStage = stageMeta[activeStage];
  const openInsightTheme = (themeId: number) => {
    const theme = insight?.themes.find((row) => row.theme_id === themeId);
    setInsightStockDetail(null);
    setThemeDetailRequest({
      themeId,
      dataDate: themeSummary?.dataDate ?? insight?.analysis_date ?? null,
      realtime: theme?.realtime_snapshot_at ? {
        themeName: theme.theme_name,
        rank: theme.realtime_rank,
        strength: theme.theme_strength,
        validStockCount: theme.up_count,
        linkedStockCount: theme.valid_stock_count,
        snapshotAt: theme.realtime_snapshot_at,
        hypothesis: theme.insight_status === "NEW" ? "NEW" : ["WEAKENING", "MISMATCH"].includes(theme.insight_status) ? "WEAKENING" : "CONFIRMED",
      } : undefined,
    });
  };
  const openInsightStock = (stock: DrctInsightStock) => {
    setThemeDetailRequest(null);
    setInsightStockTab(activeStage === "verify" ? "pattern" : "summary");
    setInsightStockDetail(stock);
  };
  const realtimeThemeTop12Panel = activeStage === "verify" ? <RealtimeThemeRankPanel
    rows={realtimeThemeScheduler.snapshot.themes}
    snapshotAt={realtimeThemeScheduler.snapshot.snapshot_at}
    intervalMinutes={realtimeThemeScheduler.intervalMinutes}
    loading={realtimeThemeScheduler.isRefreshing && !realtimeThemeScheduler.snapshot.snapshot_at}
    error={realtimeThemeScheduler.error ?? ""}
    onRetry={() => void ensureRealtimeThemeSnapshot()}
    onOpenTheme={openInsightTheme}
    onOpenAll={() => navigate("/realtime-theme-treemap")}
  /> : null;
  const todayInsightPanel = <TodayInsightPanel stage={activeStage} insight={insight} previousInsight={previousInsightSnapshotRef.current} themeSummary={themeSummary} reviewCounts={reviewCounts} reviewRows={reviewThemeRows} failed={Boolean(insightError)} realtimeThemePanel={realtimeThemeTop12Panel} onOpen={() => navigate("/drct-insight")} onOpenTheme={openInsightTheme} onOpenStock={openInsightStock} />;

  return (
    <div className={`space-y-4 dashboard-v2 dashboard-routine dashboard-stage-${activeStage}`}>
      <div className="dashboard-routine-topbar">
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

        <SectionCard className="dashboard-routine-nav">
          <div className="dashboard-routine-tabs" role="tablist" aria-label="매매 루틴 단계">
            {(Object.keys(stageMeta) as DashboardStage[]).map((stage, index) => {
              const item = stageMeta[stage];
              return <button key={stage} type="button" role="tab" aria-selected={activeStage === stage} className={activeStage === stage ? "is-active" : ""} onClick={() => setActiveStage(stage)}><small>{item.number} · {item.title}</small><strong>{item.kicker}</strong><span>{index < 2 ? "→" : ""}</span></button>;
            })}
          </div>
          <div className="dashboard-routine-nav-copy">
            <p>{currentStage.description}</p>
          </div>
        </SectionCard>
      </div>

      {activeStage === "review" ? todayInsightPanel : null}

      {activeStage === "plan" ? <SectionCard className="dashboard-v2-indicator-section dashboard-routine-indicators">
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
      </SectionCard> : null}

      {activeStage === "plan" ? <SectionCard className="dashboard-v2-readiness-section">
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
              <div><span className="dashboard-v2-operation-eyebrow">PRICE × FLOW</span><h4>D+1 테마 후보(가격·수급)</h4></div>
              <StatusBadge label="D+1" tone="blue" />
            </div>
            <div className="dashboard-v2-observation-action-row">
              <label className="dashboard-v2-observation-date">
                <span>신호 대상일</span>
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
                {isObservationCalculating ? "신호 계산 중..." : "D+1 신호 계산"}
              </button>
            </div>
            {observationCalculationFeedback ? <p className="dashboard-v2-feedback success dashboard-v2-observation-feedback">{observationCalculationFeedback}</p> : null}
            {observationCalculationError ? <p className="dashboard-v2-feedback error dashboard-v2-observation-feedback">{observationCalculationError}</p> : null}
          </article>

        </div>
      </SectionCard> : null}

      {activeStage === "plan" ? <SectionCard className="dashboard-v3-market-check-section dashboard-routine-market-check">
        <div className="dashboard-v2-section-heading dashboard-v3-market-check-heading">
          <div>
            <h3 className="section-title">시장 : 오늘의 시장 체크</h3>
            <p>시장 변화 신호와 앞으로 예정된 주요 일정을 확인합니다.</p>
          </div>
        </div>
        <div className="dashboard-v3-market-check-grid">
          <article className="dashboard-v3-check-panel">
            <header>
              <div><h4>시장 변화 신호</h4><p className="dashboard-v3-signal-header-info"><span>평가 기준 {formatMarketSignalEvaluationDate(marketSignalsEvaluatedAt)}</span><span>추세 유지 상태를 제외한 현재 신호입니다.</span></p></div>
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
                    <span className={`dashboard-v3-signal-icon ${marketSignalTone(signal.current_state)}`} aria-hidden="true" />
                    <span className="dashboard-v3-signal-copy">
                      <strong>{signal.title || signal.signal_code || "시장 신호"}</strong>
                      <small>{signal.missing_reason || signal.explanation || `기준 ${signal.effective_date || "확인 중"}`}</small>
                    </span>
                    <span className={`dashboard-v3-state-badge ${marketSignalTone(signal.current_state)}`}>{signal.isTodayTransition ? "오늘 전환 · " : ""}{marketSignalStateLabel(signal.current_state)}</span>
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
      </SectionCard> : null}

      {activeStage === "plan" ? <UsKrLeadObservationPanel
        observation={usKrObservation}
        d1={observationSummary}
        insight={insight}
        usSummary={usThemeSummary}
        loading={isUsKrObservationLoading || isUsThemeSummaryLoading || isObservationLoading}
        error={usKrObservationError || usThemeError || observationError}
        onRetry={() => void Promise.all([loadUsKrObservation(), loadUsThemeSummary(), loadObservationSummary()])}
        onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: observationSummary?.run?.data_cutoff_date ?? null })}
        onOpenAll={() => navigate("/market-themes?window=0&metric=theme_strength&direction=ALL&market=us&scope=compare&section=watch")}
      /> : null}

      {activeStage === "plan" ? <CloseThemeTop12Panel
        rows={themeSummary?.topGainers ?? []}
        dataDate={themeSummary?.dataDate ?? null}
        loading={isThemeSummaryLoading}
        error={themeSummaryError}
        onRetry={() => void loadThemeSummary()}
        onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: themeSummary?.dataDate ?? null })}
        onOpenAll={() => navigate("/market-themes")}
      /> : null}

      {activeStage === "plan" ? <SectionCard className="dashboard-v4-observation-section dashboard-routine-observation">
        <div className="dashboard-v2-section-heading dashboard-v4-section-heading">
          <div>
            <h3 className="section-title">테마/종목 : 오늘의 국내 테마 신호</h3>
            <p>가격·수급 단계와 D+1 상대강세 후보를 확인합니다.</p>
          </div>
        </div>
        <div className="dashboard-v4-grid">
          <article className="dashboard-v4-panel">
            <header>
              <div><h4>D+1 테마 후보(가격·수급)</h4><p>저장된 최신 D+1 후보 Top4</p></div>
              {observationSummary?.run ? <span>{observationDateLabel(observationSummary.run.target_date)}</span> : null}
            </header>
            {isObservationLoading ? (
              <div className="dashboard-v4-radar-skeleton" aria-label="D+1 테마 후보(가격·수급) 불러오는 중">{[0, 1, 2, 3].map((index) => <i key={index} />)}</div>
            ) : observationError ? (
              <div className="dashboard-v4-state error"><p>D+1 테마 후보(가격·수급)를 불러오지 못했습니다.</p><button type="button" className="btn btn-secondary" onClick={() => void loadObservationSummary()}>다시 시도</button></div>
            ) : observationSummary?.run && observationSummary.items.length ? (
              <div className="dashboard-v4-radar-wrap">
                <ObservationRadarGrid
                  items={observationSummary.items.slice(0, 4)}
                  statusNames={OBSERVATION_STATE_LABELS}
                  onThemeClick={(themeId) => navigate(`/market-themes?view=prediction&target_date=${observationSummary.run!.target_date}&theme_id=${themeId}`)}
                />
                <button type="button" className="dashboard-v4-footer-button" onClick={() => navigate("/market-themes?view=prediction")}>전체 테마 신호 보기</button>
              </div>
            ) : (
              <div className="dashboard-v4-state"><p>저장된 D+1 테마 신호가 없습니다.</p><button type="button" className="btn btn-secondary" onClick={() => navigate("/market-themes?view=prediction")}>테마 신호 화면으로 이동</button></div>
            )}
          </article>
        </div>
      </SectionCard> : null}

      {activeStage !== "review" ? todayInsightPanel : null}

      {activeStage === "review" ? <PostMarketReviewWorkspace
        insight={insight}
        rows={reviewThemeRows}
        counts={reviewCounts}
        supply={reviewSupply}
        supplyError={reviewSupplyError}
        onRetrySupply={() => void loadReviewSupply()}
        onOpenTheme={openInsightTheme}
        onOpenStock={openInsightStock}
        onOpenSupply={() => navigate("/market-trends")}
        onOpenHistory={() => navigate("/drct-insight?view=performance")}
      /> : null}

      {activeStage === "review" ? <SectionCard className="dashboard-routine-catalyst">
        <div className="dashboard-v2-section-heading"><div><h3 className="section-title">오늘의 주요 소식</h3><p>장후 복기에 필요한 최신 텔레그램·뉴스·공시 제목만 모았습니다.</p></div><span>채널별 최대 3건</span></div>
        {reviewBriefingError ? <div className="dashboard-review-state error"><span>{reviewBriefingError}</span><button type="button" onClick={() => void loadReviewBriefing()}>다시 시도</button></div> : isReviewBriefingLoading && !reviewBriefing ? <div className="dashboard-review-state">주요 소식을 불러오는 중입니다.</div> : <div className="dashboard-catalyst-grid">
          <article><header><div><span>TELEGRAM</span><strong>텔레그램</strong></div><button type="button" onClick={() => navigate("/telegram-briefing")}>전체 보기 →</button></header>{reviewBriefing?.telegram.length ? <ul>{reviewBriefing.telegram.map((item) => <li key={item.id}><button type="button" onClick={() => navigate("/telegram-briefing")}><strong>{item.title}</strong><small>{item.message_at.slice(0, 16).replace("T", " ")}</small></button></li>)}</ul> : <p>오늘 수집된 텔레그램 제목이 없습니다.</p>}</article>
          <article><header><div><span>NEWS</span><strong>뉴스</strong></div><button type="button" onClick={() => navigate("/news")}>전체 보기 →</button></header>{reviewBriefing?.news.length ? <ul>{reviewBriefing.news.map((item) => <li key={item.id}><button type="button" onClick={() => navigate("/news")}><strong>{item.title}</strong><small>{(item.published_at ?? item.collected_at).slice(0, 16).replace("T", " ")}</small></button></li>)}</ul> : <p>최근 뉴스 제목이 없습니다.</p>}</article>
          <article><header><div><span>DISCLOSURE</span><strong>공시</strong></div><button type="button" onClick={() => navigate("/disclosures")}>전체 보기 →</button></header>{reviewBriefing?.disclosures.length ? <ul>{reviewBriefing.disclosures.map((item) => <li key={item.id}><button type="button" onClick={() => navigate("/disclosures")}><strong>{item.disclosure_title}</strong><small>{item.stock_name ?? item.stock_code ?? "종목 미지정"}{item.disclosed_at ? ` · ${item.disclosed_at.slice(0, 16).replace("T", " ")}` : ""}</small></button></li>)}</ul> : <p>최근 공시 제목이 없습니다.</p>}</article>
        </div>}
      </SectionCard> : null}

      {activeStage === "review" ? <SectionCard className="dashboard-routine-performance">
        <div className="dashboard-v2-section-heading"><div><h3 className="section-title">후보 성과</h3><p>최근 20거래일의 집중·검증 후보 평가 결과입니다.</p></div><button type="button" className="dashboard-v2-text-button" onClick={() => navigate("/drct-insight?view=performance")}>후보 성과 열기 →</button></div>
        {isPerformanceLoading && !performance ? <div className="dashboard-performance-state">후보 성과를 불러오는 중입니다.</div> : performanceError ? <div className="dashboard-performance-state error">후보 성과를 불러오지 못했습니다.<button type="button" onClick={() => void loadPerformance()}>다시 시도</button></div> : <div className="dashboard-performance-summary">
          {([['D0', performance?.summary.d0], ['D+1', performance?.summary.d1], ['D+3', performance?.summary.d3], ['D+5', performance?.summary.d5]] as const).map(([label, metric]) => <div className={directionCardClass(metric?.mean ?? null)} key={label}><span>{label}</span><strong>{metric?.mean == null ? "대기" : formatSignedPercent(metric.mean)}</strong><small>{metric?.n ? `${metric.n}건` : "평가 대기"}</small></div>)}
          <dl><div><dt>평가 진행</dt><dd>{((performance?.summary.pending_count ?? 0) + (performance?.summary.partial_count ?? 0)).toLocaleString()}</dd></div><div><dt>완료</dt><dd>{(performance?.summary.complete_count ?? 0).toLocaleString()}</dd></div></dl>
        </div>}
      </SectionCard> : null}

      {themeDetailRequest?.realtime ? <RealtimeThemeDetailDrawer
        open
        data={realtimeThemeDetail}
        loading={isRealtimeThemeDetailLoading}
        error={realtimeThemeDetailError || null}
        metric={realtimeThemeDetailMetric}
        metricLabel={realtimeThemeDetailMetric === "strength" ? "테마강도" : "단순평균"}
        metricValue={selectedRealtimeMetricValue}
        metricRank={selectedRealtimeMetricRank}
        onMetricChange={setRealtimeThemeDetailMetric}
        onClose={() => setThemeDetailRequest(null)}
        onRetry={() => void loadRealtimeThemeDetail(themeDetailRequest.themeId, true)}
      /> : <MarketThemeDetailDrawer
        open={Boolean(themeDetailRequest)}
        themeId={themeDetailRequest?.themeId ?? null}
        dataDate={themeDetailRequest?.dataDate}
        onClose={() => setThemeDetailRequest(null)}
      />}
      {insightStockDetail ? <InsightDrawer
        stock={insightStockDetail}
        view={dashboardStockView(insightStockDetail)}
        postMarket={activeStage === "review"}
        analysisDate={insight?.analysis_date ?? null}
        realtimeStatus={insight?.readiness.realtime.status ?? "NOT_READY"}
        loading={false}
        tab={insightStockTab}
        onTab={setInsightStockTab}
        onRefresh={() => void loadInsight()}
        onClose={() => setInsightStockDetail(null)}
      /> : null}

      {observationCalculationOpen ? (
        <div className="theme-observation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !isObservationCalculating) setObservationCalculationOpen(false); }}>
          <section className="theme-observation-modal" role="dialog" aria-modal="true" aria-labelledby="dashboard-market-refresh-choice-title">
            <header>
              <div><small>D+1 신호 계산</small><h3 id="dashboard-market-refresh-choice-title">시장지표를 갱신하고 계산할까요?</h3></div>
              <button type="button" aria-label="닫기" disabled={isObservationCalculating} onClick={() => setObservationCalculationOpen(false)}>×</button>
            </header>
            <p>직전 신호를 최신 실측으로 먼저 검증한 뒤 D+1 가격·수급 신호를 계산합니다. 최신 시장환경 반영 여부를 선택해 주세요.</p>
            <dl>
              <dt>현재 시장지표 최근 갱신</dt><dd>{formatDateTime(observationSummary?.market_indicator_latest_refreshed_at ?? null)}</dd>
              <dt>테마·종목 기준일</dt><dd>{themeReadiness?.dataDate ?? "-"}</dd>
              <dt>신호 대상일</dt><dd>{observationTargetDate}</dd>
            </dl>
            {isObservationCalculating ? <div className="theme-observation-modal-progress" role="status">최근 신호 검증과 D+1 가격·수급 신호 계산을 진행하고 있습니다...</div> : null}
            <div className="theme-observation-modal-actions">
              <button className="btn btn-secondary" type="button" disabled={isObservationCalculating} onClick={() => void handleObservationCalculation(false)}>현재 지표로 계산</button>
              <button className="btn btn-primary" type="button" disabled={isObservationCalculating} onClick={() => void handleObservationCalculation(true)}>전체지표 갱신 후 계산<small>시장지표 전체갱신 후 D+1 신호를 계산합니다.</small></button>
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
