import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { RealtimeThemeTreemapResponse } from "@/types/marketTheme";
import type { UsKrTodayObservation, UsKrTodayObservationItem } from "@/types/usKrThemeLink";

export type TodayMetric = "theme_strength" | "simple_return";
export type TodayDirection = "ALL" | "UP" | "DOWN";
type Props = {
  initialWindow: number;
  initialMetric: TodayMetric;
  initialDirection: TodayDirection;
  onConfigChange: (window: number, metric: TodayMetric, direction: TodayDirection) => void;
  onOpenAnalysis: (linkId: number, window: number, metric: TodayMetric, direction: TodayDirection) => void;
  onOpenThemeDetail: (themeId: number) => void;
};

type LiveStatus = "following" | "opposite" | "flat" | "missing";

const pct = (value: number | null, digits = 2) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
const tone = (value: number | null) => value == null ? "" : value > 0 ? "positive" : value < 0 ? "negative" : "flat";
const timeLabel = (value: string | null) => {
  if (!value) return "";
  const match = value.match(/(?:T|\s)(\d{2}:\d{2})/);
  return match?.[1] || "";
};
const liveStatus = (usValue: number | null, krValue: number | null): LiveStatus => {
  if (usValue == null || krValue == null) return "missing";
  if (usValue === 0 || krValue === 0) return "flat";
  return Math.sign(usValue) === Math.sign(krValue) ? "following" : "opposite";
};
const statusLabel: Record<LiveStatus, string> = {
  following: "동행",
  opposite: "역행",
  flat: "보합",
  missing: "데이터 없음",
};

export default function UsKrTodayObservationPanel({ initialWindow, initialMetric, initialDirection, onConfigChange, onOpenAnalysis, onOpenThemeDetail }: Props) {
  const [windowSize, setWindowSize] = useState(initialWindow);
  const [metric, setMetric] = useState<TodayMetric>(initialMetric);
  const [direction, setDirection] = useState<TodayDirection>(initialDirection);
  const [refreshKey, setRefreshKey] = useState(0);
  const [data, setData] = useState<UsKrTodayObservation | null>(null);
  const [snapshot, setSnapshot] = useState<RealtimeThemeTreemapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [snapshotError, setSnapshotError] = useState("");

  useEffect(() => { onConfigChange(windowSize, metric, direction); }, [windowSize, metric, direction]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    repositories.usKrThemeLinks.todayObservation(windowSize, metric).then((response) => {
      if (!cancelled) setData(response);
    }).catch((reason) => {
      if (!cancelled) {
        setData(null);
        setError(reason instanceof Error ? reason.message : "오늘의 연계 관찰을 불러오지 못했습니다.");
      }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [windowSize, metric, refreshKey]);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const loadSnapshot = async () => {
      try {
        const response = await repositories.marketThemes.getRealtimeTreemap(controller.signal);
        if (!disposed) {
          setSnapshot(response);
          setSnapshotError("");
        }
      } catch (reason) {
        if (!disposed && !controller.signal.aborted) {
          setSnapshotError(reason instanceof Error ? reason.message : "국내 실시간 스냅샷을 불러오지 못했습니다.");
        }
      }
    };
    void loadSnapshot();
    const timer = window.setInterval(() => { void loadSnapshot(); }, 30_000);
    return () => {
      disposed = true;
      controller.abort();
      window.clearInterval(timer);
    };
  }, [refreshKey]);

  const liveThemeMap = useMemo(() => new Map((snapshot?.themes || []).map((row) => [row.theme_id, row])), [snapshot]);
  const items = useMemo(() => {
    const rows = (data?.items || []).filter((row) => direction === "ALL" || row.threshold_direction === direction);
    return [...rows].sort((a, b) => {
      if (a.latest_value == null && b.latest_value != null) return 1;
      if (a.latest_value != null && b.latest_value == null) return -1;
      const primary = (b.latest_value ?? 0) - (a.latest_value ?? 0);
      if (primary !== 0) return primary;
      if (a.available !== b.available) return a.available ? -1 : 1;
      const response = (b.response_rate ?? -1) - (a.response_rate ?? -1);
      return response || b.sample_count - a.sample_count;
    });
  }, [data, direction]);
  const realtimeAvailableCount = useMemo(() => items.filter((row) => {
    const live = liveThemeMap.get(row.kr_theme_id);
    const value = metric === "theme_strength" ? live?.theme_strength : live?.avg_change_rate;
    return live != null && live.valid_stock_count > 0 && value != null;
  }).length, [items, liveThemeMap, metric]);

  const snapshotDate = snapshot?.snapshot_at ? `${snapshot.trade_date} · 장중` : "실시간 스냅샷 대기";
  return <div className="space-y-4 us-kr-today-observation">
    <SectionCard title="오늘의 연계 관찰" className="us-kr-today-toolbar-card">
      <div className="us-kr-today-panel-heading"><p>미국 선행 움직임부터 국내 과거·현재 반응까지 한 흐름으로 확인합니다.</p><span>US D-1 → KR D0</span></div>
      <div className="us-kr-today-toolbar">
        <label className="us-kr-toolbar-field"><span>분석 기간</span><select className="select-control" value={windowSize} onChange={(event) => setWindowSize(Number(event.target.value))}><option value={60}>최근 60쌍</option><option value={120}>최근 120쌍</option><option value={250}>최근 250쌍</option><option value={0}>전체</option></select></label>
        <fieldset className="us-kr-toolbar-field"><legend>미국 기준 지표</legend><div className="us-kr-segmented"><button type="button" className={metric === "theme_strength" ? "active" : ""} onClick={() => setMetric("theme_strength")}>테마강도</button><button type="button" className={metric === "simple_return" ? "active" : ""} onClick={() => setMetric("simple_return")}>단순등락률</button></div></fieldset>
        <fieldset className="us-kr-toolbar-field us-kr-direction-field"><legend>관찰 방향</legend><div className="us-kr-segmented"><button type="button" className={direction === "ALL" ? "active" : ""} onClick={() => setDirection("ALL")}>전체</button><button type="button" className={direction === "UP" ? "active" : ""} onClick={() => setDirection("UP")}>상승</button><button type="button" className={direction === "DOWN" ? "active" : ""} onClick={() => setDirection("DOWN")}>하락</button></div></fieldset>
        <button className="secondary-button us-kr-refresh-button" type="button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}><RefreshCw size={14} /> 새로고침</button>
      </div>
      {data ? <div className="us-kr-today-context-strip">
        <div className="us-kr-today-date-flow"><span><small>미국 US · D-1</small><strong>{data.latest_us_date || "-"}</strong></span><b aria-hidden="true">→</b><span><small>국내 KRX · 실시간</small><strong>{snapshotDate}</strong></span><em>휴장 간격 최대 {data.max_calendar_gap_days}일</em></div>
        <div className="us-kr-today-summary">
          <article><span>활성 연결</span><strong>{data.summary.linked_count}</strong></article><article><span>과거 분석</span><strong>{data.summary.available_count}</strong></article><article><span>실시간 확인</span><strong>{realtimeAvailableCount}</strong></article><article><span>데이터 없음</span><strong>{Math.max(items.length - realtimeAvailableCount, 0)}</strong></article>
        </div>
      </div> : null}
    </SectionCard>
    {error ? <p className="form-error-message" role="alert">{error}</p> : null}
    {snapshotError ? <p className="us-kr-snapshot-warning" role="status">과거 분석은 정상이며 국내 실시간 값만 일시적으로 조회할 수 없습니다. {snapshotError}</p> : null}
    {data ? <>
      <SectionCard title={`연계 관찰 목록 · ${items.length}`} className="us-kr-today-list-card">
        <div className="table-scroll"><table className="data-table us-kr-today-table"><colgroup><col className="rank" /><col className="us-theme" /><col className="us-move" /><col className="breadth" /><col className="connector" /><col className="kr-theme" /><col className="history" /><col className="current" /><col className="action" /></colgroup><thead><tr className="us-kr-today-group-heading"><th rowSpan={2}>순위</th><th colSpan={3} className="us-kr-group-us group-start group-end">미국 선행</th><th rowSpan={2} aria-label="연계">연계</th><th colSpan={3} className="us-kr-group-kr group-start group-end">국내 반응</th><th rowSpan={2}>작업</th></tr><tr><th className="us-kr-group-us group-start">테마</th><th className="us-kr-group-us">D-1 움직임</th><th className="us-kr-group-us group-end">확산</th><th className="us-kr-group-kr group-start">테마</th><th className="us-kr-group-kr">과거 동일조건</th><th className="us-kr-group-kr group-end">현재 반응</th></tr></thead><tbody>
          {items.map((row: UsKrTodayObservationItem, index) => {
            const live = liveThemeMap.get(row.kr_theme_id);
            const liveValue = live && live.valid_stock_count > 0 ? (metric === "theme_strength" ? live.theme_strength : live.avg_change_rate) : null;
            const status = liveStatus(row.latest_value, liveValue);
            return <tr key={row.link_id} className={!row.available ? "is-missing" : ""}>
              <td data-label="순위"><strong>{index + 1}</strong></td>
              <td className="us-kr-group-us group-start" data-label="미국 테마"><small>{row.us_group_name}</small><strong>{row.us_theme_name}</strong></td>
              <td className="us-kr-group-us" data-label="US D-1"><strong className={tone(row.latest_value)}>{pct(row.latest_value)}</strong><small>전일 대비 <span className={tone(row.delta)}>{pct(row.delta)}p</span></small></td>
              <td className="us-kr-group-us group-end" data-label="확산"><strong>{row.breadth_ratio == null ? "-" : `${Math.round(row.breadth_ratio * 100)}%`}</strong><small>{row.up_count}↑ · {row.down_count}↓ · {row.valid_stock_count}종</small></td>
              <td className="us-kr-table-arrow" aria-label="연결">→</td>
              <td className="us-kr-group-kr group-start" data-label="국내 테마"><button type="button" className="us-kr-theme-detail-trigger us-kr-theme-anchor" onClick={() => onOpenThemeDetail(row.kr_theme_id)} aria-label={`${row.kr_theme_name} 테마 상세 보기`}><small>{row.kr_group_name}</small><strong>{row.kr_theme_name}</strong><span aria-hidden="true">›</span></button></td>
              <td className="us-kr-group-kr" data-label="과거 동일조건 반응"><button type="button" className="us-kr-theme-detail-trigger us-kr-history-trigger" onClick={() => onOpenThemeDetail(row.kr_theme_id)} aria-label={`${row.kr_theme_name} 과거 동일조건 반응 및 테마 상세 보기`}>{row.available ? (row.threshold_condition ? <div className="us-kr-history-response" title={`과거 동일조건 중앙값 ${pct(row.median_kr_return)}`}><div><span className="us-kr-history-condition"><strong>{row.threshold_condition}</strong><small>: {row.sample_count}건</small></span><em>동행 {row.response_rate == null ? "-" : `${Math.round(row.response_rate)}%`}</em></div><small className="us-kr-history-values"><span>평균 <b className={tone(row.avg_kr_return)}>{pct(row.avg_kr_return)}</b></span><span>중앙 <b className={tone(row.median_kr_return)}>{pct(row.median_kr_return)}</b></span></small></div> : <span className="us-kr-neutral-label">중립 · 비교 조건 없음</span>) : <span className="us-kr-missing-label">{row.missing_reason}</span>}</button></td>
              <td className="us-kr-group-kr group-end" data-label="현재 반응"><button type="button" className="us-kr-theme-detail-trigger" onClick={() => onOpenThemeDetail(row.kr_theme_id)} aria-label={`${row.kr_theme_name} 현재 반응 및 테마 상세 보기`} title={`전일 기준일 ${row.previous_kr_date || "-"}`}><div className="us-kr-live-response-cell"><span><small>전일</small><strong className={tone(row.previous_kr_return)}>{pct(row.previous_kr_return)}</strong></span><span><small>{metric === "theme_strength" ? "현재 강도" : "현재 등락"}{timeLabel(snapshot?.snapshot_at || null) ? ` · ${timeLabel(snapshot?.snapshot_at || null)}` : ""}</small><strong className={tone(liveValue)}>{pct(liveValue)}</strong></span><em className={`us-kr-live-status ${status}`}>{statusLabel[status]}</em></div></button></td>
              <td data-label="작업"><button className="secondary-button" type="button" onClick={() => onOpenAnalysis(row.link_id, windowSize, metric, direction)}>상세 분석</button></td>
            </tr>;
          })}
          {!loading && items.length === 0 ? <tr><td colSpan={9} className="empty-table-cell">조건에 맞는 연결 테마가 없습니다.</td></tr> : null}
        </tbody></table></div>
      </SectionCard>
    </> : loading ? <SectionCard className="us-kr-placeholder-card"><p>오늘의 연결 상태를 계산하고 있습니다.</p></SectionCard> : null}
  </div>;
}
