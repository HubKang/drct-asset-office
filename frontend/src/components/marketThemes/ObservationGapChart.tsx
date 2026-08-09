import type { CSSProperties } from "react";
import type { MarketThemeObservationItem } from "@/types/marketTheme";

const clamp = (value: number) => Math.max(0, Math.min(100, value));
const valueText = (value: number | null | undefined) => value == null ? "-" : value.toFixed(1);
const gapText = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(1)}`;

export default function ObservationGapChart(props: {
  items: MarketThemeObservationItem[];
  onThemeClick: (themeId: number) => void;
}) {
  const hasActual = props.items.some((item) => item.actual_relative_strength != null);

  return <section className="observation-gap-chart" aria-labelledby="observation-gap-chart-title">
    <header>
      <div><h3 id="observation-gap-chart-title">{hasActual ? "관찰 vs 실측 Top10" : "D+1 관찰순위 Top10"}</h3><p>관찰점수와 실제 상대강도의 차이를 동일한 0~100 기준으로 비교합니다.</p></div>
      <div className="observation-gap-legend" aria-label="그래프 범례"><span className="is-predicted">예측</span><span className="is-actual">실측</span></div>
    </header>
    <div className="observation-gap-axis" aria-hidden="true"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
    <div className="observation-gap-rows">
      {props.items.map((item) => {
        const predicted = item.relative_strength_score;
        const actual = item.actual_relative_strength;
        const gap = item.relative_strength_gap;
        const predictedPosition = clamp(predicted ?? 0);
        const actualPosition = actual == null ? null : clamp(actual);
        const gapLeft = actualPosition == null ? predictedPosition : Math.min(predictedPosition, actualPosition);
        const gapWidth = actualPosition == null ? 0 : Math.abs(predictedPosition - actualPosition);
        const gapTone = gap == null ? "waiting" : gap > 0 ? "positive" : gap < 0 ? "negative" : "neutral";
        const style = {
          "--predicted-position": `${predictedPosition}%`,
          "--actual-position": `${actualPosition ?? predictedPosition}%`,
          "--gap-left": `${gapLeft}%`,
          "--gap-width": `${gapWidth}%`,
        } as CSSProperties;
        const accessible = actual == null
          ? `${item.observation_rank ?? "-"}위 ${item.theme_name}, 예측 관찰점수 ${valueText(predicted)}, 실측 대기`
          : `${item.observation_rank ?? "-"}위 ${item.theme_name}, 예측 관찰점수 ${valueText(predicted)}, 실측 상대강도 ${valueText(actual)}, 상대강도 차이 ${gapText(gap)}`;
        const tooltip = `${accessible}${item.current_score == null ? "" : `\nCURRENT ${valueText(item.current_score)}`}${item.refreshed_score == null ? "" : `\nREFRESHED ${valueText(item.refreshed_score)}`}`;
        return <button type="button" key={item.theme_id} className={`observation-gap-row is-${gapTone}`} style={style} aria-label={accessible} title={tooltip} onClick={() => props.onThemeClick(item.theme_id)}>
          <b>{item.observation_rank ?? "-"}</b>
          <span className="observation-gap-theme">{item.theme_name}</span>
          <span className="observation-gap-plot">
            <i className="observation-gap-rail"><em className="observation-gap-range" />{predicted != null ? <span className="observation-gap-marker is-predicted" /> : null}{actualPosition != null ? <span className="observation-gap-marker is-actual" /> : null}</i>
            <small><span>예측 {valueText(predicted)}</span><span>{actual == null ? "실측 대기" : `실측 ${valueText(actual)}`}</span></small>
          </span>
          <strong>{gap == null ? "대기" : gapText(gap)}</strong>
        </button>;
      })}
    </div>
  </section>;
}
