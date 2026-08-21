import { repositories } from "@/services";
import type { RealtimeThemeTreemapResponse } from "@/types/marketTheme";

export const REALTIME_THEME_INTERVAL_SECONDS = {
  "3": 180,
  "5": 300,
  "10": 600,
  "20": 1200,
  "30": 1800,
} as const;

export type RealtimeThemeIntervalMinutes = keyof typeof REALTIME_THEME_INTERVAL_SECONDS;

export const REALTIME_THEME_MARKET_OPEN_TIME = "09:00";
export const REALTIME_THEME_AUTO_STOP_TIME = "15:30";
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

const getKstMarketTimeAt = (hour: number, minute: number, now = Date.now()) => {
  const kstNow = new Date(now + KST_OFFSET_MS);
  return Date.UTC(
    kstNow.getUTCFullYear(),
    kstNow.getUTCMonth(),
    kstNow.getUTCDate(),
    hour - 9,
    minute,
  );
};

export const getRealtimeThemeMarketOpenAt = (now = Date.now()) => getKstMarketTimeAt(9, 0, now);
export const getRealtimeThemeAutoStopAt = (now = Date.now()) => getKstMarketTimeAt(15, 30, now);
export const isRealtimeThemeAutoStopTime = (now = Date.now()) => now >= getRealtimeThemeAutoStopAt(now);
export const isRealtimeThemeMarketHours = (now = Date.now()) => now >= getRealtimeThemeMarketOpenAt(now) && !isRealtimeThemeAutoStopTime(now);

export type RealtimeThemeSchedulerState = {
  snapshot: RealtimeThemeTreemapResponse;
  intervalMinutes: RealtimeThemeIntervalMinutes;
  isRealtime: boolean;
  isRefreshing: boolean;
  lastDurationMs: number | null;
  error: string | null;
  nextRefreshAt: number | null;
};

const ENABLED_STORAGE_KEY = "drct.realtimeTheme.enabled";
const INTERVAL_STORAGE_KEY = "drct.realtimeTheme.intervalMinutes";
const listeners = new Set<() => void>();
const isBrowser = typeof window !== "undefined";

const emptySnapshot = (): RealtimeThemeTreemapResponse => ({
  trade_date: "-", snapshot_at: null, theme_count: 0, linked_stock_count: 0,
  unique_stock_count: 0, valid_stock_count: 0, failed_stock_count: 0, themes: [],
});

const storedInterval = isBrowser ? window.localStorage.getItem(INTERVAL_STORAGE_KEY) : null;
const initialInterval: RealtimeThemeIntervalMinutes = storedInterval && storedInterval in REALTIME_THEME_INTERVAL_SECONDS
  ? storedInterval as RealtimeThemeIntervalMinutes
  : "10";
const storedEnabled = isBrowser && window.localStorage.getItem(ENABLED_STORAGE_KEY) === "true";
const initialRealtimeEnabled = storedEnabled && isRealtimeThemeMarketHours();
if (isBrowser && storedEnabled && !initialRealtimeEnabled) window.localStorage.setItem(ENABLED_STORAGE_KEY, "false");

let state: RealtimeThemeSchedulerState = {
  snapshot: emptySnapshot(),
  intervalMinutes: initialInterval,
  isRealtime: initialRealtimeEnabled,
  isRefreshing: false,
  lastDurationMs: null,
  error: null,
  nextRefreshAt: null,
};
let timer: number | null = null;
let refreshPromise: Promise<void> | null = null;
let snapshotLoadPromise: Promise<void> | null = null;

const emit = () => listeners.forEach((listener) => listener());
const update = (partial: Partial<RealtimeThemeSchedulerState>) => {
  state = { ...state, ...partial };
  emit();
};
const clearTimer = () => {
  if (timer != null) window.clearTimeout(timer);
  timer = null;
};
const stopRealtimeTheme = () => {
  clearTimer();
  if (isBrowser) window.localStorage.setItem(ENABLED_STORAGE_KEY, "false");
  update({ isRealtime: false, nextRefreshAt: null });
};

const scheduleNext = () => {
  clearTimer();
  if (!state.isRealtime) { update({ nextRefreshAt: null }); return; }
  const now = Date.now();
  if (!isRealtimeThemeMarketHours(now)) { stopRealtimeTheme(); return; }
  const autoStopAt = getRealtimeThemeAutoStopAt(now);
  const waitMs = REALTIME_THEME_INTERVAL_SECONDS[state.intervalMinutes] * 1000;
  const nextRefreshAt = Math.min(now + waitMs, autoStopAt);
  const isFinalRefresh = nextRefreshAt === autoStopAt;
  update({ nextRefreshAt });
  timer = window.setTimeout(() => {
    timer = null;
    if (isFinalRefresh && getRealtimeThemeAutoStopAt() !== autoStopAt) { stopRealtimeTheme(); return; }
    void refreshRealtimeTheme(isFinalRefresh);
  }, nextRefreshAt - now);
};

export const refreshRealtimeTheme = (stopAfterRefresh = false): Promise<void> => {
  if (refreshPromise) return refreshPromise;
  update({ isRefreshing: true, nextRefreshAt: null });
  refreshPromise = repositories.marketThemes.refreshRealtimeTreemap()
    .then((snapshot) => update({ snapshot, lastDurationMs: snapshot.duration_ms, error: null }))
    .catch((reason: unknown) => update({ error: reason instanceof Error ? reason.message : "실시간 갱신에 실패했습니다." }))
    .finally(() => {
      refreshPromise = null;
      update({ isRefreshing: false });
      if (stopAfterRefresh || isRealtimeThemeAutoStopTime()) stopRealtimeTheme();
      else if (state.isRealtime) scheduleNext();
    });
  return refreshPromise;
};

export const ensureRealtimeThemeSnapshot = (): Promise<void> => {
  if (state.snapshot.snapshot_at || refreshPromise) return refreshPromise ?? Promise.resolve();
  if (snapshotLoadPromise) return snapshotLoadPromise;
  snapshotLoadPromise = repositories.marketThemes.getRealtimeTreemap()
    .then((snapshot) => update({ snapshot, error: null }))
    .catch((reason: unknown) => update({ error: reason instanceof Error ? reason.message : "Snapshot 조회에 실패했습니다." }))
    .finally(() => { snapshotLoadPromise = null; });
  return snapshotLoadPromise;
};

export const setRealtimeThemeEnabled = (enabled: boolean) => {
  window.localStorage.setItem(ENABLED_STORAGE_KEY, String(enabled));
  clearTimer();
  update({ isRealtime: enabled, nextRefreshAt: null });
  if (enabled) void refreshRealtimeTheme(!isRealtimeThemeMarketHours());
};

export const setRealtimeThemeInterval = (intervalMinutes: RealtimeThemeIntervalMinutes) => {
  window.localStorage.setItem(INTERVAL_STORAGE_KEY, intervalMinutes);
  update({ intervalMinutes });
  if (state.isRealtime && !state.isRefreshing) scheduleNext();
};

export const subscribeRealtimeThemeScheduler = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const getRealtimeThemeSchedulerState = () => state;

// 경로가 바뀌어 화면 컴포넌트가 제거되어도 모듈 스케줄러는 계속 동작합니다.
if (isBrowser && state.isRealtime) void refreshRealtimeTheme();
