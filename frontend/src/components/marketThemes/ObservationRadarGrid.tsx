import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Info } from "lucide-react";
import type { MarketThemeObservationItem } from "@/types/marketTheme";

const AXES = [
  { key: "price_score", label: "가격" },
  { key: "flow_score", label: "수급" },
  { key: "breadth_score", label: "확산" },
  { key: "technical_score", label: "기술" },
  { key: "data_coverage_rate", label: "완전성", ratio: true },
] as const;
type AxisKey = (typeof AXES)[number]["key"];
const AXIS_DESCRIPTIONS: Record<AxisKey, string> = {
  price_score: "당일 및 최근 3·5·10일 등락 흐름과 단기 모멘텀을 활성 테마 간 상대점수로 나타냅니다.",
  flow_score: "외국인·기관 합산 순매수 강도의 현재값, 최근 3·5일 흐름과 가속도를 활성 테마 간 비교합니다.",
  breadth_score: "상승 종목 비율과 외국인·기관 합산 순매수가 양수인 종목 비율로 테마 내부 참여 폭을 나타냅니다.",
  technical_score: "최근 3일·10일 수익률의 상대 위치와 특정 종목 쏠림이 낮은 정도를 평균해 나타냅니다.",
  data_coverage_rate: "연결 종목 중 가격 등락률 수집에 성공해 계산에 포함된 종목 비율입니다. 강세·매수매력 점수가 아닙니다.",
};
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
  const [infoOpen, setInfoOpen] = useState(false);
  const infoRef = useRef<HTMLDivElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const infoId = useId();

  useEffect(() => {
    if (!infoOpen) return;
    const closeOnPointerDown = (event: MouseEvent) => {
      if (!infoRef.current?.contains(event.target as Node)) setInfoOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setInfoOpen(false);
    };
    document.addEventListener("mousedown", closeOnPointerDown);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnPointerDown);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [infoOpen]);

  useLayoutEffect(() => {
    if (!infoOpen) return;
    const updatePopoverPosition = () => {
      const anchor = infoRef.current;
      const popover = popoverRef.current;
      if (!anchor || !popover) return;

      const margin = 12;
      popover.style.top = "calc(100% + 8px)";
      popover.style.bottom = "auto";
      popover.style.maxHeight = "560px";
      popover.style.transform = "none";

      const anchorRect = anchor.getBoundingClientRect();
      const naturalRect = popover.getBoundingClientRect();
      const availableBelow = window.innerHeight - naturalRect.top - margin;
      const availableAbove = anchorRect.top - margin;
      if (availableBelow < Math.min(naturalRect.height, 240) && availableAbove > availableBelow) {
        popover.style.top = "auto";
        popover.style.bottom = "calc(100% + 8px)";
        popover.style.maxHeight = `${Math.max(160, Math.min(560, availableAbove))}px`;
      } else {
        popover.style.maxHeight = `${Math.max(160, Math.min(560, availableBelow))}px`;
      }

      const positionedRect = popover.getBoundingClientRect();
      const leftCorrection = Math.max(0, margin - positionedRect.left);
      const rightCorrection = Math.min(0, window.innerWidth - margin - positionedRect.right);
      popover.style.transform = `translateX(${leftCorrection + rightCorrection}px)`;
    };

    updatePopoverPosition();
    window.addEventListener("resize", updatePopoverPosition);
    window.addEventListener("scroll", updatePopoverPosition, true);
    return () => {
      window.removeEventListener("resize", updatePopoverPosition);
      window.removeEventListener("scroll", updatePopoverPosition, true);
    };
  }, [infoOpen]);

  return <section className="observation-radar-section" aria-labelledby="observation-radar-title">
    <header>
      <div>
        <div className="observation-radar-title-row" ref={infoRef}>
          <h3 id="observation-radar-title">테마 구조 비교</h3>
          <button
            type="button"
            className="observation-radar-info-button"
            aria-label="테마 구조 비교 기준 설명"
            aria-expanded={infoOpen}
            aria-controls={infoId}
            onClick={() => setInfoOpen((value) => !value)}
          >
            <Info size={14} aria-hidden="true" />
          </button>
          {infoOpen ? <div ref={popoverRef} id={infoId} className="observation-radar-info-popover" role="dialog" aria-label="테마 구조 비교 기준 설명">
            <strong>테마 구조 비교 기준</strong>
            <p>가격·수급·확산·기술은 활성 테마 간 상대점수이며, 완전성은 데이터 수집 성공 비율입니다.</p>
            <dl>
              {AXES.map((axis) => <div key={axis.key}>
                <dt>{axis.label}</dt>
                <dd>{AXIS_DESCRIPTIONS[axis.key]}</dd>
              </div>)}
            </dl>
            <div className="observation-radar-info-note">
              <p>각 축은 0~100 기준입니다. 완전성은 강세 정도가 아니라 데이터 충족 수준을 의미합니다.</p>
              <p>레이더 차트는 관찰점수의 구성 상태를 이해하기 위한 보조지표이며, 관찰점수 자체와 동일한 계산식은 아닙니다.</p>
            </div>
          </div> : null}
        </div>
        <p>가격·수급·확산·기술·완전성의 모양으로 관찰점수의 구조를 비교합니다.</p>
      </div>
      <span>동일 축 · 최대 100</span>
    </header>
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
