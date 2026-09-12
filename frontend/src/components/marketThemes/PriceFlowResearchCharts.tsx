import type { MarketThemePriceFlowRadarProfile, MarketThemePriceFlowResearchResponse } from "@/types/marketTheme";

const BASELINE_RATE = .2;
const DELTA_SCALE_POINTS = 5;
const AXES: Array<{ key: keyof MarketThemePriceFlowRadarProfile; label: string; shortLabel: string }> = [
  { key: "price_strength", label: "가격 강도", shortLabel: "가격" },
  { key: "flow_strength", label: "수급 강도", shortLabel: "수급" },
  { key: "flow_acceleration", label: "수급 가속", shortLabel: "가속" },
  { key: "breadth", label: "확산", shortLabel: "확산" },
  { key: "sustainability", label: "지속 가능성", shortLabel: "지속" },
];
const pct = (value: number | null | undefined) => value == null ? "-" : `${(value * 100).toFixed(1)}%`;
const point = (index: number, value: number) => {
  const angle = -Math.PI / 2 + index * Math.PI * 2 / AXES.length;
  return [120 + Math.cos(angle) * 76 * value, 102 + Math.sin(angle) * 76 * value];
};
const polygon = (profile: MarketThemePriceFlowRadarProfile, ratio = 1) => AXES.map((axis, index) => {
  const value = ratio === 1 ? Math.max(0, Math.min(1, Number(profile[axis.key] ?? 0) / 100)) : ratio;
  return point(index, value).join(",");
}).join(" ");

export default function PriceFlowResearchCharts({ data }: { data: MarketThemePriceFlowResearchResponse }) {
  const bestStage = [...data.stage_metrics].sort((a, b) => b.top20_rate - a.top20_rate)[0];
  const factors = [...data.radar_axis_results].sort((a, b) => Math.abs(b.difference ?? 0) - Math.abs(a.difference ?? 0));
  const strongest = factors[0];
  const second = factors[1];
  const labelOf = (axis: string) => AXES.find((item) => item.key === axis)?.label ?? axis;
  const subtleDifference = Math.abs(strongest?.difference ?? 0) < 5;
  const summary = strongest
    ? `이번 표본에서는 ${labelOf(strongest.axis)}${second ? `와 ${labelOf(second.axis)}` : ""}이 성공·실패를 가장 크게 구분했습니다.${subtleDifference ? " 전체 차이는 크지 않아 단독 판단보다는 참고용으로 사용합니다." : ""}`
    : "성공과 실패를 구분할 표본이 아직 충분하지 않습니다.";

  return <section className="price-flow-research-visuals">
    <article className="price-flow-stage-bars">
      <header><div><h4>가격·수급 단계별 다음날 강세 성과</h4><p>각 단계의 과거 사례가 다음날 전체 테마 상위 20%에 진입한 비율입니다.</p></div><span className="price-flow-basis-info" title={`${data.stage_version} · ${data.evaluated_dates}거래일 · ${data.sample_count}표본`}>ⓘ 가격·수급 단계 기준</span></header>
      <div className="price-flow-stage-delta-head"><span>단계</span><span>전체 기준 20%</span><span>실제 진입률</span><span>기준 대비</span><span>표본수</span></div>
      <div className="price-flow-stage-delta-list">{data.stage_metrics.map((item) => {
        const deltaPoints = (item.top20_rate - BASELINE_RATE) * 100;
        const width = Math.min(50, Math.abs(deltaPoints) / DELTA_SCALE_POINTS * 50);
        return <div className="price-flow-stage-row" key={item.stage_code}>
          <span className={`theme-observation-state stage-${item.stage_code.toLowerCase()}`}>{item.stage_label}</span>
          <div className={`stage-delta-track ${deltaPoints >= 0 ? "is-positive" : "is-negative"}`} title={`전체 기준 20% 대비 ${deltaPoints >= 0 ? "+" : ""}${deltaPoints.toFixed(1)}%p`}><i className="stage-delta-baseline" /><b style={{ width: `${width}%`, left: deltaPoints >= 0 ? "50%" : `${50 - width}%` }} /></div>
          <strong>{pct(item.top20_rate)}</strong>
          <em className={deltaPoints >= 0 ? "is-positive" : "is-negative"}>{deltaPoints >= 0 ? "+" : ""}{deltaPoints.toFixed(1)}%p</em>
          <small>표본 {item.sample_count.toLocaleString()}</small>
          {item.stage_code === bestStage?.stage_code ? <mark>현재 가장 양호</mark> : null}
        </div>;
      })}</div>
    </article>

    <article className="price-flow-success-failure-radar">
      <header><div><h4>성공을 가른 요인</h4><p>다음날 성공 사례와 실패 사례의 평균 요인을 비교합니다.</p></div><div className="price-flow-radar-legend"><span className="is-success">성공</span><span className="is-failure">실패</span></div></header>
      <div className="price-flow-radar-body"><svg viewBox="0 0 240 205" role="img" aria-label="성공과 실패 평균 가격 수급 Radar 비교">
        {[.25, .5, .75, 1].map((ratio) => <polygon key={ratio} points={polygon(data.success_radar, ratio)} className="price-flow-radar-grid" />)}
        {AXES.map((axis, index) => { const [x, y] = point(index, 1); const [lx, ly] = point(index, 1.18); return <g key={axis.key}><line x1="120" y1="102" x2={x} y2={y} className="price-flow-radar-grid" /><text x={lx} y={ly}>{axis.shortLabel}</text></g>; })}
        <polygon points={polygon(data.failure_radar)} className="price-flow-radar-failure" />
        <polygon points={polygon(data.success_radar)} className="price-flow-radar-success" />
      </svg><div className="price-flow-factor-bars">{factors.map((factor) => {
        const difference = factor.difference ?? 0;
        const width = Math.min(50, Math.abs(difference) / DELTA_SCALE_POINTS * 50);
        return <div key={factor.axis}><span>{labelOf(factor.axis)}</span><i className={difference >= 0 ? "is-positive" : "is-negative"}><b style={{ width: `${width}%`, left: difference >= 0 ? "50%" : `${50 - width}%` }} /></i><strong className={difference >= 0 ? "is-positive" : "is-negative"}>{difference >= 0 ? "+" : ""}{difference.toFixed(1)}</strong></div>;
      })}</div></div>
      <footer>{summary}</footer>
    </article>
  </section>;
}
