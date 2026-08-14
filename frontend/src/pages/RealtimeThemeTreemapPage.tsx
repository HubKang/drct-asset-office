import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import type { CSSProperties } from "react";
import { Info, RefreshCw } from "lucide-react";

import PageHeader from "@/components/common/PageHeader";
import RealtimeThemeDetailDrawer from "@/components/marketThemes/RealtimeThemeDetailDrawer";
import { repositories } from "@/services";
import {
  ensureRealtimeThemeSnapshot,
  getRealtimeThemeSchedulerState,
  setRealtimeThemeEnabled,
  setRealtimeThemeInterval,
  subscribeRealtimeThemeScheduler,
  type RealtimeThemeIntervalMinutes,
} from "@/services/realtimeThemeScheduler";
import type { RealtimeThemeStocksResponse, RealtimeThemeTreemapResponse } from "@/types/marketTheme";
import { getThemeReturnHeatmapColor, getThemeReturnTextColor } from "@/utils/marketThemeReturnColor";
import { buildTreemapLayout, getTreemapTextMetrics } from "@/utils/treemapLayout";

type TreemapCellLevel = "large" | "medium" | "small" | "tiny";
type RealtimeThemeViewMetric = "average" | "strength";

function getTreemapCellDisplayMode(width: number, height: number): TreemapCellLevel {
  if (width >= 250 && height >= 100) return "large";
  if (width >= 150 && height >= 70) return "medium";
  if (width >= 80 && height >= 50) return "small";
  return "tiny";
}

function RealtimeThemeTreemapPage() {
  const scheduler = useSyncExternalStore(subscribeRealtimeThemeScheduler, getRealtimeThemeSchedulerState);
  const { snapshot, intervalMinutes, isRealtime, isRefreshing, lastDurationMs, error, nextRefreshAt } = scheduler;
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [drawerData, setDrawerData] = useState<RealtimeThemeStocksResponse | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);
  const [treemapSize, setTreemapSize] = useState({ width: 0, height: 0 });
  const [viewMetric, setViewMetric] = useState<RealtimeThemeViewMetric>("strength");
  const [strengthInfoOpen, setStrengthInfoOpen] = useState(false);
  const mountedRef = useRef(true);
  const drawerRequestIdRef = useRef(0);
  const treemapCanvasRef = useRef<HTMLDivElement | null>(null);
  const strengthControlRef = useRef<HTMLDivElement | null>(null);
  const drawerCacheRef = useRef(new Map<string, RealtimeThemeStocksResponse>());
  const drawerCacheSnapshotRef = useRef<string | null>(null);

  const rankedThemes = useMemo(() => {
    const metricValue = (theme: RealtimeThemeTreemapResponse["themes"][number]) => viewMetric === "strength" ? theme.theme_strength : theme.avg_change_rate;
    return [...snapshot.themes]
      .sort((a, b) => {
        const aValue = metricValue(a); const bValue = metricValue(b);
        if (aValue == null && bValue == null) return a.theme_name.localeCompare(b.theme_name, "ko-KR");
        if (aValue == null) return 1;
        if (bValue == null) return -1;
        return bValue - aValue || a.theme_name.localeCompare(b.theme_name, "ko-KR");
      })
      .map((theme, index) => ({ ...theme, displayRank: index + 1, displayValue: metricValue(theme) }));
  }, [snapshot.themes, viewMetric]);

  const selectedTheme = useMemo(() => rankedThemes.find((theme) => theme.theme_id === selectedThemeId) ?? null, [rankedThemes, selectedThemeId]);
  const realtimeError = useMemo(() => {
    if (!error) return null;
    const reasonMatch = error.match(/\(([^()]+)\)\s*$/);
    return {
      message: reasonMatch ? error.slice(0, reasonMatch.index).trim() : error,
      reason: reasonMatch?.[1] ?? null,
    };
  }, [error]);

  const treemapLayout = useMemo(() => {
    const started = performance.now();
    const rects = buildTreemapLayout(rankedThemes.map((theme) => ({ id: String(theme.theme_id), value: theme.linked_stock_count })), { preserveOrder: true });
    return { rects: new Map(rects.map((rect) => [Number(rect.id), rect])), durationMs: performance.now() - started };
  }, [rankedThemes]);

  const loadDrawer = useCallback(async (themeId: number, snapshotAt: string | null, keepData = false) => {
    const requestId = ++drawerRequestIdRef.current;
    if (drawerCacheSnapshotRef.current !== snapshotAt) {
      drawerCacheRef.current.clear();
      drawerCacheSnapshotRef.current = snapshotAt;
    }
    const cacheKey = `${snapshotAt ?? "none"}:${themeId}`;
    const cached = drawerCacheRef.current.get(cacheKey);
    if (cached) {
      setDrawerData(cached); setDrawerLoading(false); setDrawerError(null);
      return;
    }
    if (!keepData) setDrawerData(null);
    setDrawerLoading(true); setDrawerError(null);
    try {
      const data = await repositories.marketThemes.getRealtimeThemeStocks(themeId);
      if (mountedRef.current && requestId === drawerRequestIdRef.current) {
        drawerCacheRef.current.set(cacheKey, data);
        setDrawerData(data);
      }
    } catch (nextError) {
      if (mountedRef.current && requestId === drawerRequestIdRef.current) setDrawerError(nextError instanceof Error ? nextError.message : "테마 상세 조회에 실패했습니다.");
    } finally {
      if (mountedRef.current && requestId === drawerRequestIdRef.current) setDrawerLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void ensureRealtimeThemeSnapshot();
    return () => { mountedRef.current = false; drawerRequestIdRef.current += 1; };
  }, []);

  useEffect(() => {
    const canvas = treemapCanvasRef.current;
    if (!canvas) return;
    const updateSize = () => setTreemapSize({ width: canvas.clientWidth, height: canvas.clientHeight });
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [snapshot.themes.length]);

  useEffect(() => {
    if (!strengthInfoOpen) return;
    const closeOnOutside = (event: MouseEvent) => {
      if (!strengthControlRef.current?.contains(event.target as Node)) setStrengthInfoOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setStrengthInfoOpen(false); };
    document.addEventListener("mousedown", closeOnOutside);
    window.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("mousedown", closeOnOutside); window.removeEventListener("keydown", closeOnEscape); };
  }, [strengthInfoOpen]);

  const openDrawer = (themeId: number) => { setSelectedThemeId(themeId); void loadDrawer(themeId, snapshot.snapshot_at); };
  const closeDrawer = useCallback(() => { drawerRequestIdRef.current += 1; setSelectedThemeId(null); setDrawerData(null); setDrawerError(null); setDrawerLoading(false); }, []);

  return <div className="realtime-theme-page">
    <PageHeader title="실시간 테마 트리맵" description="현재 활성 테마와 연결 종목의 장중 등락률을 실시간 Snapshot으로 확인합니다." />
    <section className="realtime-theme-overview" aria-label="실시간 수집 현황">
      <div className="realtime-theme-kpis"><div><span>활성 테마</span><strong>{snapshot.theme_count}</strong></div><div><span>연결</span><strong>{snapshot.linked_stock_count}</strong></div><div><span>고유 종목</span><strong>{snapshot.unique_stock_count}</strong></div><div><span>수집</span><strong>{snapshot.valid_stock_count} / {snapshot.unique_stock_count}</strong></div></div>
      <div className="realtime-theme-controls">
        <label><span>대기 <span className="realtime-theme-wait-help" title="실시간 데이터 수집이 완료된 후 선택한 시간만큼 기다렸다가 다음 수집을 시작합니다."><Info size={13} aria-hidden="true" /></span></span><select value={intervalMinutes} onChange={(event) => setRealtimeThemeInterval(event.target.value as RealtimeThemeIntervalMinutes)}><option value="3">3분</option><option value="5">5분</option><option value="10">10분</option><option value="20">20분</option><option value="30">30분</option></select></label>
        <span className="realtime-theme-last">최근 갱신 <strong>{snapshot.snapshot_at?.slice(11) || "미수집"}</strong>{lastDurationMs == null ? "" : ` · ${(lastDurationMs / 1000).toFixed(1)}초`}</span>
        <button className={`btn ${isRealtime ? "btn-primary" : "btn-secondary"}`} type="button" onClick={() => setRealtimeThemeEnabled(!isRealtime)}><span aria-hidden="true">●</span> 실시간 {isRealtime ? "ON" : "OFF"}</button>
      </div>
      {isRefreshing ? <p className="realtime-theme-refreshing"><RefreshCw size={15} className="realtime-spin" /> 실시간 데이터 갱신 중...</p> : null}
      {isRealtime && !isRefreshing ? <p className="realtime-theme-refreshing is-waiting"><RefreshCw size={15} /> 실시간 자동 갱신 진행 중 · 다음 갱신 {nextRefreshAt == null ? "준비 중" : new Date(nextRefreshAt).toLocaleTimeString("ko-KR", { hour12: false })}</p> : null}
      {realtimeError ? <div className="realtime-theme-error" role="alert">
        <span className="realtime-theme-error-dot" aria-hidden="true" />
        <div><strong>실시간 수집 실패</strong><p>{realtimeError.message}</p></div>
        {realtimeError.reason ? <code>{realtimeError.reason}</code> : null}
      </div> : null}
    </section>
    <section className="realtime-theme-placeholder" aria-label="실시간 테마 트리맵">
      <div className="realtime-theme-treemap-head">
        <div><strong>실시간 테마 트리맵</strong><span>면적 = 연결 종목 수 · 색상/순위 = 선택 계산 기준</span></div>
        <div className="realtime-theme-treemap-tools">
          <div ref={strengthControlRef} className="realtime-theme-metric-control">
            <button type="button" className={viewMetric === "average" ? "is-active" : ""} aria-pressed={viewMetric === "average"} onClick={() => setViewMetric("average")}>단순평균</button>
            <span className={viewMetric === "strength" ? "is-active" : ""}><button type="button" aria-pressed={viewMetric === "strength"} onClick={() => setViewMetric("strength")}>테마강도</button><button type="button" className="realtime-theme-strength-info-button" aria-label="테마강도 계산 기준 설명" aria-expanded={strengthInfoOpen} onClick={() => setStrengthInfoOpen((open) => !open)}><Info size={12} /></button></span>
            {strengthInfoOpen ? <div className="realtime-theme-strength-popover" role="dialog" aria-label="테마강도 계산 기준"><strong>테마강도</strong><p>일부 급등·급락 종목이 평균을 과도하게 왜곡하지 않도록 절사평균과 중앙값을 함께 사용합니다.</p><ul><li>대표 강도: 절사평균 60% + 중앙값 40%</li><li>확산도: 같은 방향으로 움직이는 종목 비율 반영</li><li>종목수 보정: 종목이 적을수록 시장 중앙값 쪽으로 보정</li></ul><p>추가 시세 호출 없이 현재 Snapshot만으로 계산하며 결과는 저장하지 않습니다.</p><small>등락률과 동일한 % 단위입니다.</small></div> : null}
          </div>
          <small>Layout {treemapLayout.durationMs.toFixed(2)}ms</small>
        </div>
      </div>
      {rankedThemes.some((theme) => theme.linked_stock_count > 0) ? <div ref={treemapCanvasRef} className="realtime-theme-treemap-canvas">{rankedThemes.map((theme) => {
        const rect = treemapLayout.rects.get(theme.theme_id); if (!rect) return null;
        const width = treemapSize.width * rect.width / 100;
        const height = treemapSize.height * rect.height / 100;
        const level = getTreemapCellDisplayMode(width, height);
        const metrics = getTreemapTextMetrics(rect, theme.theme_name, { variant: "marketTrend" });
        const rate = theme.displayValue;
        const style = { left: `calc(${rect.x}% + 2px)`, top: `calc(${rect.y}% + 2px)`, width: `calc(${rect.width}% - 4px)`, height: `calc(${rect.height}% - 4px)`, background: getThemeReturnHeatmapColor(rate), color: getThemeReturnTextColor(rate), "--realtime-title-size": `${metrics.titleFontSize}px`, "--realtime-title-lines": metrics.titleLineClamp } as CSSProperties;
        const formattedRate = rate == null ? "-" : `${rate > 0 ? "+" : ""}${rate.toFixed(2)}%`;
        return <button key={theme.theme_id} type="button" className={`realtime-theme-tile is-${level}${selectedThemeId === theme.theme_id ? " is-selected" : ""}`} style={style} title={`테마: ${theme.theme_name}\n기준: ${viewMetric === "strength" ? "테마강도" : "단순평균"}\n순위: ${theme.displayRank}위\n현재 값: ${formattedRate}\n연결 종목: ${theme.linked_stock_count}`} aria-pressed={selectedThemeId === theme.theme_id} onClick={() => openDrawer(theme.theme_id)}><b>{theme.displayRank}</b><strong>{theme.theme_name}</strong><em>{formattedRate} <span>({theme.linked_stock_count}종목)</span></em></button>;
      })}</div> : <p>실시간 ON을 누르면 첫 Snapshot을 수집합니다.</p>}
    </section>
    <RealtimeThemeDetailDrawer open={selectedThemeId != null} data={drawerData} loading={drawerLoading} error={drawerError} metric={viewMetric} metricLabel={viewMetric === "strength" ? "테마강도" : "단순평균"} metricValue={selectedTheme?.displayValue ?? null} metricRank={selectedTheme?.displayRank ?? null} onMetricChange={setViewMetric} onClose={closeDrawer} onRetry={() => selectedThemeId != null && void loadDrawer(selectedThemeId, snapshot.snapshot_at, true)} />
  </div>;
}

export default RealtimeThemeTreemapPage;
