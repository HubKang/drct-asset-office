import type { CSSProperties } from "react";
import { ChevronLeft, ChevronRight, Minus, MoveHorizontal } from "lucide-react";
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
      <div><h3 id="observation-gap-chart-title">{hasActual ? "예측 vs 실제 Top10" : "D+1 후보 Ranking Top10"}</h3><p>D+1 후보점수의 유니버스 Percentile과 실제 상대강도 Percentile을 동일한 0~100 기준으로 비교합니다.</p></div>
      <div className="observation-gap-legend" aria-label="그래프 범례"><span className="is-predicted">예측</span><span className="is-actual"><MoveHorizontal aria-hidden="true" size={13} strokeWidth={2.5} />실측</span></div>
    </header>
    <div className="observation-gap-axis" aria-hidden="true"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
    <div className="observation-gap-rows">
      {props.items.map((item) => {
        const predicted = item.prediction_percentile;
        const actual = item.actual_relative_strength;
        const gap = item.relative_strength_gap;
        const predictedPosition = clamp(predicted ?? 0);
        const actualPosition = actual == null ? null : clamp(actual);
        const gapLeft = actualPosition == null ? predictedPosition : Math.min(predictedPosition, actualPosition);
        const gapWidth = actualPosition == null ? 0 : Math.abs(predictedPosition - actualPosition);
        const comparison = predicted == null || actual == null
          ? "waiting"
          : actual > predicted
            ? "actual-higher"
            : actual < predicted
              ? "actual-lower"
              : "equal";
        const actualDirectionIcon = comparison === "actual-higher"
          ? <ChevronRight aria-hidden="true" size={13} strokeWidth={3} />
          : comparison === "actual-lower"
            ? <ChevronLeft aria-hidden="true" size={13} strokeWidth={3} />
            : <Minus aria-hidden="true" size={12} strokeWidth={3} />;
        const style = {
          "--predicted-position": `${predictedPosition}%`,
          "--actual-position": `${actualPosition ?? predictedPosition}%`,
          "--gap-left": `${gapLeft}%`,
          "--gap-width": `${gapWidth}%`,
        } as CSSProperties;
        const accessible = actual == null
          ? `${item.observation_rank ?? "-"}위 ${item.theme_name}, 예측 Percentile ${valueText(predicted)}, 실측 대기`
          : `${item.observation_rank ?? "-"}위 ${item.theme_name}, 예측 Percentile ${valueText(predicted)}, 실제 상대강도 Percentile ${valueText(actual)}, ${actual > (predicted ?? actual) ? "실측이 예측보다 큼" : actual < (predicted ?? actual) ? "실측이 예측보다 작음" : "예측과 실측이 같음"}, Percentile 차이 ${gapText(gap)}`;
        const tooltip = `${accessible}${item.current_score == null ? "" : `\nCURRENT ${valueText(item.current_score)}`}${item.refreshed_score == null ? "" : `\nREFRESHED ${valueText(item.refreshed_score)}`}`;
        return <button type="button" key={item.theme_id} className={`observation-gap-row is-${comparison}`} style={style} aria-label={accessible} title={tooltip} onClick={() => props.onThemeClick(item.theme_id)}>
          <b>{item.observation_rank ?? "-"}</b>
          <span className="observation-gap-theme">{item.theme_name}</span>
          <span className="observation-gap-plot">
            <i className="observation-gap-rail"><em className="observation-gap-range" />{predicted != null ? <span className="observation-gap-marker is-predicted" /> : null}{actualPosition != null ? <span className="observation-gap-marker is-actual" aria-hidden="true">{actualDirectionIcon}</span> : null}</i>
            <small><span>예측 Pctl {valueText(predicted)}</span><span>{actual == null ? "실측 대기" : `실제 Pctl ${valueText(actual)}`}</span></small>
          </span>
          <strong>{gap == null ? "대기" : gapText(gap)}</strong>
        </button>;
      })}
    </div>
  </section>;
}
