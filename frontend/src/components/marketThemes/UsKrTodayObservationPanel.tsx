import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { UsKrTodayObservation, UsKrTodayObservationItem } from "@/types/usKrThemeLink";

export type TodayMetric = "theme_strength" | "simple_return";
export type TodayDirection = "ALL" | "UP" | "DOWN";
type Props = {
  initialWindow: number;
  initialMetric: TodayMetric;
  initialDirection: TodayDirection;
  onConfigChange: (window: number, metric: TodayMetric, direction: TodayDirection) => void;
  onOpenAnalysis: (linkId: number, window: number, metric: TodayMetric, direction: TodayDirection) => void;
};

const pct = (value: number | null, digits = 2) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
const tone = (value: number | null) => value == null ? "" : value > 0 ? "positive" : value < 0 ? "negative" : "flat";

export default function UsKrTodayObservationPanel({ initialWindow, initialMetric, initialDirection, onConfigChange, onOpenAnalysis }: Props) {
  const [windowSize, setWindowSize] = useState(initialWindow);
  const [metric, setMetric] = useState<TodayMetric>(initialMetric);
  const [direction, setDirection] = useState<TodayDirection>(initialDirection);
  const [refreshKey, setRefreshKey] = useState(0);
  const [data, setData] = useState<UsKrTodayObservation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { onConfigChange(windowSize, metric, direction); }, [windowSize, metric, direction]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    repositories.usKrThemeLinks.todayObservation(windowSize, metric).then((response) => {
      if (!cancelled) setData(response);
    }).catch((reason) => {
      if (!cancelled) { setData(null); setError(reason instanceof Error ? reason.message : "오늘의 연계 관찰을 불러오지 못했습니다."); }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [windowSize, metric, refreshKey]);

  const items = useMemo(() => {
    const rows = (data?.items || []).filter((row) => direction === "ALL" || row.threshold_direction === direction);
    return [...rows].sort((a, b) => {
      if (a.available !== b.available) return a.available ? -1 : 1;
      const av = a.latest_value ?? 0, bv = b.latest_value ?? 0;
      const primary = direction === "UP" ? bv - av : direction === "DOWN" ? av - bv : Math.abs(bv) - Math.abs(av);
      if (primary) return primary;
      const response = (b.response_rate ?? -1) - (a.response_rate ?? -1);
      return response || b.sample_count - a.sample_count;
    });
  }, [data, direction]);

  return <div className="space-y-4 us-kr-today-observation">
    <SectionCard title="오늘의 연계 관찰" className="us-kr-today-toolbar-card">
      <p className="us-kr-analysis-intro">직전 미국 실제 거래일의 연결 테마 상태와 과거 동일 조건에서 나타난 국내 D0 반응을 함께 확인합니다.</p>
      <div className="us-kr-today-toolbar">
        <label className="us-kr-toolbar-field"><span>분석 기간</span><select className="select-control" value={windowSize} onChange={(event) => setWindowSize(Number(event.target.value))}><option value={60}>최근 60쌍</option><option value={120}>최근 120쌍</option><option value={250}>최근 250쌍</option><option value={0}>전체</option></select></label>
        <fieldset className="us-kr-toolbar-field"><legend>미국 기준 지표</legend><div className="us-kr-segmented"><button type="button" className={metric === "theme_strength" ? "active" : ""} onClick={() => setMetric("theme_strength")}>테마강도</button><button type="button" className={metric === "simple_return" ? "active" : ""} onClick={() => setMetric("simple_return")}>단순등락률</button></div></fieldset>
        <fieldset className="us-kr-toolbar-field us-kr-direction-field"><legend>관찰 방향</legend><div className="us-kr-segmented"><button type="button" className={direction === "ALL" ? "active" : ""} onClick={() => setDirection("ALL")}>전체</button><button type="button" className={direction === "UP" ? "active" : ""} onClick={() => setDirection("UP")}>상승</button><button type="button" className={direction === "DOWN" ? "active" : ""} onClick={() => setDirection("DOWN")}>하락</button></div></fieldset>
        <button className="secondary-button us-kr-refresh-button" type="button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}><RefreshCw size={14} /> 새로고침</button>
      </div>
    </SectionCard>
    {error ? <p className="form-error-message" role="alert">{error}</p> : null}
    {data ? <>
      <SectionCard className="us-kr-today-overview-card">
        <div className="us-kr-today-date-flow"><span><small>미국 US · D-1</small><strong>{data.latest_us_date || "-"}</strong></span><b aria-hidden="true">→</b><span><small>국내 KRX · D0</small><strong>{data.kr_target_date || "다음 실제 거래일 대기"}</strong></span><em>휴장 간격 최대 {data.max_calendar_gap_days}일</em></div>
        <div className="us-kr-today-summary">
          <article><span>활성 연결</span><strong>{data.summary.linked_count}</strong></article><article><span>관찰 가능</span><strong>{data.summary.available_count}</strong></article><article><span>데이터 없음</span><strong>{data.summary.missing_count}</strong></article><article><span>상승 / 하락</span><strong>{data.summary.up_count} / {data.summary.down_count}</strong></article>
        </div>
      </SectionCard>
      <SectionCard title={`연계 관찰 목록 · ${items.length}`} className="us-kr-today-list-card">
        <div className="table-scroll"><table className="data-table us-kr-today-table"><thead><tr><th>순위</th><th>미국 테마</th><th>최신 상태</th><th>확산</th><th aria-label="연결">연결</th><th>국내 테마</th><th>과거 동일 조건</th><th>국내 평균 D0</th><th>작업</th></tr></thead><tbody>
          {items.map((row: UsKrTodayObservationItem, index) => <tr key={row.link_id} className={!row.available ? "is-missing" : ""}>
            <td data-label="순위"><strong>{index + 1}</strong></td>
            <td data-label="미국 테마"><small>{row.us_group_name}</small><strong>{row.us_theme_name}</strong></td>
            <td data-label="최신 상태"><strong className={tone(row.latest_value)}>{pct(row.latest_value)}</strong><small>전일 대비 <span className={tone(row.delta)}>{pct(row.delta)}p</span></small></td>
            <td data-label="확산"><strong>{row.breadth_ratio == null ? "-" : `${Math.round(row.breadth_ratio * 100)}%`}</strong><small>{row.up_count}↑ · {row.down_count}↓ / {row.valid_stock_count}</small></td>
            <td className="us-kr-table-arrow" aria-label="연결">→</td>
            <td data-label="국내 테마"><small>{row.kr_group_name}</small><strong>{row.kr_theme_name}</strong></td>
            <td data-label="과거 동일 조건">{row.available ? (row.threshold_condition ? <><strong>{row.threshold_condition}</strong><small>동방향 {row.response_rate == null ? "-" : `${row.response_rate.toFixed(1)}%`} · {row.sample_count}쌍 · {row.sample_guidance}</small></> : <span className="us-kr-neutral-label">중립 · 비교 조건 없음</span>) : <span className="us-kr-missing-label">{row.missing_reason}</span>}</td>
            <td data-label="국내 평균 D0"><strong className={tone(row.avg_kr_return)}>{pct(row.avg_kr_return)}</strong></td>
            <td data-label="작업"><button className="secondary-button" type="button" onClick={() => onOpenAnalysis(row.link_id, windowSize, metric, direction)}>상세 분석</button></td>
          </tr>)}
          {!loading && items.length === 0 ? <tr><td colSpan={9} className="empty-table-cell">조건에 맞는 연결 테마가 없습니다.</td></tr> : null}
        </tbody></table></div>
      </SectionCard>
    </> : loading ? <SectionCard className="us-kr-placeholder-card"><p>오늘의 연결 상태를 계산하고 있습니다.</p></SectionCard> : null}
  </div>;
}
