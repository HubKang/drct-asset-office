import type { MarketThemeObservationItem } from "@/types/marketTheme";

const AXES = [
  { key: "price_score", label: "가격" },
  { key: "flow_score", label: "수급" },
  { key: "breadth_score", label: "확산" },
  { key: "technical_score", label: "기술" },
  { key: "data_coverage_rate", label: "완전성", ratio: true },
] as const;
const cx = 120;
const cy = 96;
const radius = 72;
const point = (index: number, ratio: number) => {
  const angle = -Math.PI / 2 + index * Math.PI * 2 / AXES.length;
  return [cx + Math.cos(angle) * radius * ratio, cy + Math.sin(angle) * radius * ratio] as const;
};
const polygon = (ratio: number) => AXES.map((_, index) => point(index, ratio).join(",")).join(" ");
const scoreText = (value: number | null | undefined) => value == null ? "-" : value.toFixed(1);
const gapText = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(1)}`;

export default function ObservationRadarGrid(props: {
  items: MarketThemeObservationItem[];
  statusNames: Record<string, string>;
  onThemeClick: (themeId: number) => void;
}) {
  return <section className="observation-radar-section" aria-labelledby="observation-radar-title">
    <header><div><h3 id="observation-radar-title">테마 구조 비교</h3><p>가격·수급·확산·기술·완전성의 모양으로 관찰점수의 구조를 비교합니다.</p></div><span>동일 축 · 최대 100</span></header>
    <div className="observation-radar-grid">
      {props.items.map((item) => {
        const values = AXES.map((axis) => {
          const raw = item[axis.key];
          return raw == null ? null : Math.max(0, Math.min(100, "ratio" in axis && axis.ratio ? raw * 100 : raw));
        });
        const complete = values.every((value) => value != null);
        const dataPoints = complete ? values.map((value, index) => point(index, (value ?? 0) / 100).join(",")).join(" ") : null;
        const detail = AXES.map((axis, index) => `${axis.label} ${scoreText(values[index])}`).join(", ");
        const actualText = item.actual_relative_strength == null ? "실측 대기" : `실측 ${scoreText(item.actual_relative_strength)} · Gap ${gapText(item.relative_strength_gap)}`;
        return <button type="button" key={item.theme_id} className="observation-radar-card" onClick={() => props.onThemeClick(item.theme_id)} aria-label={`${item.observation_rank ?? "-"}위 ${item.theme_name}, ${detail}, ${actualText}`} title={detail}>
          <header><b>#{item.observation_rank ?? "-"}</b><span className={`theme-observation-state state-${item.status_code.toLowerCase()}`}>{props.statusNames[item.status_code] ?? item.status_code}</span></header>
          <div className="observation-radar-visual">
            <svg viewBox="0 0 240 192" role="img" aria-label={`${item.theme_name} 5축 구조`}>
              {[.25, .5, .75, 1].map((ratio) => <polygon key={ratio} points={polygon(ratio)} className="observation-radar-grid-line" />)}
              {AXES.map((axis, index) => { const [x, y] = point(index, 1); const [labelX, labelY] = point(index, 1.2); return <g key={axis.key}><line x1={cx} y1={cy} x2={x} y2={y} className="observation-radar-axis" /><circle cx={labelX} cy={labelY} r="16" className="observation-radar-axis-hit"><title>{axis.label} {scoreText(values[index])}</title></circle><text x={labelX} y={labelY} className="observation-radar-label">{axis.label}</text></g>; })}
              {dataPoints ? <><polygon points={dataPoints} className="observation-radar-data" />{values.map((value, index) => { const [x, y] = point(index, (value ?? 0) / 100); return <circle key={AXES[index].key} cx={x} cy={y} r="3" className="observation-radar-point"><title>{AXES[index].label} {scoreText(value)}</title></circle>; })}</> : null}
            </svg>
            <span className="observation-radar-center"><b>{item.theme_name}</b><strong>{scoreText(item.relative_strength_score)}</strong></span>
          </div>
          <footer className={item.relative_strength_gap == null ? "is-waiting" : item.relative_strength_gap > 0 ? "is-positive" : item.relative_strength_gap < 0 ? "is-negative" : "is-neutral"}>{complete ? actualText : `구조 데이터 부족 · ${actualText}`}</footer>
        </button>;
      })}
    </div>
  </section>;
}
