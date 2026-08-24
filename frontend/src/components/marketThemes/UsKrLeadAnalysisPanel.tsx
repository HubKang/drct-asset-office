import { useEffect, useMemo, useState } from "react";

import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { UsKrLeadAnalysis, UsKrLeadPair, UsKrThemeLink } from "@/types/usKrThemeLink";

type Props = { links: UsKrThemeLink[]; overviewLoading: boolean; initialLinkId?: number; initialWindow?: number; initialMetric?: Metric };
type Metric = "theme_strength" | "simple_return";
const PAGE_SIZE = 20;
const pct = (value: number | null, digits = 2) => value === null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
const rate = (value: number | null, digits = 2) => value === null ? "-" : `${value.toFixed(digits)}%`;
const corr = (value: number | null) => value === null ? "-" : value.toFixed(3);
const tone = (value: number | null) => value === null ? "" : value > 0 ? "positive" : value < 0 ? "negative" : "flat";

function ScatterPlot({ data }: { data: UsKrLeadAnalysis }) {
  const width = 820, height = 360, left = 62, right = 26, top = 24, bottom = 48;
  const pairs = data.pairs;
  const maxX = Math.max(1, ...pairs.map((row) => Math.abs(row.us_value))) * 1.12;
  const maxY = Math.max(1, ...pairs.map((row) => Math.abs(row.kr_return))) * 1.12;
  const sx = (value: number) => left + ((value + maxX) / (maxX * 2)) * (width - left - right);
  const sy = (value: number) => top + ((maxY - value) / (maxY * 2)) * (height - top - bottom);
  const slope = data.metrics.regression_slope;
  const intercept = data.metrics.regression_intercept;
  return <div className="us-kr-scatter-wrap">
    <svg className="us-kr-scatter" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="미국 테마 지표와 다음 국내 거래일 등락률 산점도">
      <rect x={left} y={top} width={width - left - right} height={height - top - bottom} rx="8" fill="#f8fafc" />
      <rect x={sx(0)} y={top} width={width - right - sx(0)} height={sy(0) - top} fill="#fff1f2" opacity=".34" />
      <rect x={left} y={sy(0)} width={sx(0) - left} height={height - bottom - sy(0)} fill="#eff6ff" opacity=".42" />
      <line x1={left} x2={width - right} y1={sy(0)} y2={sy(0)} className="axis-zero" />
      <line x1={sx(0)} x2={sx(0)} y1={top} y2={height - bottom} className="axis-zero" />
      {slope !== null && intercept !== null ? <line x1={sx(-maxX)} y1={sy(slope * -maxX + intercept)} x2={sx(maxX)} y2={sy(slope * maxX + intercept)} className="regression-line" /> : null}
      {pairs.map((row) => <circle key={`${row.us_trade_date}-${row.kr_trade_date}`} cx={sx(row.us_value)} cy={sy(row.kr_return)} r="5.5" className={row.direction_match === true ? "match" : row.direction_match === false ? "mismatch" : "neutral"}><title>{`${row.us_trade_date} ${data.us_metric_label} ${pct(row.us_value)} → ${row.kr_trade_date} 국내 ${pct(row.kr_return)} · ${row.calendar_gap_days}일`}</title></circle>)}
      <text x={(left + width - right) / 2} y={height - 10} textAnchor="middle">미국 D-1 · {data.us_metric_label} (%)</text>
      <text transform={`translate(17 ${(top + height - bottom) / 2}) rotate(-90)`} textAnchor="middle">국내 D0 · 일별 등락률 (%)</text>
      <text x={width - right - 7} y={top + 17} textAnchor="end" className="quadrant-label">동반 상승</text>
      <text x={left + 7} y={height - bottom - 10} className="quadrant-label">동반 하락</text>
    </svg>
    <div className="us-kr-scatter-legend"><span><i className="match" />방향 일치</span><span><i className="mismatch" />방향 불일치</span><span><i className="line" />회귀선</span></div>
  </div>;
}

export default function UsKrLeadAnalysisPanel({ links, overviewLoading, initialLinkId = 0, initialWindow = 120, initialMetric = "theme_strength" }: Props) {
  const activeLinks = useMemo(() => links.filter((row) => row.active === 1), [links]);
  const [linkId, setLinkId] = useState(initialLinkId);
  const [windowSize, setWindowSize] = useState(initialWindow);
  const [metric, setMetric] = useState<Metric>(initialMetric);
  const [data, setData] = useState<UsKrLeadAnalysis | null>(null);
  const [thresholdDirection, setThresholdDirection] = useState<"UP" | "DOWN">("UP");
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (activeLinks.length && !activeLinks.some((row) => row.id === linkId)) setLinkId(activeLinks[0].id);
  }, [activeLinks, linkId]);
  useEffect(() => {
    if (!linkId) { setData(null); return; }
    let cancelled = false;
    setLoading(true); setError("");
    repositories.usKrThemeLinks.leadAnalysis(linkId, windowSize, metric).then((response) => {
      if (!cancelled) { setData(response); setPage(1); }
    }).catch((reason) => {
      if (!cancelled) { setData(null); setError(reason instanceof Error ? reason.message : "선행 분석을 불러오지 못했습니다."); }
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [linkId, windowSize, metric, refreshKey]);

  if (!overviewLoading && activeLinks.length === 0) return <SectionCard title="테마별 선행 분석" className="us-kr-placeholder-card"><p>먼저 한미테마연계에서 분석할 미국·국내 테마를 연결해 주세요.</p></SectionCard>;
  const metrics = data?.metrics;
  const thresholdRows = data?.thresholds.filter((row) => row.direction === thresholdDirection) || [];
  const pageCount = Math.max(1, Math.ceil((data?.pairs.length || 0) / PAGE_SIZE));
  const pageRows = data?.pairs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) || [];
  return <div className="space-y-4 us-kr-lead-analysis">
    <SectionCard title="테마별 선행 분석" className="us-kr-lead-toolbar-card">
      <p className="us-kr-analysis-intro">미국 거래일의 테마 지표와 그 이후 첫 국내 실제 거래일의 등락률을 1:1로 비교합니다. 휴장 간격은 최대 7일입니다.</p>
      <div className="us-kr-lead-toolbar">
        <label className="us-kr-toolbar-field us-kr-theme-select"><span>연결 테마</span><select className="select-control" value={linkId} onChange={(e) => setLinkId(Number(e.target.value))}>{activeLinks.map((row) => <option key={row.id} value={row.id}>{row.us_theme_name} → {row.kr_theme_name}</option>)}</select></label>
        <label className="us-kr-toolbar-field"><span>분석 기간</span><select className="select-control" value={windowSize} onChange={(e) => setWindowSize(Number(e.target.value))}><option value={60}>최근 60쌍</option><option value={120}>최근 120쌍</option><option value={250}>최근 250쌍</option><option value={0}>전체</option></select></label>
        <fieldset className="us-kr-toolbar-field us-kr-metric-field"><legend>미국 기준 지표</legend><div className="us-kr-segmented"><button type="button" className={metric === "theme_strength" ? "active" : ""} onClick={() => setMetric("theme_strength")}>테마강도</button><button type="button" className={metric === "simple_return" ? "active" : ""} onClick={() => setMetric("simple_return")}>단순등락률</button></div></fieldset>
        <button className="secondary-button us-kr-refresh-button" type="button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}>↻ 새로고침</button>
      </div>
    </SectionCard>
    {error ? <p className="form-error-message" role="alert">{error}</p> : null}
    {loading && !data ? <SectionCard className="us-kr-placeholder-card"><p>분석 데이터를 계산하고 있습니다.</p></SectionCard> : null}
    {data ? <>
      <SectionCard className="us-kr-lead-result-card">
        <div className="us-kr-pair-heading"><div><small>미국 US · D-1</small><strong>{data.link.us_theme_name}</strong><span>{data.link.us_group_name} · {data.us_metric_label}</span></div><b aria-hidden="true">→</b><div><small>국내 KRX · D0</small><strong>{data.link.kr_theme_name}</strong><span>{data.link.kr_group_name} · {data.kr_metric_label}</span></div><p className="us-kr-latest-match"><span>최근 매칭</span><strong>{data.latest_us_date || "-"} → {data.latest_kr_date || "-"}</strong></p></div>
        <div className="us-kr-lead-summary">
          <article><span>유효 표본</span><strong>{metrics?.sample_count || 0}쌍</strong><small>후보 {metrics?.candidate_count || 0} · 제외 {metrics?.excluded_count || 0}</small><em>{metrics?.sample_guidance}</em></article>
          <article><span>방향 일치율</span><strong>{rate(metrics?.direction_match_rate ?? null)}</strong><small>유효 방향 {metrics?.direction_sample_count || 0}쌍</small></article>
          <article><span>상승 → 상승</span><strong>{rate(metrics?.us_up_kr_up_rate ?? null)}</strong><small>하락 → 하락 {rate(metrics?.us_down_kr_down_rate ?? null)}</small></article>
          <article><span>국내 평균 반응</span><strong className={tone(metrics?.avg_kr_return ?? null)}>{pct(metrics?.avg_kr_return ?? null)}</strong><small>중앙값 {pct(metrics?.median_kr_return ?? null)}</small></article>
          <article><span>Pearson 상관</span><strong>{corr(metrics?.pearson_correlation ?? null)}</strong><small>Spearman {corr(metrics?.spearman_correlation ?? null)}</small></article>
        </div>
      </SectionCard>
      <div className="us-kr-analysis-grid">
        <SectionCard title="조건별 국내 반응" className="us-kr-analysis-detail-card us-kr-threshold-card">
          <div className="us-kr-segmented compact"><button type="button" className={thresholdDirection === "UP" ? "active" : ""} onClick={() => setThresholdDirection("UP")}>미국 상승</button><button type="button" className={thresholdDirection === "DOWN" ? "active" : ""} onClick={() => setThresholdDirection("DOWN")}>미국 하락</button></div>
          <div className="table-scroll"><table className="data-table"><thead><tr><th>조건</th><th>표본</th><th>동방향 반응</th><th>국내 평균</th><th>중앙값</th></tr></thead><tbody>{thresholdRows.map((row) => <tr key={`${row.direction}-${row.threshold}`}><td><strong>{row.condition}</strong></td><td>{row.sample_count}쌍</td><td>{rate(row.response_rate)}</td><td className={tone(row.avg_kr_return)}>{pct(row.avg_kr_return)}</td><td className={tone(row.median_kr_return)}>{pct(row.median_kr_return)}</td></tr>)}</tbody></table></div>
        </SectionCard>
        <SectionCard title="미국 D-1 → 국내 D0 분포" className="us-kr-analysis-detail-card us-kr-scatter-card"><ScatterPlot data={data} /></SectionCard>
      </div>
      <SectionCard title={`실제 거래일 매칭 · ${data.pairs.length}쌍`} className="us-kr-pair-table-card">
        <div className="table-scroll"><table className="data-table"><thead><tr><th>미국 거래일</th><th>{data.us_metric_label}</th><th>국내 거래일</th><th>국내 등락률</th><th>간격</th><th>방향</th></tr></thead><tbody>{pageRows.map((row: UsKrLeadPair) => <tr key={`${row.us_trade_date}-${row.kr_trade_date}`}><td>{row.us_trade_date}</td><td className={tone(row.us_value)}>{pct(row.us_value)}</td><td>{row.kr_trade_date}</td><td className={tone(row.kr_return)}>{pct(row.kr_return)}</td><td>{row.calendar_gap_days}일</td><td><span className={`us-kr-direction-badge ${row.direction_match === true ? "match" : row.direction_match === false ? "mismatch" : "neutral"}`}>{row.direction_match === true ? "일치" : row.direction_match === false ? "불일치" : "중립 제외"}</span></td></tr>)}</tbody></table></div>
        <footer className="us-kr-pagination"><span>{page} / {pageCount} 페이지</span><div><button className="secondary-button" type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>이전</button><button className="secondary-button" type="button" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>다음</button></div></footer>
      </SectionCard>
    </> : null}
  </div>;
}
