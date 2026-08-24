import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Info, RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import RealtimeThemeDetailDrawer from "@/components/marketThemes/RealtimeThemeDetailDrawer";
import ThemeTreemapCanvas, { type ThemeTreemapViewItem } from "@/components/marketThemes/ThemeTreemapCanvas";
import UsThemeDetailDrawer from "@/components/marketThemes/UsThemeDetailDrawer";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import { ensureRealtimeThemeSnapshot, getRealtimeThemeSchedulerState, REALTIME_THEME_AUTO_STOP_TIME, setRealtimeThemeEnabled, setRealtimeThemeInterval, setRealtimeThemeSuspended, subscribeRealtimeThemeScheduler, type RealtimeThemeIntervalMinutes } from "@/services/realtimeThemeScheduler";
import type { RealtimeThemeStocksResponse, RealtimeThemeTreemapResponse } from "@/types/marketTheme";
import type { UsThemeTreemap } from "@/types/usMarketTheme";

type MarketScope = "KR" | "US";
type ViewMetric = "average" | "strength";
const formatValue = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;

function RealtimeThemeTreemapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const marketParam = searchParams.get("market")?.toLowerCase();
  const market: MarketScope = marketParam === "us" ? "US" : "KR";
  const scheduler = useSyncExternalStore(subscribeRealtimeThemeScheduler, getRealtimeThemeSchedulerState);
  const { snapshot, intervalMinutes, isRealtime, isRefreshing, lastDurationMs, error, nextRefreshAt } = scheduler;
  const [viewMetric, setViewMetric] = useState<ViewMetric>("strength");
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [krDrawerData, setKrDrawerData] = useState<RealtimeThemeStocksResponse | null>(null);
  const [krDrawerLoading, setKrDrawerLoading] = useState(false);
  const [krDrawerError, setKrDrawerError] = useState<string | null>(null);
  const [usData, setUsData] = useState<UsThemeTreemap | null>(null);
  const [usLoading, setUsLoading] = useState(false);
  const [usError, setUsError] = useState<string | null>(null);
  const [strengthInfoOpen, setStrengthInfoOpen] = useState(false);
  const mountedRef = useRef(true);
  const krDrawerRequestRef = useRef(0);
  const usRequestRef = useRef(0);
  const strengthControlRef = useRef<HTMLDivElement | null>(null);
  const krDrawerCacheRef = useRef(new Map<string, RealtimeThemeStocksResponse>());
  const krDrawerCacheSnapshotRef = useRef<string | null>(null);

  const changeMarket = (nextMarket: MarketScope) => {
    const next = new URLSearchParams(searchParams);
    next.set("market", nextMarket.toLowerCase());
    setSearchParams(next, { replace: true });
    setSelectedThemeId(null);
  };

  const loadUsTreemap = useCallback(async () => {
    const requestId = ++usRequestRef.current;
    setUsLoading(true); setUsError(null);
    try {
      const data = await repositories.usMarketThemes.treemap();
      if (mountedRef.current && requestId === usRequestRef.current) setUsData(data);
    } catch (reason) {
      if (mountedRef.current && requestId === usRequestRef.current) setUsError(reason instanceof Error ? reason.message : "미국 테마 트리맵 조회에 실패했습니다.");
    } finally {
      if (mountedRef.current && requestId === usRequestRef.current) setUsLoading(false);
    }
  }, []);

  const loadKrDrawer = useCallback(async (themeId: number, snapshotAt: string | null, keepData = false) => {
    const requestId = ++krDrawerRequestRef.current;
    if (krDrawerCacheSnapshotRef.current !== snapshotAt) { krDrawerCacheRef.current.clear(); krDrawerCacheSnapshotRef.current = snapshotAt; }
    const cacheKey = `${snapshotAt ?? "none"}:${themeId}`;
    const cached = krDrawerCacheRef.current.get(cacheKey);
    if (cached) { setKrDrawerData(cached); setKrDrawerLoading(false); setKrDrawerError(null); return; }
    if (!keepData) setKrDrawerData(null);
    setKrDrawerLoading(true); setKrDrawerError(null);
    try {
      const data = await repositories.marketThemes.getRealtimeThemeStocks(themeId);
      if (mountedRef.current && requestId === krDrawerRequestRef.current) { krDrawerCacheRef.current.set(cacheKey, data); setKrDrawerData(data); }
    } catch (reason) {
      if (mountedRef.current && requestId === krDrawerRequestRef.current) setKrDrawerError(reason instanceof Error ? reason.message : "테마 상세 조회에 실패했습니다.");
    } finally {
      if (mountedRef.current && requestId === krDrawerRequestRef.current) setKrDrawerLoading(false);
    }
  }, []);

  useEffect(() => {
    if (marketParam !== "kr" && marketParam !== "us") {
      const next = new URLSearchParams(searchParams); next.set("market", "kr"); setSearchParams(next, { replace: true });
    }
  }, [marketParam, searchParams, setSearchParams]);

  useEffect(() => {
    mountedRef.current = true;
    setRealtimeThemeSuspended(market === "US");
    if (market === "US") void loadUsTreemap(); else void ensureRealtimeThemeSnapshot();
    return () => setRealtimeThemeSuspended(false);
  }, [market, loadUsTreemap]);

  useEffect(() => () => { mountedRef.current = false; krDrawerRequestRef.current += 1; usRequestRef.current += 1; }, []);
  useEffect(() => {
    if (!strengthInfoOpen) return;
    const outside = (event: MouseEvent) => { if (!strengthControlRef.current?.contains(event.target as Node)) setStrengthInfoOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setStrengthInfoOpen(false); };
    document.addEventListener("mousedown", outside); window.addEventListener("keydown", escape);
    return () => { document.removeEventListener("mousedown", outside); window.removeEventListener("keydown", escape); };
  }, [strengthInfoOpen]);

  const krThemes = useMemo(() => {
    const value = (theme: RealtimeThemeTreemapResponse["themes"][number]) => viewMetric === "strength" ? theme.theme_strength : theme.avg_change_rate;
    return [...snapshot.themes].sort((a, b) => {
      const left = value(a), right = value(b);
      if (left == null && right == null) return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      if (left == null) return 1; if (right == null) return -1;
      return right - left || a.theme_name.localeCompare(b.theme_name, "ko-KR");
    }).map((theme, index) => ({ ...theme, displayRank: index + 1, displayValue: value(theme) }));
  }, [snapshot.themes, viewMetric]);

  const usThemes = useMemo(() => [...(usData?.items ?? [])].sort((a, b) => {
    const left = viewMetric === "strength" ? a.theme_strength : a.simple_return;
    const right = viewMetric === "strength" ? b.theme_strength : b.simple_return;
    if (left == null && right == null) return a.theme_name.localeCompare(b.theme_name, "ko-KR");
    if (left == null) return 1; if (right == null) return -1;
    return right - left || a.theme_name.localeCompare(b.theme_name, "ko-KR");
  }).map((theme, index) => ({ ...theme, displayRank: index + 1, displayValue: viewMetric === "strength" ? theme.theme_strength : theme.simple_return })), [usData, viewMetric]);

  const items: ThemeTreemapViewItem[] = market === "KR" ? krThemes.map((theme) => ({
    id: theme.theme_id, title: theme.theme_name, rank: theme.displayRank, value: theme.displayValue, areaValue: theme.linked_stock_count, stockCount: theme.linked_stock_count,
    tooltip: `테마: ${theme.theme_name}\n기준: ${viewMetric === "strength" ? "테마강도" : "단순평균"}\n순위: ${theme.displayRank}위\n현재 값: ${formatValue(theme.displayValue)}\n연결 종목: ${theme.linked_stock_count}`,
  })) : usThemes.map((theme) => ({
    id: theme.theme_id, title: theme.theme_name, rank: theme.displayRank, value: theme.displayValue, areaValue: theme.linked_stock_count, stockCount: theme.linked_stock_count,
    tooltip: `테마그룹: ${theme.theme_group_name}\n테마: ${theme.theme_name}\n기준일: ${theme.trade_date ?? "-"}\n단순등락률: ${formatValue(theme.simple_return)}\n테마강도: ${formatValue(theme.theme_strength)}\n상승비율: ${theme.breadth_ratio == null ? "-" : `${(theme.breadth_ratio * 100).toFixed(0)}%`}\n연결 종목: ${theme.linked_stock_count}`,
  }));

  const realtimeError = error ? (() => { const match = error.match(/\(([^()]+)\)\s*$/); return { message: match ? error.slice(0, match.index).trim() : error, reason: match?.[1] ?? null }; })() : null;
  const selectedKrTheme = krThemes.find((theme) => theme.theme_id === selectedThemeId) ?? null;
  const closeKrDrawer = () => { krDrawerRequestRef.current += 1; setSelectedThemeId(null); setKrDrawerData(null); setKrDrawerError(null); setKrDrawerLoading(false); };

  const metricControl = <div ref={strengthControlRef} className="realtime-theme-metric-control">
    <button type="button" className={viewMetric === "average" ? "is-active" : ""} aria-pressed={viewMetric === "average"} onClick={() => setViewMetric("average")}>{market === "KR" ? "단순평균" : "단순등락률"}</button>
    <span className={viewMetric === "strength" ? "is-active" : ""}><button type="button" aria-pressed={viewMetric === "strength"} onClick={() => setViewMetric("strength")}>테마강도</button><button type="button" className="realtime-theme-strength-info-button" aria-label="테마강도 계산 기준 설명" aria-expanded={strengthInfoOpen} onClick={() => setStrengthInfoOpen((open) => !open)}><Info size={12} /></button></span>
    {strengthInfoOpen ? <div className="realtime-theme-strength-popover" role="dialog" aria-label="테마강도 계산 기준"><strong>테마강도</strong><p>일부 급등·급락 종목이 평균을 과도하게 왜곡하지 않도록 절사평균과 중앙값을 함께 사용합니다.</p><ul><li>대표 강도: 절사평균 60% + 중앙값 40%</li><li>확산도: 같은 방향으로 움직이는 종목 비율 반영</li><li>종목수 보정: 종목이 적을수록 시장 중앙값 쪽으로 보정</li></ul><p>{market === "KR" ? "현재 Snapshot" : "저장된 최신 확정 종가 집계"}만 사용하며 화면 조회 중에는 재계산하지 않습니다.</p><small>등락률과 동일한 % 단위입니다.</small></div> : null}
  </div>;

  const scope = <div className="stock-market-scope market-theme-scope-control" role="group" aria-label="시장 범위"><button type="button" className={market === "KR" ? "active" : ""} aria-pressed={market === "KR"} onClick={() => changeMarket("KR")}>국내 KRX</button><button type="button" className={market === "US" ? "active" : ""} aria-pressed={market === "US"} onClick={() => changeMarket("US")}>미국 US</button></div>;

  return <div className="realtime-theme-page">
    <div className="realtime-theme-header-grid"><PageHeader title={market === "KR" ? "실시간 테마 트리맵" : "미국 테마 트리맵"} description={market === "KR" ? "현재 활성 테마와 연결 종목의 장중 등락률을 실시간 Snapshot으로 확인합니다." : "최근 확정된 미국 종가 기준 테마 등락률을 확인합니다."} /><section className="market-theme-scope-panel realtime-theme-scope-panel"><strong>시장</strong>{scope}</section></div>

    {market === "KR" ? <section className="realtime-theme-overview" aria-label="실시간 수집 현황">
      <div className="realtime-theme-kpis"><div><span>활성 테마</span><strong>{snapshot.theme_count}</strong></div><div><span>연결</span><strong>{snapshot.linked_stock_count}</strong></div><div><span>고유 종목</span><strong>{snapshot.unique_stock_count}</strong></div><div><span>수집</span><strong>{snapshot.valid_stock_count} / {snapshot.unique_stock_count}</strong></div></div>
      <div className="realtime-theme-controls"><label><span>대기 <span className="realtime-theme-wait-help" title="수집 완료 후 선택 시간만큼 기다렸다 다음 수집을 시작합니다."><Info size={13} /></span></span><select value={intervalMinutes} onChange={(event) => setRealtimeThemeInterval(event.target.value as RealtimeThemeIntervalMinutes)}><option value="3">3분</option><option value="5">5분</option><option value="10">10분</option><option value="20">20분</option><option value="30">30분</option></select></label><span className="realtime-theme-last">최근 갱신 <strong>{snapshot.snapshot_at?.slice(11) || "미수집"}</strong>{lastDurationMs == null ? "" : ` · ${(lastDurationMs / 1000).toFixed(1)}초`}</span><button className={`btn ${isRealtime ? "btn-primary" : "btn-secondary"}`} type="button" onClick={() => setRealtimeThemeEnabled(!isRealtime)}><span>●</span> 실시간 {isRealtime ? "ON" : "OFF"}</button></div>
      {isRefreshing ? <p className="realtime-theme-refreshing"><RefreshCw size={15} className="realtime-spin" /> 실시간 데이터 갱신 중...</p> : null}{isRealtime && !isRefreshing ? <p className="realtime-theme-refreshing is-waiting"><RefreshCw size={15} /> 실시간 자동 갱신 진행 중 · 다음 갱신 {nextRefreshAt == null ? "준비 중" : new Date(nextRefreshAt).toLocaleTimeString("ko-KR", { hour12: false })} · {REALTIME_THEME_AUTO_STOP_TIME} 최종 갱신 후 자동 종료</p> : null}
      {realtimeError ? <div className="realtime-theme-error" role="alert"><span className="realtime-theme-error-dot" /><div><strong>실시간 수집 실패</strong><p>{realtimeError.message}</p></div>{realtimeError.reason ? <code>{realtimeError.reason}</code> : null}</div> : null}
    </section> : <section className="realtime-theme-overview realtime-theme-us-overview" aria-label="미국 테마 확정 데이터 현황">
      <div className="realtime-theme-kpis"><div><span>활성 테마</span><strong>{usData?.active_theme_count ?? 0}</strong></div><div><span>연결</span><strong>{usData?.linked_stock_count ?? 0}</strong></div><div><span>집계 종목</span><strong>{usData?.aggregated_stock_count ?? 0}</strong></div><div><span>기준일</span><strong>{usData?.latest_date ?? "-"}</strong></div></div>
      <div className="realtime-theme-controls"><span className="realtime-theme-last">저장된 최신 확정 종가 데이터</span><button className="btn btn-secondary" type="button" disabled={usLoading} onClick={() => void loadUsTreemap()}><RefreshCw size={15} className={usLoading ? "realtime-spin" : ""} /> 새로고침</button></div>
      {usError ? <div className="realtime-theme-error" role="alert"><span className="realtime-theme-error-dot" /><div><strong>미국 테마 조회 실패</strong><p>{usError}</p></div></div> : null}
    </section>}

    <ThemeTreemapCanvas title={market === "KR" ? "실시간 테마 트리맵" : "미국 테마 트리맵"} subtitle={market === "KR" ? "면적 = 연결 종목 수 · 색상/순위 = 선택 계산 기준" : `면적 = 활성 연결 종목 수 · 색상/순위 = 최신 확정 ${viewMetric === "strength" ? "테마강도" : "단순등락률"}`} tools={metricControl} items={items} selectedId={selectedThemeId} emptyMessage={market === "KR" ? "실시간 ON을 누르면 첫 Snapshot을 수집합니다." : usLoading ? "미국 테마 데이터를 불러오는 중입니다." : "집계된 미국 테마 데이터가 없습니다."} onSelect={(themeId) => { setSelectedThemeId(themeId); if (market === "KR") void loadKrDrawer(themeId, snapshot.snapshot_at); }} />
    <RealtimeThemeDetailDrawer open={market === "KR" && selectedThemeId != null} data={krDrawerData} loading={krDrawerLoading} error={krDrawerError} metric={viewMetric} metricLabel={viewMetric === "strength" ? "테마강도" : "단순평균"} metricValue={selectedKrTheme?.displayValue ?? null} metricRank={selectedKrTheme?.displayRank ?? null} onMetricChange={setViewMetric} onClose={closeKrDrawer} onRetry={() => selectedThemeId != null && void loadKrDrawer(selectedThemeId, snapshot.snapshot_at, true)} />
    <UsThemeDetailDrawer open={market === "US" && selectedThemeId != null} themeId={selectedThemeId} tradeDate={usData?.latest_date} onClose={() => setSelectedThemeId(null)} />
  </div>;
}

export default RealtimeThemeTreemapPage;
