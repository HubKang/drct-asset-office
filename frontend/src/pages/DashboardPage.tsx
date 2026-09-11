import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import MarketThemeDetailDrawer from "@/components/marketThemes/MarketThemeDetailDrawer";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";
import { InsightDrawer, type DrawerTab, type IntradayView } from "@/pages/DrctInsightPage";
import { repositories } from "@/services";
import {
  ensureRealtimeThemeSnapshot,
  getRealtimeThemeSchedulerState,
  setRealtimeThemeSuspended,
  subscribeRealtimeThemeScheduler,
} from "@/services/realtimeThemeScheduler";
import type { CollectionRun } from "@/types/collectionRun";
import type { MarketDataCollectionRun } from "@/types/marketData";
import type { MarketCalendarEvent, MarketCalendarImportance } from "@/types/marketCalendar";
import type { UsThemeDashboardSummary } from "@/types/usMarketTheme";
import type { DrctInsightPerformance, DrctInsightStock, DrctInsightToday } from "@/types/drctInsight";
import type { NewsItem } from "@/types/news";
import type { TelegramItem } from "@/types/telegram";
import type { Disclosure } from "@/types/disclosure";
import type { DailyThemeFlowResponse } from "@/types/marketTrend";
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
const THEME_FLOW_COLLECTOR = "market_theme_price_flow_refresh";

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

function TodayInsightPanel({ stage, insight, themeSummary, realtimeRows, snapshotAt, reviewCounts, reviewRows, performance, failed, onOpen, onOpenTheme, onOpenStock }: {
  stage: DashboardStage;
  insight: DrctInsightToday | null;
  themeSummary: ThemeSummaryData | null;
  realtimeRows: RealtimeThemeRows;
  snapshotAt: string | null;
  reviewCounts?: { focus: number; confirmed: number; partial: number; weakened: number; new: number };
  reviewRows?: Array<{ id: number; name: string; close: string; value?: number | null; verdict: string; tone: string }>;
  performance?: DrctInsightPerformance | null;
  failed: boolean;
  onOpen: () => void;
  onOpenTheme: (themeId: number) => void;
  onOpenStock: (stock: DrctInsightStock) => void;
}) {
  const focusThemes = (insight?.themes ?? [])
    .filter((row) => row.focus_candidate_count > 0)
    .sort((a, b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999));
  const displayedThemes = focusThemes.slice(0, 3);
  const focusStocks = (insight?.stocks ?? [])
    .filter((row) => row.focus_candidate)
    .sort((a, b) => (a.focus_rank ?? 999) - (b.focus_rank ?? 999))
    .slice(0, 4);
  const liveByTheme = new Map(realtimeRows.map((row, index) => [row.theme_id, { ...row, rank: index + 1 }]));
  const focusThemeIds = new Set(focusThemes.map((row) => row.theme_id));
  const confirmedCount = focusThemes.filter((row) => Number(liveByTheme.get(row.theme_id)?.theme_strength) > 0).length;
  const weakenedCount = Math.max(0, focusThemes.length - confirmedCount);
  const surpriseThemes = realtimeRows.filter((row) => !focusThemeIds.has(row.theme_id) && Number(row.theme_strength) > 0).slice(0, 3);
  const relativeStrongCount = focusStocks.filter((row) => (row.relative_strength ?? 0) > 0).length;
  const selectedNames = focusThemes.slice(0, 2).map((row) => row.theme_name).join(" · ") || "상위 관찰 테마";
  const sourceDate = themeSummary?.dataDate ?? insight?.analysis_date ?? "확인 중";
  const sourceLabel = stage === "plan"
    ? `전일 종가 기준 ${sourceDate}`
    : snapshotAt ? `실시간 Snapshot ${snapshotAt.slice(0, 19).replace("T", " ")}` : "실시간 Snapshot 대기 중";
  const stockSignal = (stock: DrctInsightToday["stocks"][number]) => {
    if (stock.gates.execution === "INVALID") return { label: "! 주의", tone: "warning" };
    if ((stock.relative_strength ?? 0) > 0) return { label: "▲ 강화", tone: "up" };
    if ((stock.relative_strength ?? 0) < 0) return { label: "▼ 약화", tone: "down" };
    return { label: "→ 유지", tone: "stable" };
  };

  if (stage === "review") {
    const counts = reviewCounts ?? { focus: focusThemes.length, confirmed: 0, partial: 0, weakened: 0, new: 0 };
    const outcome = insight?.outcome_summary;
    return <SectionCard className="dashboard-insight-panel dashboard-routine-insight dashboard-stage-insight is-review">
      <div className="dashboard-insight-head"><div><small>REVIEW · ACTUAL</small><h3>DrCT 오늘의 결과</h3></div><div className="dashboard-insight-head-tools"><span>종가 기준 {themeSummary?.dataDate ?? insight?.analysis_date ?? "확인 중"}</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>상세 →</button></div></div>
      {failed ? <p className="dashboard-insight-error">인사이트 요약을 불러오지 못했습니다.</p> : <>
        <section className="dashboard-insight-decision"><span>오늘의 결론</span><strong>장전 집중 {counts.focus}개 중 {counts.confirmed}개 확인 · {counts.partial}개 부분 · {counts.weakened}개 약화</strong><p>장중 신규 발견 {counts.new}개 · Focus 평균 D0 {formatSignedPercent(outcome?.average_d0_return ?? null)}</p></section>
        <div className="dashboard-insight-strip" aria-label="장후 결과 요약"><span className="is-confirmed">확인 <b>{counts.confirmed}</b></span><span>부분 <b>{counts.partial}</b></span><span className="is-weakened">약화 <b>{counts.weakened}</b></span><span className="is-new">NEW <b>{counts.new}</b></span><span className="is-key">Focus D0 <b>{formatSignedPercent(outcome?.average_d0_return ?? null)}</b></span></div>
        <div className="dashboard-insight-columns dashboard-insight-review-columns">
          <article className="dashboard-insight-signal-list"><header><div><h4>가설 결과 Top3</h4><p>종가 기준 최종 판정</p></div><span>{counts.focus}개</span></header><div>{reviewRows?.slice(0, 3).map((row) => { const [rank, change] = row.close.split(" · "); return <button type="button" className="dashboard-insight-review-row" key={`${row.tone}-${row.id}`} onClick={() => onOpenTheme(row.id)}><strong>{row.name}</strong><span className="dashboard-insight-review-result">{change ? <small>{rank}</small> : null}<b className={row.value == null ? "is-neutral" : row.value >= 0 ? "is-up" : "is-down"}>{change ?? row.close}</b></span><em className={`is-${row.tone}`}>{row.verdict}</em></button>; })}</div></article>
          <article className="dashboard-insight-signal-list"><header><div><h4>후보성과</h4><p>최근 20거래일 평균</p></div><span>D0~D+5</span></header><div className="dashboard-insight-outcome-row">{([['D0', performance?.summary.d0], ['D+1', performance?.summary.d1], ['D+3', performance?.summary.d3], ['D+5', performance?.summary.d5]] as const).map(([label, metric]) => <div key={label}><span>{label}</span><strong className={(metric?.mean ?? 0) >= 0 ? "is-up" : "is-down"}>{metric?.mean == null ? "대기" : formatSignedPercent(metric.mean)}</strong><small>{metric?.n ? `${metric.n}건` : "평가 대기"}</small></div>)}</div></article>
        </div>
        <footer className="dashboard-insight-review-footer"><span>상세 가설 리뷰와 후보성과는 아래 영역에서 확인합니다.</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>인사이트 상세 →</button></footer>
      </>}
    </SectionCard>;
  }

  return <SectionCard className={`dashboard-insight-panel dashboard-routine-insight dashboard-stage-insight is-${stage}`}>
    <div className="dashboard-insight-head">
      <div><small>{stage === "plan" ? "PLAN · PREVIOUS CLOSE" : "VERIFY · LIVE SNAPSHOT"}</small><h3>{stage === "plan" ? "DrCT 오늘의 인사이트" : "DrCT 실시간 인사이트"}</h3></div>
      <div className="dashboard-insight-head-tools"><span>{sourceLabel}</span><button type="button" className="dashboard-v2-text-button" onClick={onOpen}>인사이트 열기 →</button></div>
    </div>
    {failed ? <p className="dashboard-insight-error">인사이트 요약을 불러오지 못했습니다.</p> : <>
      <section className="dashboard-insight-decision">
        <span>{stage === "plan" ? "오늘의 판단" : "현재 판단"}</span>
        {stage === "plan" ? <><strong>{selectedNames}를 우선 관찰합니다.</strong><p>Focus {insight?.summary.focus_candidate_count ?? 0}종목을 준비하고, 장중에는 테마 강도·확산·종목 상대강도를 확인합니다.</p></> : <><strong>집중테마 {focusThemes.length}개 중 {confirmedCount}개 확인 · {weakenedCount}개 약화</strong><p>Focus {insight?.summary.focus_candidate_count ?? 0}종목 중 {relativeStrongCount}개가 현재 테마보다 강합니다.</p></>}
      </section>
      <div className="dashboard-insight-strip" aria-label={stage === "plan" ? "장전 준비 요약" : "장중 가설 검증 요약"}>
        {stage === "plan" ? <>
          <span>관찰 <b>{insight?.summary.observed_theme_count ?? "-"}</b></span><span className="is-key">집중테마 <b>{focusThemes.length}</b></span><span className="is-key">Focus <b>{insight?.summary.focus_candidate_count ?? "-"}</b></span><span>검증 <b>{insight?.summary.final_candidate_count ?? "-"}</b></span><span>내관찰 <b>{insight?.summary.my_watch_count ?? "-"}</b></span>
        </> : <>
          <span>집중테마 <b>{focusThemes.length}</b></span><span className="is-confirmed">가설 확인 <b>{confirmedCount}</b></span><span className="is-weakened">가설 약화 <b>{weakenedCount}</b></span><span className="is-new">신규 급부상 <b>{surpriseThemes.length}</b></span><span className="is-key">Focus 강세 <b>{relativeStrongCount}</b></span>
        </>}
      </div>
      <div className="dashboard-insight-columns">
        <article className="dashboard-insight-signal-list">
          <header><div><h4>{stage === "plan" ? "오늘 우선 볼 테마" : "장전 가설 vs 현재"}</h4><p>{stage === "plan" ? "전일 확정 데이터 기준" : "현재 실시간 강도 우선"}</p></div><span>{focusThemes.length}개</span></header>
          <div>{displayedThemes.length ? displayedThemes.map((theme, index) => {
            const close = themeSummary?.topGainers.find((row) => row.themeId === theme.theme_id);
            const live = liveByTheme.get(theme.theme_id);
            const confirmed = Number(live?.theme_strength) > 0;
            return <button type="button" className="dashboard-insight-theme-row" key={theme.theme_id} onClick={() => onOpenTheme(theme.theme_id)}>
              <div className="dashboard-insight-row-title"><span>#{theme.observation_rank ?? index + 1}</span><strong>{theme.theme_name}</strong>{stage === "plan" ? <em>Focus {theme.focus_candidate_count}</em> : <em className={confirmed ? "is-confirmed" : "is-weakened"}>{confirmed ? "✓ 확인" : "△ 약화"}</em>}</div>
              {stage === "plan" ? <><p>{insightThemeLead(theme).replace(`관찰 #${theme.observation_rank ?? "-"} · `, "")}</p><dl><div><dt>전일 종가</dt><dd className={(close?.dailyReturn ?? theme.change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>{formatSignedPercent(close?.dailyReturn ?? theme.change_rate)}</dd></div><div><dt>전일 확산</dt><dd>{theme.valid_stock_count}/{theme.linked_stock_count}</dd></div></dl></> : <dl className="is-compare"><div><dt>장전</dt><dd>관찰 #{theme.observation_rank ?? "-"} · 전일 {formatSignedPercent(close?.dailyReturn ?? theme.change_rate)} · 확산 {theme.valid_stock_count}/{theme.linked_stock_count}</dd></div><div><dt>현재</dt><dd className={(live?.theme_strength ?? 0) >= 0 ? "is-up" : "is-down"}>{live ? `실시간 #${live.rank} · 강도 ${formatSignedPercent(live.theme_strength)} · 확산 ${live.valid_stock_count}/${live.linked_stock_count}` : "실시간 Top12 순위 이탈"}</dd></div></dl>}
            </button>;
          }) : <p className="dashboard-insight-empty">현재 집중테마가 없습니다.</p>}</div>
          {focusThemes.length > displayedThemes.length ? <button type="button" className="dashboard-insight-all" onClick={onOpen}>집중테마 전체 {focusThemes.length} →</button> : null}
        </article>
        <article className="dashboard-insight-signal-list dashboard-insight-stock-list">
          <header><div><h4>{stage === "plan" ? "오늘 볼 Focus 종목" : "Focus 실시간 Signal"}</h4><p>{stage === "plan" ? "성공 유사도와 전일 종가" : "현재 등락과 테마 대비 강도"}</p></div><span>Top {focusStocks.length}</span></header>
          <div>{focusStocks.length ? focusStocks.map((stock) => {
            const signal = stockSignal(stock);
            return <button type="button" className="dashboard-insight-stock-row" key={stock.stock_id} onClick={() => onOpenStock(stock)}>
              <div><strong>{stock.stock_name}</strong><small>{stock.theme_name ?? "테마 미지정"}</small></div>
              <div className="dashboard-insight-similarity"><span>성공 유사 {Math.round(stock.success_similarity)}</span><i><b style={{ width: `${Math.max(0, Math.min(100, stock.success_similarity))}%` }} /></i></div>
              <b className={(stock.change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>{stage === "plan" ? "전일 " : "현재 "}{formatSignedPercent(stock.change_rate)}</b>
              {stage === "plan" ? <em>관찰</em> : <><span className={(stock.relative_strength ?? 0) >= 0 ? "is-up" : "is-down"}>테마 대비 {stock.relative_strength == null ? "대기" : `${formatSignedPercent(stock.relative_strength)}p`}</span><em className={`is-${signal.tone}`}>{signal.label}</em></>}
            </button>;
          }) : <p className="dashboard-insight-empty">현재 Focus 종목이 없습니다.</p>}</div>
          <button type="button" className="dashboard-insight-all" onClick={onOpen}>Focus 전체 {insight?.summary.focus_candidate_count ?? 0} →</button>
        </article>
      </div>
      {stage === "plan" ? <footer className="dashboard-insight-checks"><strong>장이 열리면 확인</strong><span>○ 집중테마가 실시간 강도 상위에 유지되는가</span><span>○ 상승 확산이 확대되는가</span><span>○ Focus 종목이 테마보다 강한가</span></footer> : <footer className="dashboard-insight-discovery"><strong>장중 신규 발견</strong>{surpriseThemes.length ? surpriseThemes.map((theme) => <button type="button" key={theme.theme_id} onClick={() => onOpenTheme(theme.theme_id)}><span>{theme.theme_name}</span><b className="is-up">{formatSignedPercent(theme.theme_strength)}</b><small>실시간 #{liveByTheme.get(theme.theme_id)?.rank} · 확산 {theme.valid_stock_count}/{theme.linked_stock_count}</small></button>) : <span>현재 신규 급부상 테마가 없습니다.</span>}<button type="button" className="dashboard-v2-text-button" onClick={onOpen}>실시간 상세 →</button></footer>}
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
                  <small>수집 {row.valid_stock_count}/{row.linked_stock_count}종목 · 단순평균 {formatSignedPercent(row.avg_change_rate)}</small>
                </span>
                <strong className={Number(row.theme_strength) >= 0 ? "dashboard-v2-return-value" : "dashboard-v2-realtime-negative-value"}>
                  {formatSignedPercent(row.theme_strength)}
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

function HypothesisThemeRow({ name, value, premarket, intraday, verdict, onOpen }: {
  name: string; value: number | null; premarket: string; intraday: string; verdict: string; onOpen: () => void;
}) {
  return <button type="button" className="dashboard-hypothesis-row" onClick={onOpen}>
    <div className="dashboard-hypothesis-row-head"><strong>{name}</strong><b className={(value ?? 0) > 0 ? "is-up" : (value ?? 0) < 0 ? "is-down" : "is-neutral"}>{formatSignedPercent(value)}</b></div>
    <dl><div><dt>장전</dt><dd>{premarket}</dd></div><div><dt>장중</dt><dd>{intraday}</dd></div><div><dt>판정</dt><dd>{verdict}</dd></div></dl>
  </button>;
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
  const [insightStockDetail, setInsightStockDetail] = useState<DrctInsightStock | null>(null);
  const [insightStockTab, setInsightStockTab] = useState<DrawerTab>("summary");
  const [insight, setInsight] = useState<DrctInsightToday | null>(() => repositories.drctInsight.peekToday());
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

  const loadInsight = useCallback(async () => {
    const controller = new AbortController();
    setInsightError("");
    try {
      setInsight(await repositories.drctInsight.today(controller.signal));
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
      void Promise.all([loadReadiness(), loadUsThemeSummary(), loadMarketSignals(), loadUpcomingCalendar(), loadObservationSummary(), loadInsight(), loadThemeSummary()]);
      return;
    }
    if (activeStage === "verify") {
      setRealtimeThemeSuspended(false);
      void Promise.all([ensureRealtimeThemeSnapshot(), loadInsight(), loadThemeSummary()]);
      return;
    }
    setRealtimeThemeSuspended(true);
    void Promise.all([loadThemeSummary(), loadInsight(), loadPerformance(), loadReviewBriefing(), loadReviewSupply()]);
  }, [activeStage, loadInsight, loadMarketSignals, loadObservationSummary, loadPerformance, loadReadiness, loadReviewBriefing, loadReviewSupply, loadThemeSummary, loadUpcomingCalendar, loadUsThemeSummary]);

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
      await Promise.all([loadReadiness(true), loadUsThemeSummary(), loadThemeSummary(), loadMarketSignals(), loadUpcomingCalendar(), loadObservationSummary(), loadInsight()]);
    }
    if (activeStage === "verify") await Promise.all([ensureRealtimeThemeSnapshot(), loadInsight(), loadThemeSummary()]);
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
  const realtimeRows = [...realtimeThemeScheduler.snapshot.themes]
    .filter((row) => row.theme_strength != null && Number.isFinite(row.theme_strength))
    .sort((a, b) => Number(b.theme_strength) - Number(a.theme_strength) || a.theme_name.localeCompare(b.theme_name, "ko-KR"))
    .slice(0, 12);
  const focusThemes = (insight?.themes ?? []).filter((row) => row.focus_candidate_count > 0);
  const focusThemeIds = new Set(focusThemes.map((row) => row.theme_id));
  const confirmedThemes = realtimeRows.filter((row) => focusThemeIds.has(row.theme_id) && Number(row.theme_strength) > 0);
  const weakenedThemes = focusThemes.filter((theme) => !confirmedThemes.some((row) => row.theme_id === theme.theme_id));
  const surpriseThemes = realtimeRows.filter((row) => !focusThemeIds.has(row.theme_id) && Number(row.theme_strength) > 0).slice(0, 5);
  const selectedRealtimeContext = themeDetailRequest?.realtime ? (() => {
    const live = realtimeRows.find((row) => row.theme_id === themeDetailRequest.themeId);
    return live ? { ...themeDetailRequest.realtime, themeName: live.theme_name, rank: realtimeRows.findIndex((row) => row.theme_id === live.theme_id) + 1, strength: live.theme_strength, validStockCount: live.valid_stock_count, linkedStockCount: live.linked_stock_count, snapshotAt: realtimeThemeScheduler.snapshot.snapshot_at } : themeDetailRequest.realtime;
  })() : undefined;
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
  const reviewValueTone = (value: string) => /\+\d/.test(value) ? "is-positive" : /-\d/.test(value) ? "is-negative" : "is-neutral";
  const reviewCounts = {
    focus: focusThemes.length,
    confirmed: reviewThemeRows.filter((row) => row.tone === "confirmed").length,
    partial: reviewThemeRows.filter((row) => row.tone === "partial").length,
    weakened: reviewThemeRows.filter((row) => row.tone === "weakened").length,
    new: reviewThemeRows.filter((row) => row.tone === "new").length,
  };
  const currentStage = stageMeta[activeStage];
  const todayInsightPanel = <TodayInsightPanel stage={activeStage} insight={insight} themeSummary={themeSummary} realtimeRows={realtimeRows} snapshotAt={realtimeThemeScheduler.snapshot.snapshot_at} reviewCounts={reviewCounts} reviewRows={reviewThemeRows} performance={performance} failed={Boolean(insightError)} onOpen={() => navigate("/drct-insight")} onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: themeSummary?.dataDate ?? null })} onOpenStock={(stock) => { setInsightStockTab("summary"); setInsightStockDetail(stock); }} />;

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

      {activeStage === "plan" ? <SectionCard className="dashboard-v2-theme-summary-section dashboard-routine-us-themes">
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
      </SectionCard> : null}

      {activeStage === "plan" ? <CloseThemeTop12Panel
        rows={themeSummary?.topGainers ?? []}
        dataDate={themeSummary?.dataDate ?? null}
        loading={isThemeSummaryLoading}
        error={themeSummaryError}
        onRetry={() => void loadThemeSummary()}
        onOpenTheme={(themeId) => setThemeDetailRequest({ themeId, dataDate: themeSummary?.dataDate ?? null })}
        onOpenAll={() => navigate("/market-themes")}
      /> : null}

      {activeStage === "verify" || activeStage === "review" ? <SectionCard className="dashboard-v2-theme-summary-section dashboard-routine-kr-themes">
        <div className="dashboard-v2-section-heading dashboard-v2-theme-summary-heading">
          <div>
            <h3 className="section-title">테마/종목 : 국내 테마 강도 순위</h3>
            <p>{activeStage === "review" ? "최신 거래일의 상승 강도와 최근 10일 상승 지속 강도를 확인합니다." : "실시간 Snapshot으로 현재 자금이 모이는 테마를 확인합니다."}</p>
          </div>
          <div className={`dashboard-v2-theme-summary-tools ${activeStage === "verify" ? "is-realtime" : ""}`}>
            <span>{activeStage === "review"
              ? themeSummary?.dataDate ? `국내 데이터 기준일 ${themeSummary.dataDate}` : "국내 데이터 기준일 확인 중"
              : realtimeThemeScheduler.snapshot.snapshot_at ? `Snapshot ${realtimeThemeScheduler.snapshot.snapshot_at.slice(0, 19).replace("T", " ")}` : "실시간 Snapshot 확인 중"}</span>
            <button type="button" className="dashboard-v2-text-button" onClick={() => navigate(activeStage === "verify" ? "/realtime-theme-treemap" : "/market-themes")}>{activeStage === "verify" ? "트리맵 열기" : "전체 보기"}</button>
          </div>
        </div>
        {activeStage === "review" ? (
          <div className="dashboard-v2-rank-grid">
            <ThemeRankPanel
              kind="gainers" rows={(themeSummary?.topGainers ?? []).slice(0, 6)} dataDate={themeSummary?.dataDate ?? themeReadiness?.dataDate ?? null}
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
        ) : (
          <RealtimeThemeRankPanel
            rows={realtimeThemeScheduler.snapshot.themes}
            snapshotAt={realtimeThemeScheduler.snapshot.snapshot_at}
            intervalMinutes={realtimeThemeScheduler.intervalMinutes}
            loading={realtimeThemeScheduler.isRefreshing && !realtimeThemeScheduler.snapshot.snapshot_at}
            error={realtimeThemeScheduler.error ?? ""}
            onRetry={() => void ensureRealtimeThemeSnapshot()}
            onOpenTheme={() => navigate("/realtime-theme-treemap")}
            onOpenAll={() => navigate("/realtime-theme-treemap")}
          />
        )}
      </SectionCard> : null}

      {activeStage === "verify" ? <SectionCard className="dashboard-routine-hypothesis">
        <div className="dashboard-v2-section-heading">
          <div><h3 className="section-title">오늘의 가설 검증</h3><p>Insight 집중테마와 현재 실시간 상위 Snapshot을 런타임에서 비교합니다.</p></div>
          <span>신규 저장 없음</span>
        </div>
        <div className="dashboard-hypothesis-grid">
          <article className="is-confirmed"><header><span>✓</span><div><strong>예상 + 실제 강세</strong><small>{confirmedThemes.length}개 확인</small></div></header><div className="dashboard-hypothesis-items">{confirmedThemes.length ? confirmedThemes.map((row) => { const theme = focusThemes.find((item) => item.theme_id === row.theme_id); const rank = realtimeRows.findIndex((item) => item.theme_id === row.theme_id) + 1; return <HypothesisThemeRow key={row.theme_id} name={row.theme_name} value={row.theme_strength} premarket={insightThemeLead(theme)} intraday={`실시간 #${rank} · 강도 ${formatSignedPercent(row.theme_strength)} · 확산 ${row.valid_stock_count}/${row.linked_stock_count}`} verdict="가설 확인" onOpen={() => setThemeDetailRequest({ themeId: row.theme_id, dataDate: themeSummary?.dataDate ?? null, realtime: { themeName: row.theme_name, rank, strength: row.theme_strength, validStockCount: row.valid_stock_count, linkedStockCount: row.linked_stock_count, snapshotAt: realtimeThemeScheduler.snapshot.snapshot_at, hypothesis: "CONFIRMED" } })} />; }) : <p>현재 상위권에서 확인된 집중테마가 없습니다.</p>}</div></article>
          <article className="is-weakened"><header><span>△</span><div><strong>예상했지만 약화</strong><small>{weakenedThemes.length}개 점검</small></div></header><div className="dashboard-hypothesis-items">{weakenedThemes.length ? weakenedThemes.map((row) => { const close = themeSummary?.topGainers.find((item) => item.themeId === row.theme_id); const live = realtimeRows.find((item) => item.theme_id === row.theme_id); const rank = live ? realtimeRows.findIndex((item) => item.theme_id === row.theme_id) + 1 : null; return <HypothesisThemeRow key={row.theme_id} name={row.theme_name} value={live?.theme_strength ?? row.theme_strength ?? row.change_rate} premarket={`${insightThemeLead(row)}${close ? ` · 전일 종가 ${formatSignedPercent(close.dailyReturn)}` : ""}`} intraday={live ? `실시간 강도 ${formatSignedPercent(live.theme_strength)} · 확산 ${live.valid_stock_count}/${live.linked_stock_count}` : "실시간 Top12 순위 이탈"} verdict="가설 약화" onOpen={() => setThemeDetailRequest({ themeId: row.theme_id, dataDate: themeSummary?.dataDate ?? null, realtime: { themeName: row.theme_name, rank, strength: live?.theme_strength ?? row.theme_strength ?? row.change_rate, validStockCount: live?.valid_stock_count ?? row.valid_stock_count, linkedStockCount: live?.linked_stock_count ?? row.linked_stock_count, snapshotAt: realtimeThemeScheduler.snapshot.snapshot_at, hypothesis: "WEAKENING" } })} />; }) : <p>약화로 분류된 집중테마가 없습니다.</p>}</div></article>
          <article className="is-new"><header><span>NEW</span><div><strong>예상 밖 급부상</strong><small>{surpriseThemes.length}개 발견</small></div></header><div className="dashboard-hypothesis-items">{surpriseThemes.length ? surpriseThemes.map((row) => { const rank = realtimeRows.findIndex((item) => item.theme_id === row.theme_id) + 1; return <HypothesisThemeRow key={row.theme_id} name={row.theme_name} value={row.theme_strength} premarket="집중 대상 아님" intraday={`실시간 #${rank} · 강도 ${formatSignedPercent(row.theme_strength)} · 확산 ${row.valid_stock_count}/${row.linked_stock_count}`} verdict="장중 신규 발견" onOpen={() => setThemeDetailRequest({ themeId: row.theme_id, dataDate: themeSummary?.dataDate ?? null, realtime: { themeName: row.theme_name, rank, strength: row.theme_strength, validStockCount: row.valid_stock_count, linkedStockCount: row.linked_stock_count, snapshotAt: realtimeThemeScheduler.snapshot.snapshot_at, hypothesis: "NEW" } })} />; }) : <p>현재 새롭게 부상한 상위 테마가 없습니다.</p>}</div></article>
        </div>
      </SectionCard> : null}

      {activeStage === "plan" ? <SectionCard className="dashboard-v4-observation-section dashboard-routine-observation">
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
      </SectionCard> : null}

      {activeStage !== "review" ? todayInsightPanel : null}

      {activeStage === "review" ? <SectionCard className="dashboard-routine-review-table">
        <div className="dashboard-v2-section-heading"><div><h3 className="section-title">오늘의 가설 리뷰</h3><p>현재 Insight 집중테마와 최신 국내 종가 상위 결과를 비교합니다.</p></div><span>런타임 비교</span></div>
        <div className="dashboard-review-counts" aria-label="가설 리뷰 요약">
          <div><span>장전 집중</span><strong>{reviewCounts.focus}</strong></div>
          <div className="is-confirmed"><span>확인</span><strong>{reviewCounts.confirmed}</strong></div>
          <div className="is-partial"><span>부분</span><strong>{reviewCounts.partial}</strong></div>
          <div className="is-weakened"><span>약화</span><strong>{reviewCounts.weakened}</strong></div>
          <div className="is-new"><span>NEW</span><strong>{reviewCounts.new}</strong></div>
        </div>
        <div className="dashboard-review-table" role="table" aria-label="오늘의 가설 리뷰">
          <div role="row" className="is-head"><span role="columnheader">테마</span><span role="columnheader">장전 근거</span><span role="columnheader">장중 흐름</span><span role="columnheader">종가 결과</span><span role="columnheader">판정</span></div>
          {reviewThemeRows.length ? reviewThemeRows.map((row) => <button type="button" role="row" key={`${row.tone}-${row.id}`} onClick={() => row.tone === "new" ? setThemeDetailRequest({ themeId: row.id, dataDate: themeSummary?.dataDate ?? null }) : navigate("/drct-insight")}><strong role="cell">{row.name}</strong><span role="cell" className={`dashboard-review-value ${reviewValueTone(row.premarket)}`}>{row.premarket}</span><span role="cell" className={`dashboard-review-value ${reviewValueTone(row.intraday)}`}>{row.intraday}</span><span role="cell" className={`dashboard-review-value ${reviewValueTone(row.close)}`}>{row.close}</span><b role="cell" className={`is-${row.tone}`}>{row.verdict}</b></button>) : <p>비교할 테마 데이터가 아직 없습니다.</p>}
        </div>
      </SectionCard> : null}

      {activeStage === "review" ? <SectionCard className="dashboard-routine-supply">
        <div className="dashboard-v2-section-heading"><div><h3 className="section-title">오늘의 수급 요약</h3><p>오늘 포착된 수급 이벤트에서 테마별 유입 강도를 추립니다.</p></div><button type="button" className="dashboard-v2-text-button" onClick={() => navigate("/market-trends")}>수급 분석 열기 →</button></div>
        {reviewSupplyError ? <div className="dashboard-review-state error"><span>수급 요약을 불러오지 못했습니다.</span><button type="button" onClick={() => void loadReviewSupply()}>다시 시도</button></div> : reviewSupply ? <>
          <div className="dashboard-supply-overview"><span>기준일 {reviewSupply.trade_date}</span><strong>이벤트 {reviewSupply.summary.event_count}건</strong><span>테마 배정 {reviewSupply.summary.assigned_count} · 미배정 {reviewSupply.summary.unassigned_count}</span></div>
          {reviewSupply.items.length ? <div className="dashboard-supply-list">{reviewSupply.items.slice(0, 3).map((item) => <button type="button" key={item.theme_id} onClick={() => navigate("/market-trends")}><span>#{item.trend_rank}</span><strong>{item.theme_name}</strong><small>{item.detected_stock_count}종목 · 거래대금 {item.total_trading_value_krw_100m.toLocaleString()}억원</small><b className={(item.avg_change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>{formatSignedPercent(item.avg_change_rate)}</b></button>)}</div> : <div className="dashboard-review-state">오늘 집계된 테마 수급이 없습니다.</div>}
        </> : <div className="dashboard-review-state">수급 요약을 불러오는 중입니다.</div>}
      </SectionCard> : null}

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
          {([['D0', performance?.summary.d0], ['D+1', performance?.summary.d1], ['D+3', performance?.summary.d3], ['D+5', performance?.summary.d5]] as const).map(([label, metric]) => <div key={label}><span>{label}</span><strong>{metric?.mean == null ? "대기" : formatSignedPercent(metric.mean)}</strong><small>{metric?.n ? `${metric.n}건` : "평가 대기"}</small></div>)}
          <dl><div><dt>평가 진행</dt><dd>{((performance?.summary.pending_count ?? 0) + (performance?.summary.partial_count ?? 0)).toLocaleString()}</dd></div><div><dt>완료</dt><dd>{(performance?.summary.complete_count ?? 0).toLocaleString()}</dd></div></dl>
        </div>}
      </SectionCard> : null}

      <MarketThemeDetailDrawer
        open={Boolean(themeDetailRequest)}
        themeId={themeDetailRequest?.themeId ?? null}
        dataDate={themeDetailRequest?.dataDate}
        realtimeContext={selectedRealtimeContext}
        onClose={() => setThemeDetailRequest(null)}
      />
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
